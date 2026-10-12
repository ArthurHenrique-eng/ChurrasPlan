"""Verificação de publicação sem criar usuários, assinaturas ou eventos."""
import argparse
import json
import urllib.request


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('url'); args=parser.parse_args()
    base=args.url.rstrip('/')
    for path in ['/api/health', '/api/health/ready', '/index.html', '/parceiros.html', '/robots.txt', '/sitemap.xml', '/manifest.webmanifest']:
        with urllib.request.urlopen(base+path, timeout=10) as response:
            if response.status != 200:
                raise SystemExit('Falhou: '+path)
            if path.endswith('/ready') and json.load(response).get('status') != 'ready':
                raise SystemExit('Banco indisponível')
        print('OK', path)


if __name__=='__main__': main()
