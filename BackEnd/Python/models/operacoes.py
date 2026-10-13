"""Estado durável de segurança e operação; nenhum segredo em texto puro."""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, Index, func
from database.connection import Base


class CredencialMFA(Base):
    __tablename__ = "credenciais_mfa"
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    segredo_cifrado = Column(Text, nullable=False)
    ativo = Column(Boolean, nullable=False, default=False, server_default="0")
    ultimo_passo = Column(Integer, nullable=False, default=-1, server_default="-1")
    criado_em = Column(DateTime, nullable=False, server_default=func.now())


class RecuperacaoMFA(Base):
    __tablename__ = "recuperacao_mfa"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    codigo_hash = Column(String(64), nullable=False, unique=True)
    usado_em = Column(DateTime, nullable=True)


class ContadorRequisicao(Base):
    __tablename__ = "contadores_requisicao"
    chave = Column(String(64), primary_key=True)
    janela = Column(Integer, primary_key=True)
    quantidade = Column(Integer, nullable=False, default=1)


class TarefaOutbox(Base):
    __tablename__ = "tarefas_outbox"
    __table_args__ = (Index("ix_outbox_pronta", "status", "disponivel_em"),)
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=True, index=True)
    tipo = Column(String(40), nullable=False)
    chave = Column(String(120), nullable=False, unique=True)
    payload_cifrado = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="pendente", server_default="pendente")
    tentativas = Column(Integer, nullable=False, default=0, server_default="0")
    disponivel_em = Column(DateTime, nullable=False, server_default=func.now())
    lease_ate = Column(DateTime, nullable=True)
    lease_token = Column(String(64), nullable=True)
    erro_tipo = Column(String(80), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    concluido_em = Column(DateTime, nullable=True)


class EstadoWorker(Base):
    __tablename__ = "estado_worker"
    nome = Column(String(80), primary_key=True)
    heartbeat_em = Column(DateTime, nullable=False)
