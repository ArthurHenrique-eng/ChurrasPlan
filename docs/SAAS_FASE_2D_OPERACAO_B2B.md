# Fase 2D — Operação B2B: filiais, ofertas CSV e relatórios

**Branch de implementação:** `Saas-ChurrasPlan`. Nenhuma alteração da `main`, criação de branch de fase, checkout de pagamento ou implantação em produção.

## Entregas

- Os estabelecimentos existentes são as **unidades/filiais operacionais** de uma organização; a migration `20261008_0012` adiciona `codigo_filial` opcional e `unidade_matriz`. O código é exclusivo **dentro da organização**, podendo ser repetido em organizações distintas. Ao marcar outra filial como matriz, o sistema transfere essa identificação de modo transacional. Nenhum estabelecimento legado recebe código artificial e nenhum preço existente é modificado.
- Proprietários e gestores podem alterar código, matriz e estado ativo de filiais pelo painel; editores/leitores visualizam unidades sem poder modificar essas informações administrativas. O campo `parceiro_verificado` continua exclusivo da administração global, pois marcar uma matriz não equivale a verificar a loja.
- Importação segura de ofertas CSV com validação por linha, limite de **200 linhas / 100 KB** por envio, status de estoque, números monetários explícitos, autorização por tenant e quota do plano. Cada lote usa `chave_idempotencia` distinta por organização; reenvio com mesma chave e conteúdo retorna o resultado anterior, sem repetir inclusões. Mesma chave com conteúdo diferente → HTTP 409. A aplicação grava os resultados e o SHA-256 do conteúdo, **não o CSV original**.
- Os lotes são gravados atomica e transacionalmente: linhas válidas entram juntas, linhas inválidas são rejeitadas com número e motivo. O resultado relata `criadas`, `rejeitadas`, `erros` e `repetida`. Importações de lojas inativas, alheias, produtos alheios ou SKU inexistente não criam ofertas. Limites existentes de oferta contabilizam também importações.
- Checklist de **onboarding** reflete dados reais: loja criada, verificação administrativa, produto comercial cadastrado e ao menos uma oferta registrada. Não deve ser interpretado como confirmação de vendas.
- Relatório operacional de até 365 dias agregado por filial: total de ofertas históricas, visualizações e cliques na rota registrados pela funcionalidade “Onde comprar”. As métricas **não são faturamento, pedidos, vendas ou conversão**. `vendas_confirmadas` e `receita_confirmada` são explicitamente `null`.

## Contratos HTTP

| Método | Caminho | Autorização |
| --- | --- | --- |
| GET | `/api/parceiro/filiais` | Parceiro/admin, org selecionada |
| PATCH | `/api/parceiro/filiais/{estabelecimento_id}` | Proprietário ou gestor do tenant + CSRF |
| GET | `/api/parceiro/onboarding` | Parceiro/admin, org selecionada |
| GET | `/api/parceiro/relatorios/comercial?periodo_dias=30` | Parceiro/admin, org selecionada |
| POST | `/api/parceiro/importacoes/ofertas` | Gestor/editor/proprietário + CSRF (admin legado autorizado se org selecionada) |

O cabeçalho `X-Organizacao-ID` é obrigatório quando uma conta integra múltiplos tenants. Admin global sem organização não pode invocar essas rotas de operação específica sem selecionar uma org; os endpoints de equipe ainda exigem membership local.

### Exemplo CSV

```csv
estabelecimento_id;produto_id;preco;preco_original;estoque_status
3;41;12,90;15,90;disponivel
3;42;8,50;;baixo
4;41;14,00;;indisponivel
```

Campos obrigatórios: `estabelecimento_id`, `produto_id`, `preco`. Colunas opcionais: `preco_original`, `estoque_status` (`disponivel`, `baixo`, `indisponivel`). Suporta ponto ou vírgula decimal, com até duas casas; a vírgula deve ser citada conforme regras CSV caso o delimitador seja `,` ao invés de `;`. Preços de parceiro são **ofertas reais declaradas pelo parceiro**, não os preços de referência do planejador. O sistema não valida automaticamente sua veracidade; estabelecimentos não verificados continuam fora de recomendações públicas até aprovação.

```json
{
  "chave_idempotencia": "lote-2026-10-08-0001",
  "csv_texto": "estabelecimento_id;produto_id;preco;estoque_status\n3;41;12,90;disponivel\n"
}
```

Retorno HTTP 201 com `criadas`, `rejeitadas`, `linhas`, lista de erros e `repetida`. Falta de autenticação → 401, CSRF inválido → 403, organização externa → 404, ausência do header quando necessária → 409, payload inválido → 422. Eventos de precificação continuam com identificadores do estabelecimento; não existe deduplicação global de campanhas/preços entre lotes distintos.

## Evidências esperadas e segurança

- Testes API: filial por tenant, código único, matriz exclusiva, edição por papel, importações parciais e replay, limite do plano, CSRF, cabeçalho adulterado e relatórios sem métricas financeiras.
- Testes MySQL: migration `0011 → 0012`, teste concorrente de duas importações com mesma chave, `alembic check`, reversão até `0008` e retorno ao head. CI também executa frontend, Docker, security audit, CodeQL Python/JS e browser E2E.
- O sistema mantém os dados legados; **downgrade 0012 apaga o histórico de lotes idempotentes e os metadados das filiais**, mas preserva as ofertas importadas já criadas. Para bancos reais, fazer backup e planejar reaplicação de chaves idempotentes antes do rollback para não duplicar ofertas.

## Pendente no roadmap

Esta entrega cobre a base de **filiais, onboarding e relatórios B2B**, além de **importação inicial de ofertas CSV**. Ainda faltam campanha promocional com vigência governada e aprovação, importação estruturada de catálogo de SKUs, exportação e atualização em massa avançadas, análises comerciais com vendas integradas e automações/integrações ERP. Esses pontos pertencem à Fase 4 e não devem ser confundidos com funcionalidades prontas.

O ChurrasPlan ainda não possui cobrança real, clientes pagantes confirmados, integração ERP em produção ou campanha faturada; portanto a Fase 3 de billing e os gates de piloto continuam pendentes.
