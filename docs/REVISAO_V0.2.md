# Revisão técnica v0.2 — matriz de correções

Este documento registra a resolução das inconsistências encontradas na auditoria do MVP original.

| # | Inconsistência auditada | Resolução v0.2 |
|---:|---|---|
| 1 | `schema.sql` não possuía campos que o model/README afirmavam existir | Schema, ORM e migration foram alinhados; Alembic passou a ser a fonte de verdade. |
| 2 | Exemplo da home usava matemática diferente do backend | Exemplo recalculado com as mesmas funções/regras do backend. |
| 3 | Coeficientes de carne/cerveja estavam superdimensionados para o objetivo do produto | Bases revisadas e centralizadas; continuam configuráveis e documentadas como heurísticas. |
| 4 | `carvao_kg_por_kg_carne` personalizado era aceito, mas ignorado | O serviço de carvão usa o coeficiente personalizado quando o perfil é personalizado. |
| 5 | Lista de compras gravava necessidade, não compra | Lista grava `quantidade_compra`, embalagem e unidade comercial. |
| 6 | Custo multiplicava preço pela necessidade | Subtotal multiplica preço pela compra comercial efetiva. |
| 7 | Cerveja misturava número de latas com unidade `litro` | Necessidade permanece em litros; compra possui embalagem/unidade de venda separadas. |
| 8 | Resultado não mostrava quanto efetivamente comprar | UI exibe necessário, comprar, embalagem, oferta e subtotal. |
| 9 | POST e GET devolviam significados diferentes para o mesmo item | Quantidades/preços são persistidos como snapshot e todos os endpoints usam a mesma serialização. |
| 10 | Recarregar `resultado.html` criava novo churrasco | Frontend usa GET/PUT e backend possui idempotência por `chave_cliente`. |
| 11 | “Concluir” mantinha planejamento antigo no navegador | Concluir limpa o estado versionado; estado legado também é removido. |
| 12 | Gelo era incluído sem seleção e não dependia do que a UI dizia | Gelo ganhou flag explícito; só entra se ativado. |
| 13 | `tipo_evento` era só metadado | Fator de evento moderado passou a afetar carne e bebidas. |
| 14 | Era possível chegar a 1.500 pessoas apesar do limite declarado de 500 | Validação cruza os três grupos e limita o total a 500. |
| 15 | Produto/preço era resolvido principalmente por nome textual | Catálogo usa `slug` estável e persiste `produto_id`; nome virou apresentação/fallback. |
| 16 | Seed cobria poucos itens e não era idempotente | Seed cobre o catálogo do frontend e usa upserts/slugs; ofertas demo não duplicam pela mesma fonte. |
| 17 | Dinheiro era `FLOAT` | Preço, subtotal e custos usam `DECIMAL(12,2)`/`Numeric`. Migration converte bancos legados. |
| 18 | Histórico, preço atual e melhor preço eram confundidos | Uma oferta atual é a observação mais recente por estabelecimento; custo usa a melhor oferta atual; histórico permanece separado. |
| 19 | Todas as carnes assumiam pacote global de 2 kg | Forma de venda pertence ao produto; carnes podem ser fracionadas e outros itens usam embalagem própria. |
| 20 | `ON DELETE` do SQL e do ORM não tinham a mesma semântica | Schema/model usam CASCADE, SET NULL ou RESTRICT conforme o domínio; migration normaliza FKs em MySQL. |
| 21 | APIs/depreciações do SQLAlchemy/Pydantic geravam warnings evitáveis | `db.get()` e configuração Pydantic 2 foram adotados nas rotas/schemas revisados. |
| 22 | Testes não capturavam as inconsistências centrais | Integração agora testa compra vs. necessidade, snapshots, preços atuais, idempotência, GET/POST/PUT e flags. |
| 23 | Estado antigo do navegador seria perdido com a nova chave | `state.js` migra automaticamente `churrasplan_estado` para `churrasplan_estado_v2`. |
| 24 | Oferta antiga poderia ser reinterpretada após mudar embalagem do produto | Migration preserva preço legado no histórico, mas o marca indisponível quando a unidade original não é confiável. |

## Invariantes do domínio depois da revisão

1. `quantidade_necessaria` nunca significa embalagem.
2. `quantidade_compra` nunca significa número de embalagens; é a quantidade física coberta pela compra, na unidade de consumo.
3. `quantidade_embalagens` guarda a contagem comercial quando a venda não é fracionada.
4. `preco_unitario` refere-se à `unidade_venda` do produto.
5. `subtotal_estimado` é snapshot da compra naquele momento.
6. Atualizar uma oferta não reescreve o passado; uma nova observação gera uma nova linha em `precos`.
7. Um planejamento possui uma `chave_cliente` idempotente.
8. A soma total de pessoas é o limite validado.
9. O backend é a fonte de verdade matemática; o frontend apenas coleta escolhas e apresenta resultados.
10. Alterações de schema passam por Alembic.

## Próximas evoluções habilitadas pela nova modelagem

Sem alterar a semântica dos churrascos já salvos, a aplicação agora pode receber autenticação/usuários, CRUD administrativo de catálogo e ofertas, coleta externa de preços, geolocalização, validade/frescor da oferta, preferência de estabelecimento e um otimizador que minimize custo total considerando deslocamento e múltiplas lojas.
