"""Tabelas do banco de dados."""
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def agora():
    return datetime.now(timezone.utc)


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(100))
    plano: Mapped[str] = mapped_column(String(20), default="explorador")
    creditos: Mapped[int] = mapped_column(Integer, default=8)
    assinatura_mp_id: Mapped[str | None] = mapped_column(String(60), nullable=True)  # assinatura ativa no Mercado Pago
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    projetos: Mapped[list["Projeto"]] = relationship(back_populates="usuario", cascade="all, delete-orphan")
    movimentos: Mapped[list["MovimentoCredito"]] = relationship(back_populates="usuario", cascade="all, delete-orphan")


class Projeto(Base):
    """Um vídeo enviado pelo usuário, que vira vários cortes."""
    __tablename__ = "projetos"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    titulo: Mapped[str] = mapped_column(String(200))
    arquivo: Mapped[str] = mapped_column(String(300))            # caminho do vídeo original
    duracao: Mapped[float] = mapped_column(Float, default=0)      # segundos do vídeo inteiro
    inicio: Mapped[float] = mapped_column(Float, default=0)       # trecho analisado (segundos)
    fim: Mapped[float] = mapped_column(Float, default=0)
    creditos_usados: Mapped[int] = mapped_column(Integer, default=0)
    opcoes: Mapped[dict] = mapped_column(JSON, default=dict)      # qtd de cortes, duração, idioma, formato
    status: Mapped[str] = mapped_column(String(20), default="fila")  # fila, processando, pronto, erro
    etapa: Mapped[str] = mapped_column(String(120), default="Na fila")
    progresso: Mapped[int] = mapped_column(Integer, default=0)
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcricao: Mapped[list | None] = mapped_column(JSON, nullable=True)  # palavras com tempo
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    usuario: Mapped[Usuario] = relationship(back_populates="projetos")
    cortes: Mapped[list["Corte"]] = relationship(back_populates="projeto", cascade="all, delete-orphan", order_by="Corte.nota.desc()")


class Corte(Base):
    """Um trecho curto escolhido pela IA."""
    __tablename__ = "cortes"

    id: Mapped[int] = mapped_column(primary_key=True)
    projeto_id: Mapped[int] = mapped_column(ForeignKey("projetos.id"), index=True)
    titulo: Mapped[str] = mapped_column(String(200))
    inicio: Mapped[float] = mapped_column(Float)   # segundos no vídeo original
    fim: Mapped[float] = mapped_column(Float)
    nota: Mapped[int] = mapped_column(Integer, default=50)
    motivo: Mapped[str] = mapped_column(Text, default="")
    estilo: Mapped[dict] = mapped_column(JSON, default=dict)   # legenda, cor, posição, formato
    arquivo_fonte: Mapped[str | None] = mapped_column(String(300), nullable=True)   # pedaço do original guardado
    fonte_inicio: Mapped[float | None] = mapped_column(Float, nullable=True)
    fonte_fim: Mapped[float | None] = mapped_column(Float, nullable=True)
    arquivo_previa: Mapped[str | None] = mapped_column(String(300), nullable=True)
    arquivo_final: Mapped[str | None] = mapped_column(String(300), nullable=True)
    miniatura: Mapped[str | None] = mapped_column(String(300), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    projeto: Mapped[Projeto] = relationship(back_populates="cortes")


class MovimentoCredito(Base):
    """Histórico: cada gasto ou recarga de créditos."""
    __tablename__ = "movimentos_credito"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    quantidade: Mapped[int] = mapped_column(Integer)   # negativo = gasto
    descricao: Mapped[str] = mapped_column(String(200))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)

    usuario: Mapped[Usuario] = relationship(back_populates="movimentos")


class Pedido(Base):
    """Uma compra: pacote de créditos ou assinatura de plano."""
    __tablename__ = "pedidos"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    referencia: Mapped[str] = mapped_column(String(40), unique=True, index=True)  # external_reference
    tipo: Mapped[str] = mapped_column(String(20))           # "creditos" ou "assinatura"
    plano: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quantidade: Mapped[int] = mapped_column(Integer, default=0)   # créditos do pacote
    valor: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="pendente")  # pendente, aprovado, recusado, cancelado
    mp_id: Mapped[str | None] = mapped_column(String(60), nullable=True)  # id do pagamento/assinatura no MP
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    aprovado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    usuario: Mapped[Usuario] = relationship()
