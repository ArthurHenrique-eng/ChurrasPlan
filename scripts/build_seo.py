"""Páginas úteis geradas pelo motor determinístico; execute com domínio real antes do deploy."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
from html import escape
from urllib.parse import urlsplit
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'BackEnd'/'Python'))
from services.calculo_carne import calcular_quantidade_total_carne
from config import REGRAS_PADRAO

ROOT=Path(__file__).resolve().parents[1]/'FrontEnd'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base-url',default=os.getenv('PUBLIC_APP_URL','http://localhost:8080'));args=parser.parse_args()
    base=args.base_url.rstrip('/'); parsed=urlsplit(base)
    if parsed.scheme not in {'http','https'} or not parsed.netloc or parsed.query or parsed.fragment or parsed.username or parsed.path:
        raise SystemExit('Use a origem pública completa, sem caminho, credenciais ou query string.')
    publico=parsed.scheme=='https' and parsed.hostname not in {'localhost','127.0.0.1'} and not parsed.hostname.endswith('.example.com')
    (ROOT/'guias').mkdir(exist_ok=True)
    textos={
      'quantidade-de-carne-por-pessoa':('Quantidade de carne por pessoa', 'O perfil normal usa a base de consumo adulto e infantil do ChurrasPlan. Duração e tipo de evento ajustam essa necessidade; embalagens e incrementos comerciais são aplicados depois. Não confunda o peso necessário com a quantidade de pacotes para comprar.'),
      'churrasco-economico':('Como organizar um churrasco econômico', 'Comece pelo número de participantes e pela duração. Selecione cortes adequados ao seu orçamento, compare a cesta completa e mantenha água e acompanhamentos no planejamento. Um item barato isolado não garante a compra de menor custo: embalagem, cobertura e distância também importam.'),
      'churrasco-empresarial':('Planejamento de churrasco empresarial', 'Confirme participantes e restrições, estabeleça o orçamento, monte uma lista com compra comercial e atribua responsáveis. O tipo confraternização empresarial possui um fator específico no motor. Ofertas de parceiros são exibidas somente quando elegíveis; intenção de compra não é compra confirmada.'),
      'churrasco-de-aniversario':('Como planejar um churrasco de aniversário', 'Separe adultos e crianças, estime a duração e use convites para atualizar as confirmações. Escolha acompanhamentos conforme restrições alimentares. Revise gelo, carvão e descartáveis explicitamente, em vez de presumir que todos fazem parte de qualquer evento.')}
    for n in [10,20,30,50]:
        textos[f'churrasco-para-{n}-pessoas']=(f'Churrasco para {n} pessoas',f'Para {n} adultos, quatro horas, almoço e perfil normal, o exemplo abaixo parte do motor atual. Ao incluir crianças, mudar o perfil ou informar restrições, refaça o planejamento. A compra deve cobrir a necessidade física com os incrementos ou embalagens de cada produto.')
    links=''.join(f'<li><a href="{slug}.html">{escape(titulo)}</a></li>' for slug,(titulo,_) in textos.items())
    pages=[]
    for slug,(titulo,texto) in textos.items():
        tipo='confraternizacao_empresa' if slug=='churrasco-empresarial' else 'aniversario' if slug=='churrasco-de-aniversario' else 'almoco'
        perfil='economico' if slug=='churrasco-economico' and 'economico' in REGRAS_PADRAO['perfil']['fatores'] else 'normal'
        n=int(re.search(r'para-(\d+)-pessoas',slug).group(1)) if re.search(r'para-(\d+)-pessoas',slug) else 20
        total=calcular_quantidade_total_carne(n,0,0,4,perfil,tipo_evento=tipo)['total_kg']
        tabela=''.join(f'<tr><td>{p}</td><td>{calcular_quantidade_total_carne(p,0,0,4,perfil,tipo_evento=tipo)["total_kg"]:.2f} kg</td></tr>' for p in [10,20,30,50])
        canonical=base+'/guias/'+slug+'.html'
        dados={'@context':'https://schema.org','@type':'Article','headline':titulo,'description':texto,'mainEntityOfPage':canonical,'publisher':{'@type':'Organization','name':'ChurrasPlan'}}
        content=f'<p>{escape(texto)}</p><section class="saas-card"><h2>Exemplo calculado pelo ChurrasPlan</h2><p>{n} adultos, sem crianças, 4 horas, perfil {perfil}, evento {tipo}: <strong>{total:.2f} kg de necessidade de carne</strong>.</p><table><thead><tr><th>Adultos</th><th>Necessidade de carne</th></tr></thead><tbody>{tabela}</tbody></table><p>Valores de necessidade física. Distribua os cortes e converta a compra comercial no planejador. Preços de referência são estimativas datadas, não cotações locais ou garantia de preço.</p></section><p><a class="primary-button" href="../planejamento.html">Calcular para a minha turma</a></p><nav aria-label="Outros guias"><ul>{links}</ul></nav>'
        render(ROOT/'guias'/f'{slug}.html',titulo,texto,canonical,content,publico,dados)
        pages.append(canonical)
    render(ROOT/'guias'/'index.html','Guias para planejar churrascos','Quantidades, orçamento e organização com regras transparentes.',base+'/guias/index.html','<p>Escolha um guia e adapte os exemplos ao seu evento.</p><ul>'+links+'</ul>',publico,{'@context':'https://schema.org','@type':'CollectionPage','name':'Guias ChurrasPlan'})
    for name,title,desc in [('index.html','ChurrasPlan — Planejamento e compra de churrascos','Planeje quantidades, listas e orçamento; conecte seu churrasco a mercados, açougues e profissionais locais.'),('parceiros.html','ChurrasPlan Parceiros — Mercados, açougues e profissionais','Gerencie ofertas e filiais, receba interesse comercial e acompanhe resultados do ChurrasPlan.')]:
        p=ROOT/name;s=p.read_text();s=re.sub(r'<title>.*?</title>',f'<title>{title}</title>',s,flags=re.S)
        s=re.sub(r'<meta name="description"[^>]*>', '', s)
        s=re.sub(r'<!-- SEO_INICIO -->.*?<!-- SEO_FIM -->','',s,flags=re.S)
        metadata=metas(title,desc,base+'/'+name,publico)
        org={'@context':'https://schema.org','@type':'WebSite','name':'ChurrasPlan','url':base+'/'}
        s=s.replace('</head>','<!-- SEO_INICIO -->'+metadata+'<script type="application/ld+json">'+json.dumps(org,ensure_ascii=False)+'</script><!-- SEO_FIM --></head>');p.write_text(s)
        pages.append(base+'/'+name)
    pages.append(base+'/guias/index.html')
    xml='<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+escape(url)+'</loc></url>' for url in pages)+'</urlset>\n'
    (ROOT/'sitemap.xml').write_text(xml)
    (ROOT/'robots.txt').write_text('User-agent: *\n'+('Allow: /\n' if publico else 'Disallow: /\n')+'Disallow: /api/\nDisallow: /admin.html\nDisallow: /operacao.html\nDisallow: /minha-conta.html\nDisallow: /parceiro.html\nDisallow: /resultado.html\nDisallow: /convite.html\nSitemap: '+base+'/sitemap.xml\n')
    print(f'SEO: {len(pages)} URLs, indexação '+('pública' if publico else 'desativada (ambiente local/staging)'))


def metas(title,desc,url,publico):
    return f'<meta name="description" content="{escape(desc,quote=True)}"><link rel="canonical" href="{escape(url,quote=True)}"><meta property="og:title" content="{escape(title,quote=True)}"><meta property="og:description" content="{escape(desc,quote=True)}"><meta property="og:url" content="{escape(url,quote=True)}"><meta property="og:type" content="website"><meta name="twitter:card" content="summary"><meta name="robots" content="{"index,follow" if publico else "noindex,nofollow"}">'


def render(path,title,desc,url,content,publico,dados):
    path.write_text(f'<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} — ChurrasPlan</title>'+metas(title,desc,url,publico)+'<link rel="icon" href="../favicon.svg"><link rel="stylesheet" href="../css/unified-core.css"><link rel="stylesheet" href="../css/saas.css"><script type="application/ld+json">'+json.dumps(dados,ensure_ascii=False)+'</script></head><body class="account-page"><a class="skip-link" href="#main">Pular para o conteúdo</a><main class="saas-shell" id="main"><header class="simple-topbar"><a href="../index.html"><img src="../assets/logo-wordmark.png" alt="ChurrasPlan" width="200"></a><a href="../parceiros.html">Parceiros</a></header><section class="saas-hero"><h1>'+escape(title)+'</h1></section>'+content+'<footer><a href="../privacidade.html">Privacidade</a> · <a href="../termos.html">Termos</a></footer></main></body></html>')


if __name__=='__main__':main()
