"""Leads solicitados, métricas mínimas e indicação consentida."""
from sqlalchemy import Column, DateTime, Boolean, ForeignKey, Index, Integer, JSON, Numeric, String, Text, func
from database.connection import Base


class LeadComercial(Base):
    __tablename__ = "leads_comerciais"
    id = Column(Integer, primary_key=True)
    nome = Column(String(120), nullable=False)
    email = Column(String(160), nullable=False, index=True)
    empresa = Column(String(150), nullable=False)
    tipo_estabelecimento = Column(String(40), nullable=False)
    cidade = Column(String(120), nullable=False)
    origem = Column(String(60), nullable=False, default="parceiros", server_default="parceiros")
    utm = Column(JSON, nullable=True)
    status = Column(String(30), nullable=False, default="novo", server_default="novo", index=True)
    marketing_concedido = Column(Boolean, nullable=False, default=False, server_default="0")
    marketing_revogado_em = Column(DateTime, nullable=True)
    descadastro_hash = Column(String(64), nullable=False, unique=True)
    privacidade_versao = Column(String(40), nullable=False)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="SET NULL"), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now(), index=True)


class AtividadeLead(Base):
    __tablename__ = "atividades_lead"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("leads_comerciais.id", ondelete="CASCADE"), nullable=False, index=True)
    admin_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    tipo = Column(String(30), nullable=False)
    nota = Column(String(800), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())


class EventoProduto(Base):
    __tablename__ = "eventos_produto"
    __table_args__ = (Index("ix_eventos_produto_funil", "contexto_tipo", "criado_em", "contexto_hash", "evento"),)
    id = Column(Integer, primary_key=True)
    evento = Column(String(60), nullable=False, index=True)
    propriedades = Column(JSON, nullable=False)
    dedup_hash = Column(String(64), nullable=False, unique=True)
    contexto_tipo = Column(String(20), nullable=True)
    contexto_hash = Column(String(64), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now(), index=True)


class IndicacaoUsuario(Base):
    __tablename__ = "indicacoes_usuario"
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    codigo = Column(String(48), nullable=False, unique=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())


class AtribuicaoCadastro(Base):
    __tablename__ = "atribuicoes_cadastro"
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    indicador_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())


class FeedbackParceiro(Base):
    __tablename__ = "feedback_parceiro"
    id = Column(Integer, primary_key=True)
    organizacao_id = Column(Integer, ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False, index=True)
    nota = Column(Integer, nullable=False)
    comentario = Column(String(800), nullable=True)
    disposicao_pagar = Column(Numeric(10, 2), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())


class CustoOperacao(Base):
    __tablename__ = "custos_operacao"
    id = Column(Integer, primary_key=True)
    competencia = Column(String(7), nullable=False, index=True)
    categoria = Column(String(30), nullable=False)
    valor = Column(Numeric(12, 2), nullable=False)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
