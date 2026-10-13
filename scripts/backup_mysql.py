"""Backup gzip/AES-256-GCM; restauração somente em banco isolado e vazio.

BACKUP_ENCRYPTION_KEY: chave base64 de 32 bytes, distinta de DATA_ENCRYPTION_KEY.
Use --retention-days para retenção local. Copie o .cpg para armazenamento independente.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
import zlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MAGIC = b'CHURRASPLAN_BACKUP_V1\n'


def chave():
    raw = base64.urlsafe_b64decode(os.environ['BACKUP_ENCRYPTION_KEY'])
    if len(raw) != 32:
        raise ValueError('Chave de backup inválida')
    return raw


def nome_banco(valor):
    if not re.fullmatch(r'[A-Za-z0-9_]{1,64}', valor):
        raise ValueError('Nome de banco inválido')
    return valor


def comando(binary, database, *flags):
    # A senha fica apenas no ambiente herdado; nunca em argv ou stdout.
    env = dict(os.environ, MYSQL_PWD=os.environ.get('DB_PASSWORD', ''))
    args = [binary, '--host='+os.environ.get('DB_HOST', '127.0.0.1'),
            '--port='+os.environ.get('DB_PORT', '3306'), '--user='+os.environ.get('DB_USER', 'churrasplan'),
            *flags, nome_banco(database)]
    return args, env


def backup(output, database):
    output = Path(output)
    if output.exists():
        raise FileExistsError("Já existe um backup com este nome")
    output.parent.mkdir(parents=True, exist_ok=True)
    nonce = secrets.token_bytes(12)
    encryptor = Cipher(algorithms.AES(chave()), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(MAGIC)
    compressor = zlib.compressobj(level=6, wbits=31)
    args, env = comando('mysqldump', database, '--single-transaction', '--skip-lock-tables', '--no-tablespaces', '--set-gtid-purged=OFF', '--hex-blob')
    try:
        with tempfile.TemporaryFile() as errors, subprocess.Popen(args, env=env, stdout=subprocess.PIPE, stderr=errors) as process:
            with output.open('xb') as target:
                os.chmod(output, 0o600)
                target.write(MAGIC+nonce)
                while block := process.stdout.read(1024*1024):
                    target.write(encryptor.update(compressor.compress(block)))
                if process.wait() != 0:
                    raise RuntimeError('mysqldump falhou; verifique credenciais e acesso ao banco')
                target.write(encryptor.update(compressor.flush())+encryptor.finalize()+encryptor.tag)
        digest = hashlib.sha256()
        with output.open('rb') as stream:
            for block in iter(lambda: stream.read(1024*1024), b''):
                digest.update(block)
        manifest = output.with_suffix(output.suffix+'.json')
        manifest.write_text(json.dumps({'formato':'ChurrasPlan-AES256GCM-gzip-v1', 'criado_utc':datetime.now(UTC).isoformat(),
                                       'bytes':output.stat().st_size, 'sha256':digest.hexdigest()}, indent=2)+'\n')
        os.chmod(manifest, 0o600)
    except Exception:
        output.unlink(missing_ok=True)
        raise


def restore(source, database):
    database = nome_banco(database)
    if not database.startswith('churrasplan_restore_'):
        raise ValueError('Restaure primeiro em banco isolado churrasplan_restore_*')
    args, env = comando('mysql', database, '--batch', '--skip-column-names')
    # Não criar, dropar ou sobrescrever bancos automaticamente.
    probe = subprocess.run(args, input=b'SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE();', env=env, capture_output=True, check=True)
    if probe.stdout.strip() != b'0':
        raise ValueError('O banco de restauração deve estar vazio')
    source = Path(source)
    with tempfile.TemporaryFile() as sql, source.open('rb') as stream:
        if stream.read(len(MAGIC)) != MAGIC:
            raise ValueError('Formato de backup inválido')
        nonce = stream.read(12)
        stream.seek(-16, 2)
        tag = stream.read(16)
        decryptor = Cipher(algorithms.AES(chave()), modes.GCM(nonce, tag)).decryptor()
        decryptor.authenticate_additional_data(MAGIC)
        decompress = zlib.decompressobj(wbits=31)
        stream.seek(len(MAGIC)+12)
        remaining = source.stat().st_size-len(MAGIC)-12-16
        while remaining > 0:
            block = stream.read(min(1024*1024, remaining))
            if not block:
                raise ValueError('Backup truncado')
            remaining -= len(block)
            sql.write(decompress.decompress(decryptor.update(block)))
        sql.write(decompress.decompress(decryptor.finalize())+decompress.flush())
        if not decompress.eof:
            raise ValueError('Arquivo gzip incompleto')
        # Só importa SQL depois de validar completamente a tag GCM.
        sql.seek(0)
        with tempfile.TemporaryFile() as errors:
            resultado = subprocess.run(args, stdin=sql, stderr=errors, env=env)
        if resultado.returncode:
            raise RuntimeError('Restauração MySQL falhou. Descarte o banco isolado e investigue.')


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='acao', required=True)
    p = sub.add_parser('backup'); p.add_argument('--directory', required=True); p.add_argument('--retention-days', type=int, default=14)
    p = sub.add_parser('restore'); p.add_argument('--file', required=True); p.add_argument('--database', required=True)
    args = parser.parse_args()
    if args.acao == 'restore':
        restore(args.file, args.database)
        print('Restauração isolada concluída; valide Alembic, contagens e smoke tests.')
    else:
        if not 1 <= args.retention_days <= 365:
            parser.error('Retenção deve ser entre 1 e 365 dias')
        directory = Path(args.directory)
        output = directory/('churrasplan-'+datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')+'.cpg')
        backup(output, os.environ.get('DB_NAME','churrasplan'))
        limite = datetime.now(UTC)-timedelta(days=args.retention_days)
        for old in directory.glob('churrasplan-*.cpg'):
            if datetime.fromtimestamp(old.stat().st_mtime, UTC) < limite:
                old.unlink(); old.with_suffix('.cpg.json').unlink(missing_ok=True)
        print('Backup cifrado concluído:', output.name)


if __name__ == '__main__':
    main()
