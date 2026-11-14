"""Projetos: envio do vídeo, lista, detalhes e exclusão."""
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import PASTA_CORTES, PASTA_UPLOADS, PLANOS
from ..database import obter_banco
from ..models import MovimentoCredito, Projeto, Usuario
from ..processamento import download, video
from ..processamento.fila import creditos_para
from ..seguranca import usuario_logado

rotas = APIRouter(prefix="/api/projetos", tags=["Projetos"])
EXTENSOES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def resumo(p: Projeto) -> dict:
    return {"id": p.id, "titulo": p.titulo, "duracao": p.duracao, "inicio": p.inicio, "fim": p.fim,
            "creditos": p.creditos_usados, "status": p.status, "etapa": p.etapa, "progresso": p.progresso,
            "erro": p.erro, "cortes": len(p.cortes), "criado_em": p.criado_em.isoformat(),
            "miniatura": f"/api/cortes/{p.cortes[0].id}/miniatura" if p.cortes and p.cortes[0].miniatura else None}


def corte_json(c, palavras) -> dict:
    from ..processamento.legendas import palavras_do_corte
    return {"id": c.id, "titulo": c.titulo, "inicio": c.inicio, "fim": c.fim, "duracao": round(c.fim - c.inicio, 1),
            "nota": c.nota, "motivo": c.motivo, "estilo": c.estilo,
            "previa": f"/api/cortes/{c.id}/previa", "miniatura": f"/api/cortes/{c.id}/miniatura",
            "palavras": palavras_do_corte(palavras, c.inicio, c.fim, c.estilo.get("texto")),
            "exportado": bool(c.arquivo_final),
            "limite_inicio": c.fonte_inicio if c.fonte_inicio is not None else c.projeto.inicio,
            "limite_fim": c.fonte_fim if c.fonte_fim is not None else c.projeto.fim}


def buscar(banco: Session, usuario: Usuario, projeto_id: int) -> Projeto:
    projeto = banco.get(Projeto, projeto_id)
    if not projeto or projeto.usuario_id != usuario.id:
        raise HTTPException(404, "Projeto não encontrado.")
    return projeto


@rotas.get("")
def listar(usuario: Usuario = Depends(usuario_logado), banco: Session = Depends(obter_banco)):
    projetos = banco.scalars(select(Projeto).where(Projeto.usuario_id == usuario.id).order_by(Projeto.criado_em.desc()))
    return [resumo(p) for p in projetos]


@rotas.post("")
def criar(arquivo: UploadFile = File(...), inicio_min: float = Form(0), fim_min: float = Form(0),
          quantidade: str = Form("auto"), duracao: str = Form("medio"), idioma: str = Form("pt"),
          formato: str = Form("9:16"), usuario: Usuario = Depends(usuario_logado), banco: Session = Depends(obter_banco)):
    extensao = Path(arquivo.filename or "").suffix.lower()
    if extensao not in EXTENSOES:
        raise HTTPException(400, "Envie um vídeo MP4, MOV, MKV, WEBM ou AVI.")
    if formato not in ("9:16", "1:1", "16:9"):
        formato = "9:16"

    # Salva o arquivo em pedaços (aguenta vídeos grandes sem lotar a memória)
    nome = f"{uuid.uuid4().hex}{extensao}"
    destino = PASTA_UPLOADS / nome
    with destino.open("wb") as saida:
        shutil.copyfileobj(arquivo.file, saida, length=4 * 1024 * 1024)

    try:
        total = video.duracao(destino)
    except video.ErroVideo:
        destino.unlink(missing_ok=True)
        raise HTTPException(400, "Não consegui ler esse vídeo. Ele está corrompido?")

    inicio = max(0.0, inicio_min * 60)
    fim = min(total, fim_min * 60) if fim_min > 0 else total
    if fim - inicio < 10:
        destino.unlink(missing_ok=True)
        raise HTTPException(400, "Escolha um trecho de pelo menos 10 segundos.")

    plano = PLANOS[usuario.plano]
    if (fim - inicio) / 60 > plano["max_min"] + 0.01:
        destino.unlink(missing_ok=True)
        raise HTTPException(403, f"Seu plano analisa até {plano['max_min']} minutos por vídeo.")
    custo = creditos_para(fim - inicio)
    if custo > usuario.creditos:
        destino.unlink(missing_ok=True)
        raise HTTPException(402, f"Créditos insuficientes: precisa de {custo}, você tem {usuario.creditos}.")

    titulo = Path(arquivo.filename).stem.replace("_", " ").replace("-", " ").strip()[:200] or "Meu vídeo"
    projeto = Projeto(usuario=usuario, titulo=titulo, arquivo=nome, duracao=total, inicio=inicio, fim=fim,
                      creditos_usados=custo, opcoes={"quantidade": quantidade, "duracao": duracao,
                                                     "idioma": idioma, "formato": formato})
    usuario.creditos -= custo
    banco.add(MovimentoCredito(usuario=usuario, quantidade=-custo, descricao=f"Análise: {titulo}"))
    banco.add(projeto)
    banco.commit()
    return resumo(projeto) | {"saldo": usuario.creditos}


class PedidoLink(BaseModel):
    url: str
    inicio_min: float = 0
    fim_min: float = 0
    quantidade: str = "auto"
    duracao: str = "medio"
    idioma: str = "pt"
    formato: str = "9:16"


@rotas.post("/link/info")
def info_link(dados: PedidoLink, usuario: Usuario = Depends(usuario_logado)):
    """Lê título e duração do vídeo do link, sem baixar (para mostrar o custo antes)."""
    try:
        return download.informacoes(dados.url)
    except download.ErroLink as erro:
        raise HTTPException(400, str(erro))


@rotas.post("/link")
def criar_por_link(dados: PedidoLink, usuario: Usuario = Depends(usuario_logado), banco: Session = Depends(obter_banco)):
    try:
        info = download.informacoes(dados.url)
    except download.ErroLink as erro:
        raise HTTPException(400, str(erro))
    total = info["duracao"]
    inicio = max(0.0, dados.inicio_min * 60)
    fim = min(total, dados.fim_min * 60) if dados.fim_min > 0 else total
    if fim - inicio < 10:
        raise HTTPException(400, "Escolha um trecho de pelo menos 10 segundos.")
    plano = PLANOS[usuario.plano]
    if (fim - inicio) / 60 > plano["max_min"] + 0.01:
        raise HTTPException(403, f"Seu plano analisa até {plano['max_min']} minutos por vídeo.")
    custo = creditos_para(fim - inicio)
    if custo > usuario.creditos:
        raise HTTPException(402, f"Créditos insuficientes: precisa de {custo}, você tem {usuario.creditos}.")
    formato = dados.formato if dados.formato in ("9:16", "1:1", "16:9") else "9:16"
    projeto = Projeto(usuario=usuario, titulo=info["titulo"], arquivo="", duracao=total, inicio=inicio, fim=fim,
                      creditos_usados=custo, etapa="Na fila para baixar",
                      opcoes={"quantidade": dados.quantidade, "duracao": dados.duracao, "idioma": dados.idioma,
                              "formato": formato, "url": info["url"]})
    usuario.creditos -= custo
    banco.add(MovimentoCredito(usuario=usuario, quantidade=-custo, descricao=f"Análise: {info['titulo'][:150]}"))
    banco.add(projeto)
    banco.commit()
    return resumo(projeto) | {"saldo": usuario.creditos}


@rotas.get("/{projeto_id}")
def detalhe(projeto_id: int, usuario: Usuario = Depends(usuario_logado), banco: Session = Depends(obter_banco)):
    p = buscar(banco, usuario, projeto_id)
    return resumo(p) | {"lista_cortes": [corte_json(c, p.transcricao) for c in p.cortes]}


@rotas.delete("/{projeto_id}")
def excluir(projeto_id: int, usuario: Usuario = Depends(usuario_logado), banco: Session = Depends(obter_banco)):
    p = buscar(banco, usuario, projeto_id)
    if p.status == "processando":
        raise HTTPException(409, "Espere o processamento terminar para excluir.")
    if p.arquivo:
        (PASTA_UPLOADS / p.arquivo).unlink(missing_ok=True)
    shutil.rmtree(PASTA_CORTES / str(p.id), ignore_errors=True)
    banco.delete(p)
    banco.commit()
    return {"ok": True}
