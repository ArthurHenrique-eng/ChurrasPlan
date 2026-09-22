-- ChurrasPlan v6.4 - schema MySQL de referência (Alembic head 20260918_0005).
-- Fonte de verdade para evolução: Alembic (`alembic upgrade head`).
-- Este arquivo representa uma instalação NOVA no head 20260918_0005.
-- Para bancos existentes, NÃO recrie tabelas: aplique as migrations.
CREATE DATABASE IF NOT EXISTS churrasplan CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE churrasplan;

CREATE TABLE categorias (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nome VARCHAR(60) NOT NULL, 
	tipo VARCHAR(30) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (nome)
) ENGINE=InnoDB;
CREATE INDEX ix_categorias_id ON categorias (id);

CREATE TABLE eventos_seguranca (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tipo VARCHAR(40) NOT NULL, 
	chave_hash VARCHAR(64) NOT NULL, 
	sucesso BOOL NOT NULL DEFAULT '0', 
	criado_em DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id)
) ENGINE=InnoDB;
CREATE INDEX ix_eventos_seguranca_chave_hash ON eventos_seguranca (chave_hash);
CREATE INDEX ix_eventos_seguranca_criado_em ON eventos_seguranca (criado_em);
CREATE INDEX ix_eventos_seguranca_tipo ON eventos_seguranca (tipo);
CREATE INDEX ix_eventos_seguranca_tipo_chave_criado ON eventos_seguranca (tipo, chave_hash, criado_em);

CREATE TABLE planos_assinatura (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	slug VARCHAR(50) NOT NULL, 
	nome VARCHAR(100) NOT NULL, 
	publico_alvo VARCHAR(20) NOT NULL, 
	preco_mensal NUMERIC(12, 2) NOT NULL, 
	recursos JSON, 
	ativo BOOL NOT NULL DEFAULT '1', 
	criado_em DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id)
) ENGINE=InnoDB;
CREATE UNIQUE INDEX ix_planos_assinatura_slug ON planos_assinatura (slug);

CREATE TABLE usuarios (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	nome VARCHAR(120) NOT NULL, 
	email VARCHAR(160) NOT NULL, 
	senha_hash VARCHAR(255) NOT NULL, 
	papel VARCHAR(20) NOT NULL DEFAULT 'usuario', 
	plano VARCHAR(30) NOT NULL DEFAULT 'gratuito', 
	ativo BOOL NOT NULL DEFAULT '1', 
	email_verificado_em DATETIME, 
	ultimo_login_em DATETIME, 
	criado_em DATETIME NOT NULL DEFAULT now(), 
	atualizado_em DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id)
) ENGINE=InnoDB;
CREATE UNIQUE INDEX ix_usuarios_email ON usuarios (email);
CREATE INDEX ix_usuarios_id ON usuarios (id);
CREATE INDEX ix_usuarios_papel ON usuarios (papel);

CREATE TABLE assinaturas_usuario (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	usuario_id INTEGER NOT NULL, 
	plano_id INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL DEFAULT 'ativa', 
	provedor VARCHAR(40), 
	id_externo VARCHAR(120), 
	iniciado_em DATETIME NOT NULL DEFAULT now(), 
	termina_em DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE, 
	FOREIGN KEY(plano_id) REFERENCES planos_assinatura (id) ON DELETE RESTRICT, 
	UNIQUE (id_externo)
) ENGINE=InnoDB;
CREATE INDEX ix_assinaturas_usuario_usuario_id ON assinaturas_usuario (usuario_id);

CREATE TABLE auditoria_admin (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	admin_usuario_id INTEGER, 
	acao VARCHAR(80) NOT NULL, 
	entidade VARCHAR(60) NOT NULL, 
	entidade_id VARCHAR(80), 
	detalhes JSON, 
	criado_em DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(admin_usuario_id) REFERENCES usuarios (id) ON DELETE SET NULL
) ENGINE=InnoDB;
CREATE INDEX ix_auditoria_admin_acao ON auditoria_admin (acao);
CREATE INDEX ix_auditoria_admin_admin_usuario_id ON auditoria_admin (admin_usuario_id);
CREATE INDEX ix_auditoria_admin_criado_em ON auditoria_admin (criado_em);
CREATE INDEX ix_auditoria_admin_entidade ON auditoria_admin (entidade);
CREATE INDEX ix_auditoria_admin_entidade_id_criado ON auditoria_admin (entidade, entidade_id, criado_em);

CREATE TABLE churrascos (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	usuario_id INTEGER, 
	nome VARCHAR(150), 
	chave_cliente VARCHAR(64), 
	status VARCHAR(20) NOT NULL DEFAULT 'rascunho', 
	data_evento DATETIME, 
	tipo_evento VARCHAR(60) NOT NULL, 
	duracao_horas FLOAT NOT NULL, 
	perfil_consumo VARCHAR(20) NOT NULL, 
	perfil_personalizado JSON, 
	adultos INTEGER, 
	adultos_bebem_alcool INTEGER, 
	homens INTEGER NOT NULL, 
	mulheres INTEGER NOT NULL, 
	criancas INTEGER NOT NULL, 
	homens_bebem_alcool INTEGER NOT NULL, 
	mulheres_bebem_alcool INTEGER NOT NULL, 
	vegetarianos INTEGER NOT NULL DEFAULT '0', 
	veganos INTEGER NOT NULL DEFAULT '0', 
	sem_carne_bovina INTEGER NOT NULL DEFAULT '0', 
	sem_carne_suina INTEGER NOT NULL DEFAULT '0', 
	intolerantes_lactose INTEGER NOT NULL DEFAULT '0', 
	alergias TEXT, 
	outras_restricoes TEXT, 
	orcamento_maximo NUMERIC(12, 2), 
	dividir_entre INTEGER, 
	carne_total_kg NUMERIC(12, 3), 
	carvao_ativo BOOL NOT NULL, 
	gelo_ativo BOOL NOT NULL, 
	carvao_necessario_kg NUMERIC(12, 3), 
	carvao_compra_kg NUMERIC(12, 3), 
	custo_total_estimado NUMERIC(12, 2), 
	custo_por_pessoa NUMERIC(12, 2), 
	criado_em DATETIME NOT NULL DEFAULT now(), 
	atualizado_em DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id) ON DELETE SET NULL
) ENGINE=InnoDB;
CREATE UNIQUE INDEX ix_churrascos_chave_cliente ON churrascos (chave_cliente);
CREATE INDEX ix_churrascos_data_evento ON churrascos (data_evento);
CREATE INDEX ix_churrascos_id ON churrascos (id);
CREATE INDEX ix_churrascos_status ON churrascos (status);
CREATE INDEX ix_churrascos_usuario_id ON churrascos (usuario_id);

CREATE TABLE consentimentos_usuario (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	usuario_id INTEGER NOT NULL, 
	tipo VARCHAR(30) NOT NULL, 
	versao VARCHAR(30) NOT NULL, 
	concedido BOOL NOT NULL DEFAULT '1', 
	origem VARCHAR(40) NOT NULL DEFAULT 'cadastro', 
	criado_em DATETIME NOT NULL DEFAULT now(), 
	atualizado_em DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_consentimento_usuario_tipo_versao UNIQUE (usuario_id, tipo, versao), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE INDEX ix_consentimentos_usuario_tipo ON consentimentos_usuario (tipo);
CREATE INDEX ix_consentimentos_usuario_usuario_id ON consentimentos_usuario (usuario_id);

CREATE TABLE estabelecimentos (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	usuario_responsavel_id INTEGER, 
	slug VARCHAR(170) NOT NULL, 
	nome VARCHAR(150) NOT NULL, 
	tipo VARCHAR(60) NOT NULL, 
	endereco VARCHAR(255), 
	logradouro VARCHAR(160), 
	numero VARCHAR(30), 
	bairro VARCHAR(100), 
	cidade VARCHAR(100), 
	estado VARCHAR(2), 
	cep VARCHAR(12), 
	latitude FLOAT, 
	longitude FLOAT, 
	telefone VARCHAR(30), 
	site VARCHAR(255), 
	horario_funcionamento VARCHAR(120), 
	google_place_id VARCHAR(255), 
	avaliacao NUMERIC(3, 2), 
	quantidade_avaliacoes INTEGER, 
	parceiro_verificado BOOL NOT NULL DEFAULT '0', 
	ativo BOOL NOT NULL DEFAULT '1', 
	PRIMARY KEY (id), 
	FOREIGN KEY(usuario_responsavel_id) REFERENCES usuarios (id) ON DELETE SET NULL
) ENGINE=InnoDB;
CREATE INDEX ix_estabelecimentos_cidade ON estabelecimentos (cidade);
CREATE INDEX ix_estabelecimentos_estado ON estabelecimentos (estado);
CREATE UNIQUE INDEX ix_estabelecimentos_google_place_id ON estabelecimentos (google_place_id);
CREATE INDEX ix_estabelecimentos_id ON estabelecimentos (id);
CREATE INDEX ix_estabelecimentos_latitude ON estabelecimentos (latitude);
CREATE INDEX ix_estabelecimentos_longitude ON estabelecimentos (longitude);
CREATE UNIQUE INDEX ix_estabelecimentos_slug ON estabelecimentos (slug);
CREATE INDEX ix_estabelecimentos_usuario_responsavel_id ON estabelecimentos (usuario_responsavel_id);

CREATE TABLE produtos (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	categoria_id INTEGER NOT NULL, 
	produto_pai_id INTEGER, 
	tipo_produto VARCHAR(20) NOT NULL DEFAULT 'generico', 
	slug VARCHAR(140) NOT NULL, 
	nome VARCHAR(120) NOT NULL, 
	marca VARCHAR(100), 
	variante VARCHAR(120), 
	fabricante VARCHAR(120), 
	ean VARCHAR(32), 
	sku VARCHAR(80), 
	unidade_consumo VARCHAR(30) NOT NULL, 
	unidade_venda VARCHAR(30) NOT NULL, 
	venda_fracionada BOOL NOT NULL, 
	incremento_venda NUMERIC(12, 3), 
	quantidade_embalagem NUMERIC(12, 3), 
	unidade_embalagem VARCHAR(30), 
	ativo BOOL NOT NULL DEFAULT '1', 
	imagem_url VARCHAR(255), 
	descricao TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(categoria_id) REFERENCES categorias (id) ON DELETE RESTRICT, 
	FOREIGN KEY(produto_pai_id) REFERENCES produtos (id) ON DELETE SET NULL
) ENGINE=InnoDB;
CREATE INDEX ix_produtos_categoria_id ON produtos (categoria_id);
CREATE UNIQUE INDEX ix_produtos_ean ON produtos (ean);
CREATE INDEX ix_produtos_id ON produtos (id);
CREATE INDEX ix_produtos_marca ON produtos (marca);
CREATE INDEX ix_produtos_produto_pai_id ON produtos (produto_pai_id);
CREATE INDEX ix_produtos_sku ON produtos (sku);
CREATE UNIQUE INDEX ix_produtos_slug ON produtos (slug);
CREATE INDEX ix_produtos_tipo_produto ON produtos (tipo_produto);

CREATE TABLE sessoes_usuario (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	usuario_id INTEGER NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	csrf_hash VARCHAR(64) NOT NULL, 
	criado_em DATETIME NOT NULL DEFAULT now(), 
	ultimo_uso_em DATETIME NOT NULL DEFAULT now(), 
	expira_em DATETIME NOT NULL, 
	revogada BOOL NOT NULL, 
	user_agent VARCHAR(255), 
	ip_hash VARCHAR(64), 
	PRIMARY KEY (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE INDEX ix_sessoes_usuario_expira_em ON sessoes_usuario (expira_em);
CREATE UNIQUE INDEX ix_sessoes_usuario_token_hash ON sessoes_usuario (token_hash);
CREATE INDEX ix_sessoes_usuario_usuario_id ON sessoes_usuario (usuario_id);

CREATE TABLE tokens_usuario (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	usuario_id INTEGER NOT NULL, 
	tipo VARCHAR(30) NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	criado_em DATETIME NOT NULL DEFAULT now(), 
	expira_em DATETIME NOT NULL, 
	usado_em DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE INDEX ix_tokens_usuario_tipo ON tokens_usuario (tipo);
CREATE UNIQUE INDEX ix_tokens_usuario_token_hash ON tokens_usuario (token_hash);
CREATE INDEX ix_tokens_usuario_usuario_id ON tokens_usuario (usuario_id);

CREATE TABLE convites_churrasco (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	churrasco_id INTEGER NOT NULL, 
	codigo VARCHAR(32) NOT NULL, 
	ativo BOOL NOT NULL, 
	criado_em DATETIME NOT NULL DEFAULT now(), 
	expira_em DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(churrasco_id) REFERENCES churrascos (id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE UNIQUE INDEX ix_convites_churrasco_churrasco_id ON convites_churrasco (churrasco_id);
CREATE UNIQUE INDEX ix_convites_churrasco_codigo ON convites_churrasco (codigo);

CREATE TABLE lista_compras (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	churrasco_id INTEGER NOT NULL, 
	criado_em DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(churrasco_id) REFERENCES churrascos (id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE UNIQUE INDEX ix_lista_compras_churrasco_id ON lista_compras (churrasco_id);
CREATE INDEX ix_lista_compras_id ON lista_compras (id);

CREATE TABLE metricas_estabelecimentos (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	estabelecimento_id INTEGER NOT NULL, 
	tipo VARCHAR(20) NOT NULL, 
	contexto VARCHAR(40) NOT NULL DEFAULT 'onde_comprar', 
	criado_em DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT ck_metricas_estabelecimentos_tipo CHECK (tipo IN ('visualizacao','clique')), 
	FOREIGN KEY(estabelecimento_id) REFERENCES estabelecimentos (id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE INDEX ix_metricas_estabelecimentos_criado_em ON metricas_estabelecimentos (criado_em);
CREATE INDEX ix_metricas_estabelecimentos_estabelecimento_id ON metricas_estabelecimentos (estabelecimento_id);
CREATE INDEX ix_metricas_estabelecimentos_estabelecimento_tipo_criado ON metricas_estabelecimentos (estabelecimento_id, tipo, criado_em);
CREATE INDEX ix_metricas_estabelecimentos_id ON metricas_estabelecimentos (id);
CREATE INDEX ix_metricas_estabelecimentos_tipo ON metricas_estabelecimentos (tipo);

CREATE TABLE precos (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	produto_id INTEGER NOT NULL, 
	estabelecimento_id INTEGER NOT NULL, 
	criado_por_usuario_id INTEGER, 
	preco NUMERIC(12, 2) NOT NULL, 
	preco_original NUMERIC(12, 2), 
	moeda VARCHAR(3) NOT NULL DEFAULT 'BRL', 
	fonte VARCHAR(255), 
	origem VARCHAR(40) NOT NULL DEFAULT 'manual', 
	estoque_status VARCHAR(30) NOT NULL DEFAULT 'disponivel', 
	disponivel BOOL NOT NULL DEFAULT '1', 
	inicio_validade DATETIME, 
	fim_validade DATETIME, 
	coletado_em DATETIME NOT NULL DEFAULT now(), 
	data_atualizacao DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(produto_id) REFERENCES produtos (id) ON DELETE CASCADE, 
	FOREIGN KEY(estabelecimento_id) REFERENCES estabelecimentos (id) ON DELETE CASCADE, 
	FOREIGN KEY(criado_por_usuario_id) REFERENCES usuarios (id) ON DELETE SET NULL
) ENGINE=InnoDB;
CREATE INDEX ix_precos_criado_por_usuario_id ON precos (criado_por_usuario_id);
CREATE INDEX ix_precos_estabelecimento_id ON precos (estabelecimento_id);
CREATE INDEX ix_precos_id ON precos (id);
CREATE INDEX ix_precos_produto_id ON precos (produto_id);

CREATE TABLE churrasco_bebidas (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	churrasco_id INTEGER NOT NULL, 
	produto_id INTEGER, 
	preco_id INTEGER, 
	produto_slug VARCHAR(140), 
	nome_item VARCHAR(120) NOT NULL, 
	quantidade_necessaria NUMERIC(12, 3) NOT NULL, 
	unidade_necessaria VARCHAR(30) NOT NULL, 
	quantidade_compra NUMERIC(12, 3) NOT NULL, 
	unidade_compra VARCHAR(30) NOT NULL, 
	quantidade_embalagens INTEGER, 
	tamanho_embalagem NUMERIC(12, 3), 
	unidade_embalagem VARCHAR(30), 
	unidade_venda VARCHAR(30) NOT NULL, 
	preco_unitario NUMERIC(12, 2), 
	subtotal_estimado NUMERIC(12, 2), 
	estabelecimento_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(churrasco_id) REFERENCES churrascos (id) ON DELETE CASCADE, 
	FOREIGN KEY(produto_id) REFERENCES produtos (id) ON DELETE SET NULL, 
	FOREIGN KEY(preco_id) REFERENCES precos (id) ON DELETE SET NULL, 
	FOREIGN KEY(estabelecimento_id) REFERENCES estabelecimentos (id) ON DELETE SET NULL
) ENGINE=InnoDB;
CREATE INDEX ix_churrasco_bebidas_churrasco_id ON churrasco_bebidas (churrasco_id);
CREATE INDEX ix_churrasco_bebidas_id ON churrasco_bebidas (id);
CREATE INDEX ix_churrasco_bebidas_produto_id ON churrasco_bebidas (produto_id);
CREATE INDEX ix_churrasco_bebidas_produto_slug ON churrasco_bebidas (produto_slug);

CREATE TABLE churrasco_carnes (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	churrasco_id INTEGER NOT NULL, 
	percentual NUMERIC(6, 2) NOT NULL, 
	produto_id INTEGER, 
	preco_id INTEGER, 
	produto_slug VARCHAR(140), 
	nome_item VARCHAR(120) NOT NULL, 
	quantidade_necessaria NUMERIC(12, 3) NOT NULL, 
	unidade_necessaria VARCHAR(30) NOT NULL, 
	quantidade_compra NUMERIC(12, 3) NOT NULL, 
	unidade_compra VARCHAR(30) NOT NULL, 
	quantidade_embalagens INTEGER, 
	tamanho_embalagem NUMERIC(12, 3), 
	unidade_embalagem VARCHAR(30), 
	unidade_venda VARCHAR(30) NOT NULL, 
	preco_unitario NUMERIC(12, 2), 
	subtotal_estimado NUMERIC(12, 2), 
	estabelecimento_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(churrasco_id) REFERENCES churrascos (id) ON DELETE CASCADE, 
	FOREIGN KEY(produto_id) REFERENCES produtos (id) ON DELETE SET NULL, 
	FOREIGN KEY(preco_id) REFERENCES precos (id) ON DELETE SET NULL, 
	FOREIGN KEY(estabelecimento_id) REFERENCES estabelecimentos (id) ON DELETE SET NULL
) ENGINE=InnoDB;
CREATE INDEX ix_churrasco_carnes_churrasco_id ON churrasco_carnes (churrasco_id);
CREATE INDEX ix_churrasco_carnes_id ON churrasco_carnes (id);
CREATE INDEX ix_churrasco_carnes_produto_id ON churrasco_carnes (produto_id);
CREATE INDEX ix_churrasco_carnes_produto_slug ON churrasco_carnes (produto_slug);

CREATE TABLE churrasco_extras (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	churrasco_id INTEGER NOT NULL, 
	tipo VARCHAR(30) NOT NULL, 
	produto_id INTEGER, 
	preco_id INTEGER, 
	produto_slug VARCHAR(140), 
	nome_item VARCHAR(120) NOT NULL, 
	quantidade_necessaria NUMERIC(12, 3) NOT NULL, 
	unidade_necessaria VARCHAR(30) NOT NULL, 
	quantidade_compra NUMERIC(12, 3) NOT NULL, 
	unidade_compra VARCHAR(30) NOT NULL, 
	quantidade_embalagens INTEGER, 
	tamanho_embalagem NUMERIC(12, 3), 
	unidade_embalagem VARCHAR(30), 
	unidade_venda VARCHAR(30) NOT NULL, 
	preco_unitario NUMERIC(12, 2), 
	subtotal_estimado NUMERIC(12, 2), 
	estabelecimento_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(churrasco_id) REFERENCES churrascos (id) ON DELETE CASCADE, 
	FOREIGN KEY(produto_id) REFERENCES produtos (id) ON DELETE SET NULL, 
	FOREIGN KEY(preco_id) REFERENCES precos (id) ON DELETE SET NULL, 
	FOREIGN KEY(estabelecimento_id) REFERENCES estabelecimentos (id) ON DELETE SET NULL
) ENGINE=InnoDB;
CREATE INDEX ix_churrasco_extras_churrasco_id ON churrasco_extras (churrasco_id);
CREATE INDEX ix_churrasco_extras_id ON churrasco_extras (id);
CREATE INDEX ix_churrasco_extras_produto_id ON churrasco_extras (produto_id);
CREATE INDEX ix_churrasco_extras_produto_slug ON churrasco_extras (produto_slug);

CREATE TABLE lista_compras_itens (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	lista_compras_id INTEGER NOT NULL, 
	produto_id INTEGER, 
	estabelecimento_compra_id INTEGER, 
	descricao VARCHAR(150) NOT NULL, 
	quantidade NUMERIC(12, 3) NOT NULL, 
	unidade VARCHAR(30) NOT NULL, 
	quantidade_embalagens INTEGER, 
	unidade_venda VARCHAR(30) NOT NULL, 
	categoria VARCHAR(30) NOT NULL, 
	preco_unitario NUMERIC(12, 2), 
	subtotal_estimado NUMERIC(12, 2), 
	valor_pago_total NUMERIC(12, 2), 
	comprado BOOL NOT NULL DEFAULT '0', 
	comprado_em DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(lista_compras_id) REFERENCES lista_compras (id) ON DELETE CASCADE, 
	FOREIGN KEY(produto_id) REFERENCES produtos (id) ON DELETE SET NULL, 
	FOREIGN KEY(estabelecimento_compra_id) REFERENCES estabelecimentos (id) ON DELETE SET NULL
) ENGINE=InnoDB;
CREATE INDEX ix_lista_compras_itens_id ON lista_compras_itens (id);
CREATE INDEX ix_lista_compras_itens_lista_compras_id ON lista_compras_itens (lista_compras_id);

CREATE TABLE respostas_convite (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	convite_id INTEGER NOT NULL, 
	chave_resposta VARCHAR(48) NOT NULL, 
	nome VARCHAR(120) NOT NULL, 
	resposta VARCHAR(20) NOT NULL, 
	tipo_convidado VARCHAR(20) NOT NULL, 
	consome_alcool BOOL NOT NULL, 
	vegetariano BOOL NOT NULL, 
	vegano BOOL NOT NULL, 
	sem_carne_bovina BOOL NOT NULL, 
	sem_carne_suina BOOL NOT NULL, 
	intolerante_lactose BOOL NOT NULL, 
	alergias TEXT, 
	outras_restricoes TEXT, 
	criado_em DATETIME NOT NULL DEFAULT now(), 
	atualizado_em DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(convite_id) REFERENCES convites_churrasco (id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE UNIQUE INDEX ix_respostas_convite_chave_resposta ON respostas_convite (chave_resposta);
CREATE INDEX ix_respostas_convite_convite_id ON respostas_convite (convite_id);
CREATE INDEX ix_respostas_convite_resposta ON respostas_convite (resposta);
