# Fase 4A — Catálogo B2B em escala e campanhas moderadas

Implementado diretamente na branch **`Saas-ChurrasPlan`**. Nunca modificar `main` sem instrução; nenhuma branch auxiliar foi criada.

## Catálogo comercial CSV (criar e atualizar)

`POST /api/parceiro/importacoes/catalogo` recebe JSON com `chave_idempotencia` e `csv_texto`. Autorização: membro da organização com papel proprietário, gestor ou editor; CSRF obrigatório. O tenant é resolvido no servidor, usando `X-Organizacao-ID` quando necessário. Administrador global só opera com organização explícita.

Exemplo CSV separado por ponto e vírgula:

```csv
sku;produto_pai_id;nome;marca;unidade_venda;quantidade_embalagem;unidade_embalagem;ean;ativo
AGUA-1500;12;Água Mineral;Marca Exemplo;garrafa;1,5;litro;7891234567890;true
CARVAO-3000;24;Carvão Vegetal;Marca Exemplo;saco;3;kg;;true
```

- Colunas obrigatórias: `sku`, `produto_pai_id`, `nome`, `marca`, `unidade_venda`, `quantidade_embalagem`, `unidade_embalagem`. Opcionais: `ean` (8 a 32 dígitos), `variante` e `ativo`.
- `produto_pai_id` precisa apontar para um produto **genérico ativo**. Essa categoria pode ser selecionada no catálogo existente; um SKU comercial nunca vira produto genérico.
- **Upsert** pelo `sku` dentro da organização. Código novo cria SKU, código existente atualiza nome/marca/unidade/tamanho/EAN/atividade sem mudar o ID. Alterar o genérico pai de um SKU existente exige criar novo SKU, evitando reinterpretar histórico de preços.
- O EAN permanece único globalmente conforme o banco. EAN repetido, linha malformada, código repetido no mesmo lote, quantidade inválida ou cota esgotada são rejeitados com motivo/número da linha, sem bloquear demais linhas válidas.
- Até **200 linhas** e **100 KB** por lote. Lotes são transacionais no MySQL e no SQLite; uma linha inválida é descartada via savepoint. `criados`, `atualizados`, `rejeitados` e `erros` são retornados. Importações paralelas de uma mesma organização se serializam por bloqueio da linha da organização.
- A chave idempotente é única **por organização** e vinculada a SHA-256 do CSV. Reenvio exato retorna `repetida=true` sem duplicar; mesma chave com CSV diferente retorna 409.
- Somente resumo e hash do CSV são persistidos em `importacoes_catalogo`. **Nenhum arquivo CSV em texto completo, preço fictício ou pagamento** é armazenado pela importação de catálogo. O histórico das ofertas continua intacto.
- Novos SKUs consomem a cota `produtos_comerciais` do plano; atualização de SKUs existentes não consome nova cota. O plano continua Free por padrão ou concessão administrativa temporária.

Exemplo JSON:

```json
{
  "chave_idempotencia": "lote-catalogo-2026-outubro",
  "csv_texto": "sku;produto_pai_id;nome;marca;unidade_venda;quantidade_embalagem;unidade_embalagem\nAGUA-1500;12;Água Mineral;Marca Exemplo;garrafa;1,5;litro\n"
}
```

## Campanhas comerciais

Os itens de campanha são **referências a ofertas reais `precos.id` já cadastradas** por filial. Criar uma campanha não cria preços, cupons, compras, pagamentos ou direitos de assinatura. Campanhas só divulgam preços previamente cadastrados e moderados.

### API

| Método | Rota | Acesso |
| --- | --- | --- |
| GET | `/api/parceiro/ofertas/campanhas` | Qualquer membro B2B, lista as últimas 200 ofertas elegíveis do tenant |
| GET | `/api/parceiro/campanhas` | Qualquer membro B2B, até 200 campanhas do tenant |
| POST | `/api/parceiro/campanhas` | Proprietário/gestor cria rascunho |
| PUT | `/api/parceiro/campanhas/{id}` | Proprietário/gestor corrige rascunho/rejeitada |
| POST | `/api/parceiro/campanhas/{id}/enviar` | Proprietário/gestor envia para revisão |
| POST | `/api/parceiro/campanhas/{id}/cancelar` | Proprietário/gestor cancela, inclusive aprovada |
| GET | `/api/admin/campanhas/pendentes` | Administrador global, fila moderada |
| POST | `/api/admin/campanhas/{id}/revisar` | Administrador global aprova/rejeita, CSRF |
| GET | `/api/campanhas/ativas` | Público, somente aprovadas, vigentes e com oferta atualmente válida |

Exemplo criação:

```json
{
  "codigo": "OUTUBRO-AGUA",
  "nome": "Ofertas de Outubro",
  "descricao": "Seleção promocional da filial",
  "inicio_em": "2026-10-09T09:00:00Z",
  "fim_em": "2026-10-12T21:00:00Z",
  "preco_ids": [100, 101]
}
```

Estados: `rascunho` → `em_revisao` → `aprovada` ou `rejeitada`. Rejeitada pode ser editada e reenviada. Cancelamento é irrevogável no fluxo atual. Datas são normalizadas em UTC, duração máxima **90 dias**, sem retroagir mais de um dia. Itens de campanha pertencem exclusivamente à organização; a campanha tem código único por tenant e até **50 ofertas distintas**.

Aprovação recusa campanha expirada, produto inativo, oferta indisponível, filial não verificada/inativa ou preço cuja vigência não cubra a campanha. Após aprovada, a consulta pública **reavalia** status da loja/produto, estoque e vigência, inclusive se uma filial perder a verificação. A simples aprovação não força exposição de uma loja que deixou de atender requisitos. Todas as decisões administrativas são auditadas com ator e justificativa de rejeição, e eventos dos gestores entram em `auditoria_organizacao`.

O painel de parceiros permite envio de CSV, criação/envio/cancelamento de campanhas e leitura do estado. O painel administrativo traz a fila de revisão com aprovação/rejeição e justificativa. O formulário de **edição de campanha rejeitada** está disponível pela API; a UI inicial mostra a instrução, ainda não um editor visual completo.

## Migração, rollback e testes

Migration `20261008_0013`: `importacoes_catalogo`, `campanhas_comerciais`, `campanhas_comerciais_itens`; nenhuma mudança nas tabelas existentes de preços, usuários ou estabelecimentos. Antes de `alembic downgrade 20261008_0012`, salvar a auditoria/histórico destas três tabelas; o rollback é destrutivo para **metadados de campanhas e resumos de importação**, não para SKUs/valores de ofertas já persistidos. Reaplicar lote após rollback pode recriar SKUs? O upsert por SKU preserva IDs, mas a idempotência histórica deixa de existir: avaliar antes de reprocessar.

Gates: testes de importação parcial, SKU existente, quota, EAN, replay, role editor/leitor, spoof de tenant, transições e moderação; MySQL concorrente, upgrade/downgrade/head, schema/ORM; JavaScript, E2E Chromium e CodeQL Python/JS. Histórico CI tem de corresponder ao **head final**.

**Fora do escopo:** cobrança/checkout/pagamentos da Fase 3, cupons resgatáveis, campanha de mídia paga, conciliação de compras, conversão em vendas reais, ERP de produção, automação de preço, expurgo de logs e marketplace completo. Dados de visualização/clique não são transações comerciais.
