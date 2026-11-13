"""Fila de processamento: um "trabalhador" em segundo plano pega os projetos
na fila, um de cada vez, e transforma cada vídeo em cortes."""
import logging
import math
import threading
import time
import traceback
import uuid

from sqlalchemy import select

from ..config import PASTA_CORTES, PASTA_UPLOADS, PLANOS
from ..database import SessaoBanco
from ..models import Corte, MovimentoCredito, Projeto
from . import destaques, download, transcricao, video

log = logging.getLogger("clipstorage.fila")
_parar = threading.Event()


def _etapa(banco, projeto: Projeto, texto: str, progresso: int):
    projeto.etapa, projeto.progresso = texto, progresso
    banco.commit()
    log.info("Projeto %s: %s (%s%%)", projeto.id, texto, progresso)


def processar(projeto_id: int):
    banco = SessaoBanco()
    projeto = banco.get(Projeto, projeto_id)
    try:
        projeto.status = "processando"
        pasta = PASTA_CORTES / str(projeto.id)
        pasta.mkdir(parents=True, exist_ok=True)
        opcoes = projeto.opcoes or {}
        plano = PLANOS[projeto.usuario.plano]

        # Veio de um link? Baixa só o trecho escolhido.
        if opcoes.get("url") and not projeto.arquivo:
            _etapa(banco, projeto, "Baixando o vídeo do link", 1)

            def baixando(fracao):
                novo = 1 + int(fracao * 8)
                if novo > projeto.progresso:
                    _etapa(banco, projeto, f"Baixando o vídeo do link ({int(fracao * 100)}%)", novo)

            nome = uuid.uuid4().hex
            baixado = download.baixar_trecho(opcoes["url"], projeto.inicio, projeto.fim, PASTA_UPLOADS, nome, baixando)
            # o arquivo baixado já é só o trecho: passa a começar do zero
            projeto.arquivo = baixado.name
            projeto.opcoes = {**opcoes, "inicio_original": projeto.inicio}
            projeto.inicio, projeto.fim = 0.0, video.duracao(baixado)
            banco.commit()

        origem = PASTA_UPLOADS / projeto.arquivo

        _etapa(banco, projeto, "Lendo o vídeo", 5)
        palavras = None
        if video.tem_audio(origem):
            _etapa(banco, projeto, "Transformando o áudio em texto", 10)
            wav = video.extrair_audio(origem, projeto.inicio, projeto.fim, pasta / "audio.wav")

            def avancar(fracao):
                novo = 10 + int(fracao * 45)
                if novo - projeto.progresso >= 3:
                    _etapa(banco, projeto, "Transformando o áudio em texto", novo)

            palavras = transcricao.transcrever(wav, projeto.inicio, opcoes.get("idioma", "pt"), avancar)
            wav.unlink(missing_ok=True)
            projeto.transcricao = palavras

            _etapa(banco, projeto, "Medindo os momentos mais empolgantes", 58)
            volumes = video.volume_por_segundo(origem, projeto.inicio, projeto.fim)
        else:
            volumes = [0.0] * int(projeto.fim - projeto.inicio)

        _etapa(banco, projeto, "A IA está escolhendo os melhores trechos", 65)
        minutos = (projeto.fim - projeto.inicio) / 60
        qtd = destaques.quantos_cortes(minutos, str(opcoes.get("quantidade", "auto")), plano["max_cortes"])
        escolhidos, modo = destaques.escolher(volumes, projeto.inicio, palavras, qtd, opcoes.get("duracao", "medio"))
        if not escolhidos:
            raise RuntimeError("Não encontrei trechos bons nesse vídeo.")
        log.info("Projeto %s: %s cortes escolhidos (modo %s)", projeto.id, len(escolhidos), modo)

        formato = opcoes.get("formato", "9:16")
        for n, c in enumerate(escolhidos, start=1):
            _etapa(banco, projeto, f"Cortando e ajustando o formato ({n} de {len(escolhidos)})",
                   70 + int(28 * (n - 1) / len(escolhidos)))
            corte = Corte(projeto=projeto, titulo=c["titulo"], inicio=c["inicio"], fim=c["fim"], nota=c["nota"],
                          motivo=c["motivo"], estilo={"legenda": "destaque", "cor": "#ffd84d", "posicao": "baixo", "formato": formato})
            banco.add(corte)
            banco.flush()
            previa = pasta / f"corte_{corte.id}_previa.mp4"
            # prévia leve (sem legenda gravada: o editor mostra a legenda por cima)
            video.renderizar(origem, c["inicio"], c["fim"], previa, formato, escala=0.5, rapido=True)
            corte.arquivo_previa = str(previa.relative_to(PASTA_CORTES))
            corte.miniatura = str(video.miniatura(previa, pasta / f"corte_{corte.id}.jpg").relative_to(PASTA_CORTES))
            banco.commit()

        projeto.status = "pronto"
        _etapa(banco, projeto, "Tudo pronto!", 100)
    except Exception as erro:
        log.error("Erro no projeto %s:\n%s", projeto_id, traceback.format_exc())
        banco.rollback()
        projeto = banco.get(Projeto, projeto_id)
        projeto.status, projeto.erro, projeto.etapa = "erro", str(erro)[:500], "Erro no processamento"
        # devolve os créditos
        if projeto.creditos_usados:
            projeto.usuario.creditos += projeto.creditos_usados
            banco.add(MovimentoCredito(usuario_id=projeto.usuario_id, quantidade=projeto.creditos_usados,
                                       descricao=f"Estorno: {projeto.titulo}"))
            projeto.creditos_usados = 0
        banco.commit()
    finally:
        banco.close()


def _laco():
    # Se o servidor caiu no meio de um processamento, recoloca na fila
    with SessaoBanco() as banco:
        for p in banco.scalars(select(Projeto).where(Projeto.status == "processando")):
            p.status, p.etapa, p.progresso = "fila", "Na fila", 0
            p.cortes.clear()
        banco.commit()
    while not _parar.is_set():
        with SessaoBanco() as banco:
            proximo = banco.scalar(select(Projeto.id).where(Projeto.status == "fila").order_by(Projeto.criado_em))
        if proximo:
            processar(proximo)
        else:
            time.sleep(1.5)


def iniciar():
    _parar.clear()
    threading.Thread(target=_laco, name="fila-de-cortes", daemon=True).start()


def parar():
    _parar.set()


def creditos_para(segundos: float) -> int:
    return max(1, math.ceil(segundos / 60))
