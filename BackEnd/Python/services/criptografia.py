"""Cifra autenticada para segredos recuperáveis; senhas usam Argon2."""
from cryptography.fernet import Fernet
from config import settings

_chave_dev = Fernet.generate_key()


def cifra() -> Fernet:
    chave = settings.DATA_ENCRYPTION_KEY.encode() if settings.DATA_ENCRYPTION_KEY else _chave_dev
    if settings.APP_ENV == "production" and not settings.DATA_ENCRYPTION_KEY:
        raise RuntimeError("DATA_ENCRYPTION_KEY ausente")
    return Fernet(chave)


def cifrar(valor: str) -> str:
    return cifra().encrypt(valor.encode()).decode()


def decifrar(valor: str) -> str:
    return cifra().decrypt(valor.encode()).decode()
