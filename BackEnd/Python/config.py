"""Configuração central do ChurrasPlan.

As regras abaixo são heurísticas de planejamento e ficam deliberadamente
centralizadas. A aplicação mantém três conceitos separados:
necessidade física, compra comercial e custo da oferta.
"""
import os
from functools import lru_cache
from urllib.parse import quote_plus

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Settings:
    APP_NAME: str = "ChurrasPlan API"
    APP_ENV: str = os.getenv("APP_ENV", "development")
    DB_HOST: str = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT: str = os.getenv("DB_PORT", "3306")
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "churrasplan")
    DATABASE_URL_OVERRIDE: str | None = os.getenv("DATABASE_URL")
    AUTO_CREATE_SCHEMA: bool = os.getenv("AUTO_CREATE_SCHEMA", "false").lower() in {"1", "true", "yes"}
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "1800"))

    @property
    def DATABASE_URL(self) -> str:
        if self.DATABASE_URL_OVERRIDE:
            return self.DATABASE_URL_OVERRIDE
        usuario = quote_plus(self.DB_USER)
        senha = quote_plus(self.DB_PASSWORD)
        return (
            f"mysql+pymysql://{usuario}:{senha}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    CORS_ORIGINS: list[str] = [
        origem.strip() for origem in os.getenv(
            "CORS_ORIGINS", "http://127.0.0.1:5500,http://localhost:5500"
        ).split(",") if origem.strip()
    ]

    # Autenticação/sessões. Tokens nunca são armazenados em texto puro.
    SESSION_COOKIE_NAME: str = os.getenv("SESSION_COOKIE_NAME", "churrasplan_session")
    CSRF_COOKIE_NAME: str = os.getenv("CSRF_COOKIE_NAME", "churrasplan_csrf")
    SESSION_DAYS: int = int(os.getenv("SESSION_DAYS", "30"))
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "true" if APP_ENV == "production" else "false").lower() in {"1", "true", "yes"}
    REQUIRE_EMAIL_VERIFICATION: bool = os.getenv("REQUIRE_EMAIL_VERIFICATION", "true" if APP_ENV == "production" else "false").lower() in {"1", "true", "yes"}
    PUBLIC_APP_URL: str = os.getenv("PUBLIC_APP_URL", "http://127.0.0.1:5500")

    # SMTP é opcional em desenvolvimento. Em produção, configure um provedor
    # para verificação de e-mail e recuperação de senha.
    SMTP_HOST: str | None = os.getenv("SMTP_HOST")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str | None = os.getenv("SMTP_USER")
    SMTP_PASSWORD: str | None = os.getenv("SMTP_PASSWORD")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "ChurrasPlan <no-reply@churrasplan.local>")
    SMTP_TLS: bool = os.getenv("SMTP_TLS", "true").lower() in {"1", "true", "yes"}

    # Integração opcional Google Maps/Places. A chave de servidor e a chave
    # JavaScript podem ser separadas e restritas no Google Cloud.
    GOOGLE_PLACES_API_KEY: str | None = os.getenv("GOOGLE_PLACES_API_KEY")
    GOOGLE_MAPS_JS_API_KEY: str | None = os.getenv("GOOGLE_MAPS_JS_API_KEY")
    GOOGLE_MAP_ID: str | None = os.getenv("GOOGLE_MAP_ID")
    GOOGLE_PLACES_ENABLED: bool = os.getenv("GOOGLE_PLACES_ENABLED", "false").lower() in {"1", "true", "yes"}

    # Hardening HTTP/rede. Em produção, use o backend atrás de um proxy reverso
    # que encerre TLS e encaminhe X-Forwarded-* apenas pela rede interna.
    TRUSTED_HOSTS: list[str] = [
        host.strip() for host in os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()
    ]
    FORCE_HTTPS: bool = os.getenv("FORCE_HTTPS", "true" if APP_ENV == "production" else "false").lower() in {"1", "true", "yes"}
    HSTS_SECONDS: int = int(os.getenv("HSTS_SECONDS", "31536000"))
    MAX_REQUEST_BODY_BYTES: int = int(os.getenv("MAX_REQUEST_BODY_BYTES", str(2 * 1024 * 1024)))
    TRUST_PROXY_HEADERS: bool = os.getenv("TRUST_PROXY_HEADERS", "false").lower() in {"1", "true", "yes"}

    # Rate limiting persistido em MySQL. A chave é sempre um HMAC, nunca o IP puro.
    SECURITY_PEPPER: str = os.getenv("SECURITY_PEPPER", "dev-only-change-me")
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in {"1", "true", "yes"}
    RATE_LIMIT_LOGIN_ATTEMPTS: int = int(os.getenv("RATE_LIMIT_LOGIN_ATTEMPTS", "10"))
    RATE_LIMIT_REGISTER_ATTEMPTS: int = int(os.getenv("RATE_LIMIT_REGISTER_ATTEMPTS", "8"))
    RATE_LIMIT_PUBLIC_ATTEMPTS: int = int(os.getenv("RATE_LIMIT_PUBLIC_ATTEMPTS", "30"))
    RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "900"))
    SECURITY_EVENT_RETENTION_DAYS: int = int(os.getenv("SECURITY_EVENT_RETENTION_DAYS", "7"))

    # Documentos legais versionados. Mudanças materiais devem gerar nova versão.
    TERMS_VERSION: str = os.getenv("TERMS_VERSION", "2026-09-18")
    PRIVACY_VERSION: str = os.getenv("PRIVACY_VERSION", "2026-09-21")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


FAIXAS_DURACAO_CARNE = [
    (3.0, 0.90),
    (5.0, 1.00),
    (7.0, 1.10),
    (9.0, 1.20),
    (float("inf"), 1.30),
]

FAIXAS_DURACAO_GELO = [
    (3.0, 0.80),
    (5.0, 1.00),
    (7.0, 1.20),
    (float("inf"), 1.40),
]

# O tipo de evento agora é funcional, e não apenas metadado. Os fatores são
# moderados para não duplicar o efeito da duração.
FATORES_TIPO_EVENTO = {
    "almoco": 1.00,
    "jantar": 0.95,
    "aniversario": 0.95,
    "confraternizacao_empresa": 0.90,
    "evento_prolongado": 1.10,
    "outro": 1.00,
}

REGRAS_PADRAO = {
    "perfil": {"fatores": {"leve": 0.85, "normal": 1.00, "alto": 1.20}},
    "evento": {"fatores": FATORES_TIPO_EVENTO},
    "carne": {
        # Base prática de planejamento para alimento cru antes do preparo.
        "kg_por_adulto_base": 0.40,
        "kg_por_crianca_base": 0.20,
        "faixas_duracao": FAIXAS_DURACAO_CARNE,
    },
    "bebida_nao_alcoolica": {
        "litros_por_pessoa_base": {
            "agua": 0.75,
            "refrigerante": 0.50,
            "suco": 0.30,
        },
    },
    "bebida_alcoolica": {
        # Parâmetro logístico, não recomendação de consumo.
        "litros_por_consumidor_hora": 0.45,
    },
    "gelo": {
        "kg_por_pessoa_base": 0.50,
        "faixas_duracao": FAIXAS_DURACAO_GELO,
    },
    "carvao": {"kg_por_kg_carne": 0.50},
    "extras": {
        "sal_grosso_kg_por_kg_carne": 0.02,
        "copos_por_pessoa": 2.0,
        "pratos_por_pessoa": 1.0,
        "talheres_por_pessoa": 1.0,
        "guardanapos_por_pessoa": 4,
        "sacos_lixo_a_cada_pessoas": 10,
        "acendedor_unidades": 1,
        "fosforo_isqueiro_unidades": 1,
        "papel_toalha_rolos_a_cada_pessoas": 15,
        "papel_aluminio_rolos_a_cada_pessoas": 20,
        "palitos_unidades_por_pessoa": 4,
        "margem_seguranca": 1.10,
    },
    "acompanhamentos": {
        "pao_de_alho_unidades_por_pessoa": 0.75,
        "farofa_g_por_pessoa": 60,
        "vinagrete_g_por_pessoa": 80,
        "queijo_coalho_g_por_pessoa": 60,
        "maionese_g_por_pessoa": 100,
        "salada_g_por_pessoa": 80,
        "arroz_g_por_pessoa": 80,
        "molhos_ml_por_pessoa": 20,
        "pao_g_por_pessoa": 50,
    },
    "personalizado_base": {
        "carne_adulto_kg": 0.40,
        "carne_crianca_kg": 0.20,
        "agua_litros_pessoa": 0.75,
        "refrigerante_litros_pessoa": 0.50,
        "suco_litros_pessoa": 0.30,
        "cerveja_litros_consumidor_hora": 0.45,
        "gelo_kg_pessoa": 0.50,
        "carvao_kg_por_kg_carne": 0.50,
    },
}

LIMITES = {
    "pessoas_min": 0,
    "pessoas_max": 500,
    "duracao_horas_min": 1,
    "duracao_horas_max": 48,
    "percentual_min": 0,
    "percentual_max": 100,
    "tolerancia_soma_percentual": 0.01,
}

# Catálogo comercial de fallback. Em produção, o banco é a fonte preferencial;
# estes dados permitem preview e bootstrapping antes do catálogo ser carregado.
# preço nunca aparece aqui: preço sempre vem de uma oferta cadastrada.
CATALOGO_PRODUTOS_PADRAO = {
    # Carnes / itens do seletor de carnes: venda fracionada por kg.
    **{
        slug: {
            "slug": slug, "nome": nome, "categoria": "carne",
            "unidade_consumo": "kg", "unidade_venda": "kg",
            "venda_fracionada": True, "incremento_venda": 0.10,
            "quantidade_embalagem": None, "unidade_embalagem": None,
        }
        for slug, nome in [
            ("picanha", "Picanha"), ("picanha-suina", "Picanha suína"),
            ("contra-file", "Contra-filé"), ("alcatra", "Alcatra"),
            ("fraldinha", "Fraldinha"), ("maminha", "Maminha"),
            ("acem", "Acém"), ("costela", "Costela"),
            ("costelinha-porco", "Costelinha de porco"), ("cupim", "Cupim"),
            ("linguica", "Linguiça"), ("lombo", "Lombo"),
            ("bisteca", "Bisteca"), ("frango", "Frango"),
            ("asinha-frango", "Asinha de frango"), ("coracao", "Coração"),
            ("queijo-coalho-churrasco", "Queijo coalho"), ("pao-alho-churrasco", "Pão de alho"),
            ("bife-ancho", "Bife Ancho"), ("bife-chorizo", "Bife de Chorizo"),
            ("prime-rib", "Prime Rib"), ("short-rib", "Short Rib"),
            ("file-mignon", "Filé Mignon"),
        ]
    },
    "carvao": {"slug": "carvao", "nome": "Carvão", "categoria": "extra", "unidade_consumo": "kg", "unidade_venda": "saco", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 3.0, "unidade_embalagem": "kg"},
    "agua": {"slug": "agua", "nome": "Água", "categoria": "bebida", "unidade_consumo": "litro", "unidade_venda": "garrafa", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 1.5, "unidade_embalagem": "litro"},
    "refrigerante": {"slug": "refrigerante", "nome": "Refrigerante", "categoria": "bebida", "unidade_consumo": "litro", "unidade_venda": "garrafa", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 2.0, "unidade_embalagem": "litro"},
    "suco": {"slug": "suco", "nome": "Suco", "categoria": "bebida", "unidade_consumo": "litro", "unidade_venda": "caixa", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 1.0, "unidade_embalagem": "litro"},
    "cerveja": {"slug": "cerveja", "nome": "Cerveja", "categoria": "bebida", "unidade_consumo": "litro", "unidade_venda": "lata", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 0.35, "unidade_embalagem": "litro"},
    "gelo": {"slug": "gelo", "nome": "Gelo", "categoria": "bebida", "unidade_consumo": "kg", "unidade_venda": "saco", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 5.0, "unidade_embalagem": "kg"},
    "sal-grosso": {"slug": "sal-grosso", "nome": "Sal grosso", "categoria": "extra", "unidade_consumo": "kg", "unidade_venda": "pacote", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 1.0, "unidade_embalagem": "kg"},
    "acendedor": {"slug": "acendedor", "nome": "Acendedor", "categoria": "extra", "unidade_consumo": "unidade", "unidade_venda": "unidade", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 1.0, "unidade_embalagem": "unidade"},
    "fosforo-isqueiro": {"slug": "fosforo-isqueiro", "nome": "Fósforo / isqueiro", "categoria": "extra", "unidade_consumo": "unidade", "unidade_venda": "unidade", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 1.0, "unidade_embalagem": "unidade"},
    "copos": {"slug": "copos", "nome": "Copos", "categoria": "extra", "unidade_consumo": "unidade", "unidade_venda": "pacote", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 50.0, "unidade_embalagem": "unidade"},
    "pratos": {"slug": "pratos", "nome": "Pratos", "categoria": "extra", "unidade_consumo": "unidade", "unidade_venda": "pacote", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 10.0, "unidade_embalagem": "unidade"},
    "talheres": {"slug": "talheres", "nome": "Talheres", "categoria": "extra", "unidade_consumo": "unidade", "unidade_venda": "pacote", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 20.0, "unidade_embalagem": "unidade"},
    "guardanapos": {"slug": "guardanapos", "nome": "Guardanapos", "categoria": "extra", "unidade_consumo": "unidade", "unidade_venda": "pacote", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 50.0, "unidade_embalagem": "unidade"},
    "sacos-lixo": {"slug": "sacos-lixo", "nome": "Sacos de lixo", "categoria": "extra", "unidade_consumo": "unidade", "unidade_venda": "pacote", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 10.0, "unidade_embalagem": "unidade"},
    "papel-toalha": {"slug": "papel-toalha", "nome": "Papel toalha", "categoria": "extra", "unidade_consumo": "rolo", "unidade_venda": "pacote", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 2.0, "unidade_embalagem": "rolo"},
    "papel-aluminio": {"slug": "papel-aluminio", "nome": "Papel alumínio", "categoria": "extra", "unidade_consumo": "rolo", "unidade_venda": "rolo", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 1.0, "unidade_embalagem": "rolo"},
    "palitos": {"slug": "palitos", "nome": "Palitos", "categoria": "extra", "unidade_consumo": "unidade", "unidade_venda": "caixa", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 100.0, "unidade_embalagem": "unidade"},
    "pao-de-alho": {"slug": "pao-de-alho", "nome": "Pão de alho", "categoria": "acompanhamento", "unidade_consumo": "unidade", "unidade_venda": "pacote", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 5.0, "unidade_embalagem": "unidade"},
    "farofa": {"slug": "farofa", "nome": "Farofa", "categoria": "acompanhamento", "unidade_consumo": "kg", "unidade_venda": "pacote", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 0.5, "unidade_embalagem": "kg"},
    "vinagrete": {"slug": "vinagrete", "nome": "Vinagrete", "categoria": "acompanhamento", "unidade_consumo": "kg", "unidade_venda": "kg", "venda_fracionada": True, "incremento_venda": 0.1, "quantidade_embalagem": None, "unidade_embalagem": None},
    "queijo-coalho": {"slug": "queijo-coalho", "nome": "Queijo coalho", "categoria": "acompanhamento", "unidade_consumo": "kg", "unidade_venda": "pacote", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 0.5, "unidade_embalagem": "kg"},
    "maionese": {"slug": "maionese", "nome": "Maionese", "categoria": "acompanhamento", "unidade_consumo": "kg", "unidade_venda": "pote", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 0.5, "unidade_embalagem": "kg"},
    "salada": {"slug": "salada", "nome": "Salada", "categoria": "acompanhamento", "unidade_consumo": "kg", "unidade_venda": "kg", "venda_fracionada": True, "incremento_venda": 0.1, "quantidade_embalagem": None, "unidade_embalagem": None},
    "arroz": {"slug": "arroz", "nome": "Arroz", "categoria": "acompanhamento", "unidade_consumo": "kg", "unidade_venda": "pacote", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 1.0, "unidade_embalagem": "kg"},
    "molhos": {"slug": "molhos", "nome": "Molhos", "categoria": "acompanhamento", "unidade_consumo": "litro", "unidade_venda": "frasco", "venda_fracionada": False, "incremento_venda": None, "quantidade_embalagem": 0.25, "unidade_embalagem": "litro"},
    "pao": {"slug": "pao", "nome": "Pão", "categoria": "acompanhamento", "unidade_consumo": "kg", "unidade_venda": "kg", "venda_fracionada": True, "incremento_venda": 0.1, "quantidade_embalagem": None, "unidade_embalagem": None},
}


def validar_configuracao_producao(configuracao: Settings = settings) -> None:
    """Falha cedo em configurações que tornariam um deploy real inseguro/inutilizável."""
    if configuracao.APP_ENV != "production":
        return
    erros: list[str] = []
    if not configuracao.COOKIE_SECURE:
        erros.append("COOKIE_SECURE deve ser true em produção")
    if configuracao.REQUIRE_EMAIL_VERIFICATION and not configuracao.SMTP_HOST:
        erros.append("SMTP_HOST é obrigatório quando a verificação de e-mail está habilitada")
    if not configuracao.PUBLIC_APP_URL.lower().startswith("https://"):
        erros.append("PUBLIC_APP_URL deve usar HTTPS em produção")
    if not configuracao.CORS_ORIGINS or any(origem == "*" for origem in configuracao.CORS_ORIGINS):
        erros.append("CORS_ORIGINS deve listar origens explícitas em produção")
    if configuracao.GOOGLE_PLACES_ENABLED and not configuracao.GOOGLE_PLACES_API_KEY:
        erros.append("GOOGLE_PLACES_API_KEY é obrigatória quando GOOGLE_PLACES_ENABLED=true")
    if configuracao.GOOGLE_PLACES_ENABLED and not configuracao.GOOGLE_MAPS_JS_API_KEY:
        erros.append("GOOGLE_MAPS_JS_API_KEY é obrigatória quando GOOGLE_PLACES_ENABLED=true")
    if configuracao.GOOGLE_MAP_ID and not configuracao.GOOGLE_MAPS_JS_API_KEY:
        erros.append("GOOGLE_MAPS_JS_API_KEY é obrigatória quando GOOGLE_MAP_ID está configurado")
    if not configuracao.TRUSTED_HOSTS or "*" in configuracao.TRUSTED_HOSTS:
        erros.append("TRUSTED_HOSTS deve listar hosts explícitos em produção")
    if len(configuracao.SECURITY_PEPPER) < 32 or configuracao.SECURITY_PEPPER == "dev-only-change-me":
        erros.append("SECURITY_PEPPER deve possuir pelo menos 32 caracteres aleatórios em produção")
    if not configuracao.FORCE_HTTPS:
        erros.append("FORCE_HTTPS deve ser true em produção")
    if not configuracao.DATABASE_URL.lower().startswith("mysql+pymysql://"):
        erros.append("DATABASE_URL deve apontar para MySQL via PyMySQL em produção")
    if not configuracao.DATABASE_URL_OVERRIDE and not configuracao.DB_PASSWORD:
        erros.append("DB_PASSWORD não pode ser vazio em produção")
    if erros:
        raise RuntimeError("Configuração de produção inválida: " + "; ".join(erros))
