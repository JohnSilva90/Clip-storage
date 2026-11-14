"""Fila de processamento: um "trabalhador" em segundo plano pega os projetos
na fila, um de cada vez, e transforma cada vídeo em cortes."""
import logging
import math
import threading
import time
import traceback
import uuid

from sqlalchemy import select

from datetime import datetime, timedelta, timezone
import shutil

from ..contas import plano_de
from ..config import DIAS_GUARDAR, FOLGA_FONTE, PASTA_CORTES, PASTA_UPLOADS, PLANOS
from ..database import SessaoBanco
from ..models import Corte, MovimentoCredito, Projeto
from . import destaques, download, enquadramento, transcricao, video

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
        plano = plano_de(projeto.usuario)

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
            _etapa(banco, projeto, f"Enquadrando e cortando ({n} de {len(escolhidos)})",
                   70 + int(28 * (n - 1) / len(escolhidos)))
            layout = enquadramento.analisar(origem, c["inicio"], c["fim"])
            corte = Corte(projeto=projeto, titulo=c["titulo"], inicio=c["inicio"], fim=c["fim"], nota=c["nota"],
                          motivo=c["motivo"], estilo={"legenda": "destaque", "cor": "#ffd84d", "posicao": "baixo",
                                                      "formato": formato, "layout": "auto", "enquadramento": layout})
            banco.add(corte)
            banco.flush()
            # Guarda só um pedaço do original (corte + folga) para editar e exportar depois
            a = max(0.0, c["inicio"] - FOLGA_FONTE)
            b = min(video.duracao(origem), c["fim"] + FOLGA_FONTE)
            fonte = video.recortar_fonte(origem, a, b, pasta / f"corte_{corte.id}_fonte.mp4")
            corte.arquivo_fonte, corte.fonte_inicio, corte.fonte_fim = str(fonte.relative_to(PASTA_CORTES)), a, b
            previa = pasta / f"corte_{corte.id}_previa.mp4"
            # prévia leve (sem legenda gravada: o editor mostra a legenda por cima)
            video.renderizar(fonte, c["inicio"] - a, c["fim"] - a, previa, formato, escala=0.5, rapido=True, layout=layout)
            corte.arquivo_previa = str(previa.relative_to(PASTA_CORTES))
            corte.miniatura = str(video.miniatura(previa, pasta / f"corte_{corte.id}.jpg").relative_to(PASTA_CORTES))
            banco.commit()

        # O vídeo original não é mais necessário: apaga para não lotar o disco
        origem.unlink(missing_ok=True)
        projeto.arquivo = ""
        projeto.opcoes = {**(projeto.opcoes or {}), "original_apagado": True}
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


def limpar_antigos():
    """Apaga projetos mais antigos que DIAS_GUARDAR (arquivos e registros)."""
    limite = datetime.now(timezone.utc) - timedelta(days=DIAS_GUARDAR)
    with SessaoBanco() as banco:
        for p in banco.scalars(select(Projeto).where(Projeto.criado_em < limite, Projeto.status.in_(("pronto", "erro")))):
            if p.arquivo:
                (PASTA_UPLOADS / p.arquivo).unlink(missing_ok=True)
            shutil.rmtree(PASTA_CORTES / str(p.id), ignore_errors=True)
            banco.delete(p)
            log.info("Projeto %s apagado (mais de %s dias).", p.id, DIAS_GUARDAR)
        banco.commit()


def _laco():
    # Se o servidor caiu no meio de um processamento, recoloca na fila
    with SessaoBanco() as banco:
        for p in banco.scalars(select(Projeto).where(Projeto.status == "processando")):
            p.status, p.etapa, p.progresso = "fila", "Na fila", 0
            p.cortes.clear()
        banco.commit()
    ultima_limpeza = 0.0
    while not _parar.is_set():
        if time.time() - ultima_limpeza > 3600:
            ultima_limpeza = time.time()
            try:
                limpar_antigos()
            except Exception:
                log.exception("Falha na limpeza de projetos antigos")
            try:
                from ..rotas.pagamentos import rotina_de_pagamentos
                rotina_de_pagamentos()
            except Exception:
                log.exception("Falha na rotina de pagamentos")
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
