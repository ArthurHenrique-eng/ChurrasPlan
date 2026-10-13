from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint, func
from database.connection import Base


class ClienteProfissional(Base):
    __tablename__ = "clientes_profissionais"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    nome = Column(String(120), nullable=False)
    email = Column(String(160), nullable=True)
    telefone = Column(String(30), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())


class PropostaProfissional(Base):
    __tablename__ = "propostas_profissionais"
    __table_args__ = (UniqueConstraint("usuario_id", "chave", name="uq_proposta_usuario_chave"),)
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes_profissionais.id", ondelete="SET NULL"), nullable=True)
    churrasco_id = Column(Integer, ForeignKey("churrascos.id", ondelete="SET NULL"), nullable=True)
    chave = Column(String(80), nullable=False)
    titulo = Column(String(150), nullable=False)
    snapshot = Column(JSON, nullable=False)
    custo_estimado = Column(Numeric(12, 2), nullable=False)
    preco_proposto = Column(Numeric(12, 2), nullable=False)
    status = Column(String(20), nullable=False, default="rascunho", server_default="rascunho")
    criado_em = Column(DateTime, nullable=False, server_default=func.now())


class FavoritoEstabelecimento(Base):
    __tablename__ = "favoritos_estabelecimentos"
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    estabelecimento_id = Column(Integer, ForeignKey("estabelecimentos.id", ondelete="CASCADE"), primary_key=True)


class LembreteEvento(Base):
    __tablename__ = "lembretes_evento"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    churrasco_id = Column(Integer, ForeignKey("churrascos.id", ondelete="CASCADE"), nullable=False)
    tarefa_id = Column(Integer, ForeignKey("tarefas_outbox.id", ondelete="SET NULL"), nullable=True)
    quando = Column(DateTime, nullable=False)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
