# Fase 1B — catálogo genérico e preços estimados

## Objetivo e diagnóstico
Um erro em qualquer uma das quatro chamadas paralelas de `carregarParceiro()` interrompia todo o carregamento. Mesmo quando o catálogo genérico estava íntegro, o seletor podia aparecer vazio. A rota existente `/api/produtos?tipo_produto=generico` ainda calculava resumos de histórico para cada item, multiplicando consultas sem necessidade. Na listagem geral, os preços nacionais já utilizados pelo motor de cálculo não tinham campos explícitos no JSON de produtos.

## Implementação
- `GET /api/produtos/genericos`: lista genéricos ativos com categoria e referência estimada opcional, sem consultar o histórico de ofertas. O endpoint anterior permanece compatível.
- `GET /api/produtos` e `GET /api/produtos/{id}`: três campos adicionais compatíveis, sem alterar preço comercial: `preco_referencia`, `preco_referencia_data_base`, `preco_referencia_unidade`.
- Somente slugs genéricos cobertos pelo catálogo de referência BR-2026-09 retornam estimativa. SKUs comerciais, limpeza e outros itens sem calibração retornam `null` e não recebem preço fictício.
- O painel usa `Promise.allSettled`: métricas indisponíveis não bloqueiam seleção de produtos e cada área que falhar apresenta aviso. Quando o catálogo falha, a lista fica desabilitada e exibe mensagem específica.
- Categorias previstas em `20260925_0007`: carnes, bebidas, mercearia, laticínios, padaria, hortifruti, congelados, limpeza, higiene e descartáveis. `20260925_0008` completa produtos base do planejador.

## Contrato de preço
`preco_minimo_atual` e `preco_medio_historico` descrevem ofertas/histórico publicável; `preco_referencia` é **estimativa nacional de planejamento**, base set/2026, com valor pela `preco_referencia_unidade` da configuração do produto genérico. Não usar `preco_referencia` para anunciar preços reais, afirmar venda, classificar mercado ou atribuir preço a SKU sem embalagem correspondente.

Fontes de referência preexistentes: `docs/PRECOS_REFERENCIA_BRASIL_2026.md`. Nenhuma cotação externa atual foi criada e nenhum preço foi arbitrariamente adicionado.

## Banco, compatibilidade e rollback
Sem migration: reaproveita as tabelas e seeds Alembic 0007/0008, sem alteração persistente ou exclusão. Rollback = revert deste PR. Rotas e contratos anteriores preservados; nova rota e campos são aditivos.

## Testes para aprovação
- Unit/integration SQLite: opções de várias categorias, filtro genérico/comercial, campos estimativos, referência vs oferta real, cobertura dos produtos do motor e ausência de referência para limpeza/SKU.
- Integração MySQL real após `alembic upgrade head`: presença de categorias e produtos genéricos base sem depender de `seed_demo.py`.
- Node VM: catálogo disponível apesar de erro de métricas, seleção por categoria, aviso estimativo, sem preço inventado; falha do catálogo desabilita seletor.
- E2E Chromium: registro de parceiro, ativação do perfil e seleção de bebida/limpeza.
- CI: frontend, segurança, Docker e suíte geral; verificar logs do commit do PR, não usar apenas baseline.

## Limites e próximos passos
Esta entrega não altera cálculos físicos, embalagens ou subtotais; não resolve o isolamento multi-tenant nem controle de SKUs por organização, que exigem a Fase 2. Não fazer merge ou deploy sem revisão. Os PRs #3 e #4 ainda estão abertos e requerem integração ordenada.
