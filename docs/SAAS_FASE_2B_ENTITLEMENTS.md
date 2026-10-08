# Fase 2B — Entitlements B2B sem cobrança

## Gate e limites de escopo
Esta alteração parte do merge da Fase 2A (#7) na branch `Saas-ChurrasPlan`, commit `7eefa3c7ef0811ff9a7aaa742168e792c52d309b`, com **6/6 jobs CI de push + CodeQL Python/JavaScript verdes**.

**Entitlements são executados no backend** para parceiros B2B. O cálculo B2C, listas de compras e navegação pública permanecem gratuitos e sem limites novos. **Checkout, gateway, assinatura faturada, webhook e pagamento permanecem desabilitados.** Não inferir plano pago de `usuarios.plano`, `assinaturas_usuario` ou valores vindos da interface.

## Tiers técnicos e cotas iniciais
Valores **provisórios de capacidade** para piloto técnico, ainda não são oferta comercial, preço, promessa de serviço nem precificação de mercado.

| Tier | Estabelecimentos registrados | SKUs comerciais registrados | Ofertas registradas |
| --- | ---: | ---: | ---: |
| Free | 3 | 100 | 2.000 |
| Pro | 20 | 1.000 | 20.000 |
| Business | 200 | 10.000 | 100.000 |

Contagens incluem registros inativos e histórico de ofertas (não apenas ofertas disponíveis); desativar não libera quota e evita evasão. O limite só impede **nova criação**: registros antigos acima do limite continuam visíveis, editáveis e disponíveis para o planejador. O plano gratuito é o default real para toda organização, inclusive migrada; não há grants automáticos.

Planos Pro e Business **não podem ser comprados** nesta fase. Apenas o administrador global pode registrar uma concessão temporária gratuita (`cortesia_admin`), com data de expiração obrigatória e de no máximo 366 dias, auditada em `auditoria_admin`. Ao expirar ou ser revogada a concessão, o sistema volta imediatamente para Free; não exclui produtos, ofertas, estabelecimentos nem modifica valores históricos.

## Contratos HTTP
- `GET /api/planos/parceiros` (público): Free/Pro/Business, cotas e funcionalidades técnicas, `preco_mensal=null` e `checkout_habilitado=false`. Não confundir com linhas legadas do endpoint `GET /api/planos`.
- `GET /api/parceiro/entitlements`: requer autenticação de parceiro ou admin; seleciona organização pelo mesmo `X-Organizacao-ID` do painel. Retorna `plano`, `fonte`, `limites`, `uso`, `expira_em`, `recursos`, `pagamentos_habilitados=false`. Não aceita `org_id` sem membership ativo. Admin global sem tenant mantém operação administrativa.
- `PUT /api/admin/organizacoes/{id}/concessao`: exige admin global, sessão, CSRF, payload restrito a `free|pro|business`; para Pro/Business exige `expira_em` em ISO 8601 com offset (por exemplo `2026-10-15T13:00:00Z`), futuro e até 366 dias. Enviar `free` sem validade revoga o grant. Registra `concessao_plano_b2b` com `antes/depois` e nunca altera registros financeiros.
- `POST /api/parceiro/estabelecimentos`, `/produtos`, `/precos`: exigem cota somente para a inclusão, após verificar organização e papéis. Ao atingir o limite, retornam HTTP 409 com `detail.codigo="LIMITE_PLANO_ATINGIDO"`, recurso, plano e limites. Validação é **server-side** e não depende de botões/frontend.

## Invariantes de segurança
1. O papel global `parceiro` não permite editar organizações alheias. Contagem é sempre por `organizacao_id` da sessão selecionada, nunca por ID arbitrário da requisição.
2. Escritas usam `SELECT FOR UPDATE` na organização, e leituras correntes de concessão e linhas de uso. Isso serializa criação concorrente no mesmo tenant no MySQL InnoDB; um caso com duas transações disputa a última vaga no CI.
3. Concessões são salvas em `concessoes_organizacao` (migration `20261008_0010`), com um registro por organização, origem exclusivamente administrativa, FK e constraints. Ausência/expiração/registro inválido → Free.
4. Admin sem organização mantém compatibilidade operacional e não é limitado pelas cotas de parceiro; administração com organização selecionada também mantém bypass. Esse privilégio exige CSRF e papel global admin.
5. Nenhuma operação financeira foi introduzida. Registrar cortesia não corresponde a assinatura pagante, receita, checkout ou conversão.

## Testes e migrations
- CI SQLite/API: plano Free default, zero preço/checkout, limites de loja/SKU/ofertas, update de dados antigos acima da cota, isolamento entre tenants, acesso negado sem admin/CSRF, validade e revogação/expiração, audit trail.
- CI MySQL real: schema `concessoes_organizacao`, concorrência de duas inclusões para a última vaga, migrations com dados pré-2A, `alembic check`, downgrade até 0008 e reaplicação até head com preservação do legado.
- CI mantém frontend, segurança, imagens Docker, Chromium E2E e CodeQL.
- Migration não modifica `precos`, `produtos`, `churrascos` nem `usuarios`; rollback destrutivo de `concessoes_organizacao` remove concessões administrativas, então **não executar rollback em produção sem exportar grants e backup**.
- Até existir gateway seguro, nenhum estado no navegador ou valor de `assinaturas_usuario` ativa plano Pro/Business.

## Pendências da Fase 2
Gestão de membros/convites, seletor visual multi-tenant, cotas de membros e filiais, reconciliação de SKU legado com titularidade ambígua, eventos e telemetria de abuso. A Fase 3 trata cobrança, webhooks e ciclo de assinatura real; este PR **não autoriza deploy ou lançamento comercial**.
