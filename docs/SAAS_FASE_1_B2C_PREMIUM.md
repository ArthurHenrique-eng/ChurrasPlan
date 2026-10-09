# Fase 1 B2C — benefícios Free / Premium pessoal

**Branch exclusiva:** `Saas-ChurrasPlan`. **Origem:** auditoria de 09/10/2026,
commit `1f30ddd717cbdbd8b2064530287df6ce1d331cbb`.
**Autorização comercial:** Free = 5 planejamentos salvos; Premium = planejamentos ilimitados,
comparação avançada, exportação PDF/CSV, modelos reutilizáveis e análise detalhada de custos.

## Diagnóstico e limites do incremento

Antes desta fase, `usuarios.plano` e `assinaturas_usuario` coexistiam com
`assinaturas_stripe_usuario`. O novo serviço `services/entitlements_usuario.py`
**nunca** concede Premium a partir de `usuarios.plano`, de planos legados,
de flags da interface nem de redirecionamentos Stripe.
A fonte é exclusivamente assinatura Stripe TEST localmente reconciliada,
com `plano_slug=premium`, `status=active` e `periodo_fim_em` futuro.

Não muda a matemática de carne, bebida, carvão, extras, unidade de compra ou
preço; as funções determinísticas permanecem em `services/`. Não habilita
chaves `sk_live_` ou cobrança real. Não altera limites B2B nem a política
do `services/entitlements.py` empresarial.

## Contratos e autorização

| Endpoint | Público | Comportamento |
| --- | --- | --- |
| GET `/api/planos/meus-beneficios` | Conta autenticada | Plano efetivo, cota, uso e flags de recursos |
| POST `/api/churrascos` | Existente | Novo evento autenticado limitado a cinco no Free; premium ilimitado; atualização idempotente não consome vaga |
| POST `/api/churrascos/{id}/repetir` | Existente | Novo evento consome vaga; repetição histórica continua Free quando houver vaga |
| POST `/api/churrascos/{id}/vincular` | Existente | Vincular evento anônimo a uma conta consome vaga |
| GET `/api/churrascos/{id}/analise-custos` | Premium | Categorias, itens, preços conhecidos, qualidade da estimativa, orçamento |
| GET `/api/churrascos/{id}/exportar?formato=pdf\|csv` | Premium | Download de planejamento; valores estimados identificados; CSV protegido contra fórmulas |
| POST `/api/onde-comprar/churrasco/{id}/comparacao-avancada` | Premium | Compara cestas completas e alternativas verificadas, economia potencial estimada |
| GET `/api/modelos-evento` | Autenticada | Lista modelos do proprietário, inclusive após downgrade |
| POST `/api/modelos-evento` | Premium | Snapshot validado de evento próprio |
| POST `/api/modelos-evento/{id}/usar` | Premium | Novo churrasco pessoal pelo motor determinístico existente |
| DELETE `/api/modelos-evento/{id}` | Autenticada | Exclui modelo próprio inclusive após downgrade |

**Compatibilidade Free:** calculadora, lista de compras, comparação básica,
repetição quando houver cota, exportação integral LGPD, consulta/edição/exclusão
de eventos existentes continuam funcionando. Se um Free já possuía mais de cinco
eventos, eles NÃO são apagados, bloqueados ou convertidos; novas inclusões são
negadas até o uso cair abaixo de cinco. Se o Premium expirar, acontece o mesmo.
A aplicação não depende de esconder botões: o servidor verifica todos os direitos.

**Custo:** preço de referência é estimativa, distinto de oferta atual cadastrada
e de valor efetivamente pago; relatórios parciais não afirmam saldo orçamentário
como completo. Comparação avançada não implica disponibilidade de estoque,
compra realizada ou receita de parceiros. O comparador básico anterior permanece Free.

## Nova migration e rollback

`20261009_0017_modelos_evento_b2c.py` cria somente
`modelos_evento_usuario` (FK CASCADE para o usuário), contendo snapshot JSON,
nome e data. Não altera `churrascos`, `usuarios` nem tabelas de assinatura.
`downgrade()` remove a tabela de modelos (e destrói SOMENTE os próprios
modelos), preservando os eventos originais e os dados de faturamento.
**Não aplicar rollback em produção sem backup de modelos e aprovação explícita.**
O teste MySQL/Alembic do CI executa `alembic downgrade 20260925_0008`
seguido de `alembic upgrade head`; acompanhar o resultado da execução final.

## Cenários de regressão automatizados

`BackEnd/Python/tests/test_entitlements_usuario_fase1.py` cobre:
Free 5 planos, criação negada no sexto, atualização idempotente, reuso negado,
exclusão liberando vaga; acesso negado a recursos Premium via API; exportação
de privacidade livre; Premium com 7 eventos, relatórios, comparação, PDF/CSV;
modelo criado, reusado e acesso próprio; cross-user IDOR; simulação de vencimento
sem exclusão dos dados; tentativa CSRF; exportação CSV segura para planilhas.

Execução recomendada:
```powershell
cd C:\wamp64\www\ChurrasPlan
git switch Saas-ChurrasPlan
git pull --ff-only origin Saas-ChurrasPlan
docker compose --env-file .env -f docker-compose.dev.yml up -d --build
docker compose -f docker-compose.dev.yml exec backend alembic current
docker compose -f docker-compose.dev.yml exec backend pytest -q tests/test_entitlements_usuario_fase1.py
```
O container de desenvolvimento pode não conter pytest (requirements de produção
somente). Alternativa: rodar `pytest` no venv do host com
`BackEnd/Python/requirements-dev.txt`, ou consultar a execução de CI.

## Segurança

- **BOLA/IDOR:** recursos pessoais filtram `usuario_id`; não permitem ler
  arquivo, relatório ou modelo de outra conta.
- **CSRF:** criação, uso e exclusão de modelos e alteração dos eventos usam
  `usuario_atual_com_csrf`; downloads são GET somente leitura.
- **Concorrência:** lock do registro `usuarios` no MySQL abrange verificação
  de limite + inserção + commit na criação autenticada.
- **Stripe:** somente registro TEST reconciliado, com status e prazo válidos.
- **CSV:** strings que iniciam fórmula recebem apóstrofo de segurança.
- **Segredos:** nenhum segredo versionado. PDF gerado no backend sem dados de cartão.

## Pendências fora da Fase 1

Ainda precisam de homologação: processamento de alterações de assinatura em
sandbox externo sob perda de webhooks; cancelamento financeiro antes da exclusão
da conta LGPD; custos de PDF em carga; comportamento sob concorrência pesada no
MySQL; MFA administrativo; backups externos/restore; staging; revisão tributária
e contratos comerciais. A fase 2 do roadmap cobre homologação Billing B2C/B2B.
