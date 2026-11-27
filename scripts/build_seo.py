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
    outros=lambda atual: ''.join(f'<li><a href="{slug}.html">{escape(titulo)}</a></li>' for slug,(titulo,_) in textos.items() if slug!=atual)
    pages=[]
    for slug,(titulo,texto) in textos.items():
        tipo='confraternizacao_empresa' if slug=='churrasco-empresarial' else 'aniversario' if slug=='churrasco-de-aniversario' else 'almoco'
        perfil='economico' if slug=='churrasco-economico' and 'economico' in REGRAS_PADRAO['perfil']['fatores'] else 'normal'
        n=int(re.search(r'para-(\d+)-pessoas',slug).group(1)) if re.search(r'para-(\d+)-pessoas',slug) else 20
        total=calcular_quantidade_total_carne(n,0,0,4,perfil,tipo_evento=tipo)['total_kg']
        tabela=''.join(f'<tr><td>{p}</td><td>{kg(calcular_quantidade_total_carne(p,0,0,4,perfil,tipo_evento=tipo)["total_kg"])}</td></tr>' for p in [10,20,30,50])
        canonical=base+'/guias/'+slug+'.html'
        dados={'@context':'https://schema.org','@type':'Article','headline':titulo,'description':texto,'mainEntityOfPage':canonical,'publisher':{'@type':'Organization','name':'ChurrasPlan'}}
        content=(f'<section class="guide-example ticket-shadow" aria-labelledby="exemplo-titulo"><div class="ticket"><h2 id="exemplo-titulo">Exemplo calculado pelo ChurrasPlan</h2>'
                 f'<p class="guide-example__params">{n} adultos, sem crianças, 4 horas, perfil {ROTULOS.get(perfil,perfil)}, evento {ROTULOS.get(tipo,tipo)}:</p>'
                 f'<strong class="guide-example__total">{kg(total)}<small>de necessidade de carne</small></strong>'
                 f'<table><thead><tr><th>Adultos</th><th>Necessidade de carne</th></tr></thead><tbody>{tabela}</tbody></table>'
                 '<p class="guide-example__note">Valores de necessidade física. Distribua os cortes e converta a compra comercial no planejador. Preços de referência são estimativas datadas, não cotações locais ou garantia de preço.</p></div></section>'
                 '<p class="guide-cta"><a class="btn btn--primary btn--lg" href="../planejamento.html">Calcular para a minha turma</a></p>'
                 f'<nav class="guide-more" aria-labelledby="outros-guias"><h2 id="outros-guias">Outros guias</h2><ul class="guide-list">{outros(slug)}</ul></nav>')
        render(ROOT/'guias'/f'{slug}.html',titulo,texto,canonical,content,publico,dados,lead=texto,kicker='Guias de churrasco')
        pages.append(canonical)
    render(ROOT/'guias'/'index.html','Guias para planejar churrascos','Quantidades, orçamento e organização com regras transparentes.',base+'/guias/index.html','<ul class="guide-list">'+links+'</ul>',publico,{'@context':'https://schema.org','@type':'CollectionPage','name':'Guias ChurrasPlan'},lead='Escolha um guia e adapte os exemplos ao seu evento.')
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


# Rótulos legíveis para os identificadores usados pelo motor de cálculo.
ROTULOS={'normal':'normal','economico':'econômico','almoco':'almoço','aniversario':'aniversário','confraternizacao_empresa':'confraternização da empresa'}


def kg(valor):
    return f'{valor:.2f}'.replace('.',',')+' kg'


CABECALHO=('<header class="site-header"><div class="site-header__inner">'
    '<a class="brand-lockup" href="../index.html" aria-label="ChurrasPlan, página inicial"><img class="brand-lockup__icon" src="../assets/logo-icon-96.webp" alt="" width="38" height="36"><img class="brand-lockup__wordmark" src="../assets/logo-wordmark-320.webp" alt="ChurrasPlan" width="132" height="20"></a>'
    '<button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav" data-nav-toggle><span class="nav-toggle__bars"></span><span class="sr-only">Abrir menu</span></button>'
    '<nav class="site-nav" id="site-nav" aria-label="Navegação principal"><a href="../index.html#como-funciona">Como funciona</a><a href="../planos.html">Planos</a><a href="../onde-comprar.html">Onde comprar</a><a href="../parceiros.html">Para negócios</a><a class="btn btn--primary site-nav__cta" href="../planejamento.html">Planejar churrasco</a></nav>'
    '</div></header>')

RODAPE=('<footer class="site-footer"><div class="site-footer__inner"><div class="site-footer__brand"><img src="../assets/logo-wordmark-320.webp" alt="ChurrasPlan" width="150" height="23" loading="lazy"><p>Planejamento de churrasco com quantidades, orçamento e lista de compras, conectado a mercados e açougues da sua região.</p></div>'
    '<nav class="site-footer__nav" aria-label="Rodapé"><div><p class="site-footer__title">Produto</p><a href="../planejamento.html">Planejar churrasco</a><a href="../planos.html">Planos e preços</a><a href="../onde-comprar.html">Onde comprar</a><a href="index.html">Guias de churrasco</a></div>'
    '<div><p class="site-footer__title">Negócios</p><a href="../parceiros.html">ChurrasPlan Parceiros</a><a href="../parceiro.html">Área do parceiro</a><a href="../profissional.html">Área profissional</a></div>'
    '<div><p class="site-footer__title">Conta e privacidade</p><a href="../minha-conta.html">Minha conta</a><a href="../privacidade.html">Privacidade</a><a href="../termos.html">Termos de uso</a><a href="../cookies.html">Cookies</a></div></nav></div>'
    '<div class="site-footer__legal"><span>© 2026 ChurrasPlan</span><span>Quantidades e preços exibidos são estimativas de planejamento.</span></div></footer>')


def render(path,title,desc,url,content,publico,dados,lead=None,kicker=None):
    topo=(f'<p class="eyebrow"><span></span>{escape(kicker)}</p>' if kicker else '')+'<h1>'+escape(title)+'</h1>'+(f'<p class="guide-lead">{escape(lead)}</p>' if lead else '')
    path.write_text(f'<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta name="theme-color" content="#a62210"><title>{escape(title)} — ChurrasPlan</title>'+metas(title,desc,url,publico)+'<link rel="icon" href="../favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="../css/ds.css"><link rel="stylesheet" href="../css/pages/content.css"><script type="application/ld+json">'+json.dumps(dados,ensure_ascii=False)+'</script></head><body class="guide-page"><a class="skip-link" href="#main">Pular para o conteúdo</a>'+CABECALHO+'<main id="main" class="content-main"><article class="prose-page guide"><header>'+topo+'</header>'+content+'</article></main>'+RODAPE+'<script src="../js/ui.js"></script></body></html>\n')


if __name__=='__main__':main()
