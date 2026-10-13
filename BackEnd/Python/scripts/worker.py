"""python -m scripts.worker [--once]. Um processo no piloto, múltiplos no MySQL."""
import argparse
import signal
import threading
from config import validar_configuracao_producao, settings
from database.connection import SessionLocal
from services.outbox import heartbeat, processar_um
from services.retencao_dados import executar_retencao
import time
from services.observabilidade import configurar_logs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    validar_configuracao_producao()
    configurar_logs()
    if not settings.DATA_ENCRYPTION_KEY:
        raise SystemExit("Configure DATA_ENCRYPTION_KEY compartilhada entre API e worker.")
    parar = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: parar.set())
    signal.signal(signal.SIGINT, lambda *_: parar.set())
    ultima_retencao = 0.0
    while not parar.is_set():
        with SessionLocal() as db:
            heartbeat(db)
            if time.monotonic() - ultima_retencao > 3600:
                executar_retencao(db)
                ultima_retencao = time.monotonic()
            for _ in range(25):
                if not processar_um(db):
                    break
                heartbeat(db)
        if args.once:
            break
        parar.wait(5)


if __name__ == "__main__":
    main()
