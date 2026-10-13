"""Carga básica em calculadora determinística, sem persistir eventos ou cobrar."""
import argparse,json,time,urllib.request
from concurrent.futures import ThreadPoolExecutor


def main():
    p=argparse.ArgumentParser();p.add_argument('url');p.add_argument('--requests',type=int,default=30);p.add_argument('--concurrency',type=int,default=3);a=p.parse_args()
    if not 1<=a.requests<=300 or not 1<=a.concurrency<=10:p.error('Limites: 300 requests, concorrência 10')
    body=json.dumps({'homens':10,'mulheres':0,'criancas':0,'duracao_horas':4,'perfil_consumo':'normal','tipo_evento':'almoco','carnes':[{'nome':'Picanha','produto_slug':'picanha','percentual':100}],'carvao_ativo':True}).encode()
    def once(_):
        inicio=time.monotonic();req=urllib.request.Request(a.url.rstrip('/')+'/api/calculadora/carnes',data=body,headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=15) as r:
            result=json.load(r);assert r.status==200 and result['total_kg']==4
        return (time.monotonic()-inicio)*1000
    inicio=time.monotonic()
    with ThreadPoolExecutor(max_workers=a.concurrency) as pool:times=sorted(pool.map(once,range(a.requests)))
    print(json.dumps({'requisicoes':len(times),'concorrencia':a.concurrency,'segundos':round(time.monotonic()-inicio,2),'p50_ms':round(times[len(times)//2],2),'p95_ms':round(times[min(len(times)-1,int(len(times)*.95))],2)}))


if __name__=='__main__':main()
