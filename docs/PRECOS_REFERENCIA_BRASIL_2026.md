# Preços de referência Brasil — 2026

O ChurrasPlan utiliza preços de referência apenas quando não existe uma oferta
real e publicável para o produto. A referência serve para estimar orçamento,
custo por pessoa e divisão de gastos antes de parceiros disponibilizarem preços
locais.

## Regra de prioridade

1. oferta real atual de estabelecimento ativo/verificado;
2. preço de referência Brasil 2026;
3. sem preço, somente quando o item não pertence ao catálogo coberto.

Preços de referência nunca entram no ranking de mercados e não são exibidos
como oferta de um estabelecimento.

## Metodologia

Os valores foram calibrados como estimativas nacionais de varejo em setembro de
2026, usando pesquisas públicas de preços de churrasco, levantamentos recentes
de mercado e amostras de grandes varejistas. Como preço varia por cidade, marca,
promoção e embalagem, os números são arredondados para planejamento e não devem
ser apresentados como "preço atual garantido".

Fontes de calibração consultadas:

- PROCON Joinville — pesquisas mensais de churrasco 2026:
  https://www.joinville.sc.gov.br/publicacoes/pesquisas-de-precos-procon-churrasco-2026/
- PROCON Joinville — pesquisa de maio/2026:
  https://www.joinville.sc.gov.br/wp-content/uploads/2026/05/Pesquisa-de-Precos-Churrasco-mai-2026.pdf
- PROCON Patos/PB — pesquisa de itens para churrasco de fevereiro/2026:
  https://patos.pb.gov.br/noticias/proconpatos-divulga-preco-a16419.html
- Neogrid — levantamento de churrasco e bebidas em maio/2026:
  https://neogrid.com/noticias/churrasco-e-bebidas-ficam-caros-na-copa/
- Carrefour — amostras atuais de varejo para cortes e itens complementares:
  https://mercado.carrefour.com.br/

## Implementação

A tabela está em:

`BackEnd/Python/services/precos_referencia.py`

A versão atual é:

`BR-2026-09`

O catálogo base usado pelo planejador é garantido via Alembic em
`20260925_0008`. Assim, uma instalação nova não depende de `seed_demo.py`
para disponibilizar os produtos genéricos usados nos cálculos.

O `seed_demo.py` continua existindo para desenvolvimento/E2E, mas usa os
mesmos valores de referência para evitar divergência entre ambientes.
