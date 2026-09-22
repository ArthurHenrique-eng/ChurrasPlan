"""Snapshot IMUTÁVEL do metadata ChurrasPlan v0.2.

Usado exclusivamente pela migration 20260917_0001 ao inicializar um banco
vazio. Alterar este arquivo muda o significado histórico da migration 0001.
"""
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import declarative_base, declared_attr, relationship

BaseV02 = declarative_base()


class Usuario(BaseV02):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(120), nullable=False)
    email = Column(String(160), nullable=False, unique=True, index=True)
    senha_hash = Column(String(255), nullable=False)
    criado_em = Column(DateTime, server_default=func.now())
    churrascos = relationship("Churrasco", back_populates="usuario")


class Categoria(BaseV02):
    __tablename__ = "categorias"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(60), nullable=False, unique=True)
    tipo = Column(String(30), nullable=False)


class Produto(BaseV02):
    __tablename__ = "produtos"
    id = Column(Integer, primary_key=True, index=True)
    categoria_id = Column(Integer, ForeignKey("categorias.id", ondelete="RESTRICT"), nullable=False, index=True)
    slug = Column(String(140), nullable=False, unique=True, index=True)
    nome = Column(String(120), nullable=False)
    unidade_consumo = Column(String(30), nullable=False)
    unidade_venda = Column(String(30), nullable=False)
    venda_fracionada = Column(Boolean, nullable=False, default=False)
    incremento_venda = Column(Numeric(12, 3), nullable=True)
    quantidade_embalagem = Column(Numeric(12, 3), nullable=True)
    unidade_embalagem = Column(String(30), nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    imagem_url = Column(String(255), nullable=True)
    descricao = Column(Text, nullable=True)
    categoria = relationship("Categoria")
    precos = relationship("Preco", back_populates="produto", cascade="all, delete-orphan")


class Estabelecimento(BaseV02):
    __tablename__ = "estabelecimentos"
    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(170), nullable=False, unique=True, index=True)
    nome = Column(String(150), nullable=False)
    tipo = Column(String(60), nullable=False)
    endereco = Column(String(255), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    telefone = Column(String(30), nullable=True)
    site = Column(String(255), nullable=True)
    horario_funcionamento = Column(String(120), nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    precos = relationship("Preco", back_populates="estabelecimento", cascade="all, delete-orphan")


class Preco(BaseV02):
    __tablename__ = "precos"
    id = Column(Integer, primary_key=True, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id", ondelete="CASCADE"), nullable=False, index=True)
    estabelecimento_id = Column(Integer, ForeignKey("estabelecimentos.id", ondelete="CASCADE"), nullable=False, index=True)
    preco = Column(Numeric(12, 2), nullable=False)
    fonte = Column(String(255), nullable=True)
    disponivel = Column(Boolean, nullable=False, default=True)
    coletado_em = Column(DateTime, server_default=func.now(), nullable=False)
    data_atualizacao = Column(DateTime, server_default=func.now(), nullable=False)
    produto = relationship("Produto", back_populates="precos")
    estabelecimento = relationship("Estabelecimento", back_populates="precos")


class Churrasco(BaseV02):
    __tablename__ = "churrascos"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    nome = Column(String(150), nullable=True)
    chave_cliente = Column(String(64), nullable=True, unique=True, index=True)
    tipo_evento = Column(String(60), nullable=False)
    duracao_horas = Column(Float, nullable=False)
    perfil_consumo = Column(String(20), nullable=False)
    perfil_personalizado = Column(JSON, nullable=True)
    homens = Column(Integer, nullable=False, default=0)
    mulheres = Column(Integer, nullable=False, default=0)
    criancas = Column(Integer, nullable=False, default=0)
    homens_bebem_alcool = Column(Integer, nullable=False, default=0)
    mulheres_bebem_alcool = Column(Integer, nullable=False, default=0)
    carne_total_kg = Column(Numeric(12, 3), nullable=True)
    carvao_ativo = Column(Boolean, nullable=False, default=True)
    gelo_ativo = Column(Boolean, nullable=False, default=False)
    carvao_necessario_kg = Column(Numeric(12, 3), nullable=True)
    carvao_compra_kg = Column(Numeric(12, 3), nullable=True)
    custo_total_estimado = Column(Numeric(12, 2), nullable=True)
    custo_por_pessoa = Column(Numeric(12, 2), nullable=True)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    usuario = relationship("Usuario", back_populates="churrascos")
    carnes = relationship("ChurrascoCarne", back_populates="churrasco", cascade="all, delete-orphan", passive_deletes=True)
    bebidas = relationship("ChurrascoBebida", back_populates="churrasco", cascade="all, delete-orphan", passive_deletes=True)
    itens_extra = relationship("ChurrascoExtra", back_populates="churrasco", cascade="all, delete-orphan", passive_deletes=True)
    lista_compras = relationship("ListaCompras", back_populates="churrasco", uselist=False, cascade="all, delete-orphan", passive_deletes=True)


class ItemCalculadoMixin:
    produto_id = Column(Integer, ForeignKey("produtos.id", ondelete="SET NULL"), nullable=True, index=True)
    preco_id = Column(Integer, ForeignKey("precos.id", ondelete="SET NULL"), nullable=True)
    produto_slug = Column(String(140), nullable=True, index=True)
    nome_item = Column(String(120), nullable=False)
    quantidade_necessaria = Column(Numeric(12, 3), nullable=False)
    unidade_necessaria = Column(String(30), nullable=False)
    quantidade_compra = Column(Numeric(12, 3), nullable=False)
    unidade_compra = Column(String(30), nullable=False)
    quantidade_embalagens = Column(Integer, nullable=True)
    tamanho_embalagem = Column(Numeric(12, 3), nullable=True)
    unidade_embalagem = Column(String(30), nullable=True)
    unidade_venda = Column(String(30), nullable=False)
    preco_unitario = Column(Numeric(12, 2), nullable=True)
    subtotal_estimado = Column(Numeric(12, 2), nullable=True)
    estabelecimento_id = Column(Integer, ForeignKey("estabelecimentos.id", ondelete="SET NULL"), nullable=True)

    @declared_attr
    def produto(cls):
        return relationship("Produto")

    @declared_attr
    def preco(cls):
        return relationship("Preco")

    @declared_attr
    def estabelecimento(cls):
        return relationship("Estabelecimento")


class ChurrascoCarne(ItemCalculadoMixin, BaseV02):
    __tablename__ = "churrasco_carnes"
    id = Column(Integer, primary_key=True, index=True)
    churrasco_id = Column(Integer, ForeignKey("churrascos.id", ondelete="CASCADE"), nullable=False, index=True)
    percentual = Column(Numeric(6, 2), nullable=False)
    churrasco = relationship("Churrasco", back_populates="carnes")


class ChurrascoBebida(ItemCalculadoMixin, BaseV02):
    __tablename__ = "churrasco_bebidas"
    id = Column(Integer, primary_key=True, index=True)
    churrasco_id = Column(Integer, ForeignKey("churrascos.id", ondelete="CASCADE"), nullable=False, index=True)
    churrasco = relationship("Churrasco", back_populates="bebidas")


class ChurrascoExtra(ItemCalculadoMixin, BaseV02):
    __tablename__ = "churrasco_extras"
    id = Column(Integer, primary_key=True, index=True)
    churrasco_id = Column(Integer, ForeignKey("churrascos.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo = Column(String(30), nullable=False)
    churrasco = relationship("Churrasco", back_populates="itens_extra")


class ListaCompras(BaseV02):
    __tablename__ = "lista_compras"
    id = Column(Integer, primary_key=True, index=True)
    churrasco_id = Column(Integer, ForeignKey("churrascos.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)
    churrasco = relationship("Churrasco", back_populates="lista_compras")
    itens = relationship("ListaComprasItem", back_populates="lista", cascade="all, delete-orphan", passive_deletes=True)


class ListaComprasItem(BaseV02):
    __tablename__ = "lista_compras_itens"
    id = Column(Integer, primary_key=True, index=True)
    lista_compras_id = Column(Integer, ForeignKey("lista_compras.id", ondelete="CASCADE"), nullable=False, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id", ondelete="SET NULL"), nullable=True)
    descricao = Column(String(150), nullable=False)
    quantidade = Column(Numeric(12, 3), nullable=False)
    unidade = Column(String(30), nullable=False)
    quantidade_embalagens = Column(Integer, nullable=True)
    unidade_venda = Column(String(30), nullable=False)
    categoria = Column(String(30), nullable=False)
    preco_unitario = Column(Numeric(12, 2), nullable=True)
    subtotal_estimado = Column(Numeric(12, 2), nullable=True)
    comprado = Column(Boolean, nullable=False, default=False)
    lista = relationship("ListaCompras", back_populates="itens")
    produto = relationship("Produto")
