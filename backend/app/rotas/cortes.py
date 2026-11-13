"""Cortes: vídeo de prévia, edição (trecho e estilo), exportação em 1080p e download."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import PASTA_CORTES, PASTA_UPLOADS, PLANOS
from ..database import obter_banco
from ..models import Corte, Usuario
from ..processamento import legendas, video
from ..seguranca import usuario_logado
from .projetos import corte_json

rotas = APIRouter(prefix="/api/cortes", tags=["Cortes"])
CORES_OK = {"#ffd84d", "#ff8a3d", "#a78bfa", "#34d399", "#60a5fa", "#ffffff"}


class Edicao(BaseModel):
    titulo: str | None = None
    inicio: float | None = None
    fim: float | None = None
    legenda: str | None = None    # destaque, classica, neon
    cor: str | None = None
    posicao: str | None = None    # cima, meio, baixo
    formato: str | None = None    # 9:16, 1:1, 16:9
    texto: str | None = None      # texto da legenda editado à mão


def buscar(banco: Session, usuario: Usuario, corte_id: int) -> Corte:
    corte = banco.get(Corte, corte_id)
    if not corte or corte.projeto.usuario_id != usuario.id:
        raise HTTPException(404, "Corte não encontrado.")
    return corte


def _arquivo(relativo: str | None):
    if not relativo:
        raise HTTPException(404, "Arquivo ainda não existe.")
    caminho = (PASTA_CORTES / relativo).resolve()
    if PASTA_CORTES.resolve() not in caminho.parents or not caminho.exists():
        raise HTTPException(404, "Arquivo não encontrado.")
    return caminho


@rotas.get("/{corte_id}/previa")
def previa(corte_id: int, usuario: Usuario = Depends(usuario_logado), banco: Session = Depends(obter_banco)):
    return FileResponse(_arquivo(buscar(banco, usuario, corte_id).arquivo_previa), media_type="video/mp4")


@rotas.get("/{corte_id}/miniatura")
def miniatura(corte_id: int, usuario: Usuario = Depends(usuario_logado), banco: Session = Depends(obter_banco)):
    return FileResponse(_arquivo(buscar(banco, usuario, corte_id).miniatura), media_type="image/jpeg")


@rotas.patch("/{corte_id}")
def editar(corte_id: int, dados: Edicao, usuario: Usuario = Depends(usuario_logado), banco: Session = Depends(obter_banco)):
    corte = buscar(banco, usuario, corte_id)
    projeto = corte.projeto
    estilo = dict(corte.estilo or {})
    if dados.legenda in ("destaque", "classica", "neon"):
        estilo["legenda"] = dados.legenda
    if dados.cor in CORES_OK:
        estilo["cor"] = dados.cor
    if dados.posicao in ("cima", "meio", "baixo"):
        estilo["posicao"] = dados.posicao
    formato_mudou = dados.formato in ("9:16", "1:1", "16:9") and dados.formato != estilo.get("formato")
    if dados.formato in ("9:16", "1:1", "16:9"):
        estilo["formato"] = dados.formato
    if dados.texto is not None:
        estilo["texto"] = dados.texto.strip()[:600] or None
    if dados.titulo:
        corte.titulo = dados.titulo.strip()[:200]

    trecho_mudou = False
    if dados.inicio is not None and dados.fim is not None:
        ini = max(projeto.inicio, min(dados.inicio, projeto.fim - 3))
        fim = min(projeto.fim, max(dados.fim, ini + 3))
        if fim - ini > 180:
            raise HTTPException(400, "Um corte pode ter no máximo 3 minutos.")
        trecho_mudou = abs(ini - corte.inicio) > 0.05 or abs(fim - corte.fim) > 0.05
        corte.inicio, corte.fim = ini, fim

    corte.estilo = estilo
    corte.arquivo_final = None   # precisa exportar de novo
    if trecho_mudou or formato_mudou:
        pasta = PASTA_CORTES / str(projeto.id)
        previa_nova = pasta / f"corte_{corte.id}_previa.mp4"
        video.renderizar(PASTA_UPLOADS / projeto.arquivo, corte.inicio, corte.fim, previa_nova,
                         estilo["formato"], escala=0.5, rapido=True)
        video.miniatura(previa_nova, pasta / f"corte_{corte.id}.jpg")
    banco.commit()
    return corte_json(corte, projeto.transcricao)


@rotas.post("/{corte_id}/exportar")
def exportar(corte_id: int, usuario: Usuario = Depends(usuario_logado), banco: Session = Depends(obter_banco)):
    """Gera o vídeo final em 1080p com a legenda gravada (e marca d'água no plano grátis)."""
    corte = buscar(banco, usuario, corte_id)
    projeto = corte.projeto
    pasta = PASTA_CORTES / str(projeto.id)
    estilo = corte.estilo or {}
    lista = legendas.palavras_do_corte(projeto.transcricao, corte.inicio, corte.fim, estilo.get("texto"))
    marca = PLANOS[usuario.plano]["marca_dagua"]
    ass = None
    if lista or marca:
        ass = legendas.gerar_ass(lista, estilo, pasta / f"corte_{corte.id}.ass", marca, corte.fim - corte.inicio)
    final = pasta / f"corte_{corte.id}_final.mp4"
    try:
        video.renderizar(PASTA_UPLOADS / projeto.arquivo, corte.inicio, corte.fim, final,
                         estilo.get("formato", "9:16"), escala=1.0, legenda_ass=ass)
    except video.ErroVideo as erro:
        raise HTTPException(500, f"Falha ao exportar: {erro}")
    corte.arquivo_final = str(final.relative_to(PASTA_CORTES))
    banco.commit()
    return {"ok": True, "baixar": f"/api/cortes/{corte.id}/baixar"}


@rotas.get("/{corte_id}/baixar")
def baixar(corte_id: int, usuario: Usuario = Depends(usuario_logado), banco: Session = Depends(obter_banco)):
    corte = buscar(banco, usuario, corte_id)
    nome = "".join(ch for ch in corte.titulo if ch.isalnum() or ch in " -_")[:50].strip() or f"corte-{corte.id}"
    return FileResponse(_arquivo(corte.arquivo_final), media_type="video/mp4", filename=f"{nome}.mp4")
