# Release Notes — ChurrasPlan v6.3.1

Base: `ChurrasPlan_v6.2.2` fornecido pelo projeto.

## Destaques
- pipeline E2E Playwright;
- MySQL 8.4 real no CI;
- hardening HTTP, rate limiting e auditoria;
- LGPD: consentimentos, exportação e exclusão de conta;
- painel administrativo;
- Docker dev e produção com HTTPS automático por Caddy;
- CI com segurança, containers, MySQL e E2E;
- PWA instalável com cache seguro;
- refinamentos mobile/acessibilidade;
- health/readiness separado;
- migration `20260918_0005`;
- `schema.sql` atualizado para 21 tabelas.

## Compatibilidade
Bancos existentes devem usar `alembic upgrade head`. Não recrie o banco com `schema.sql` se já houver dados.

## Pré-produção
Os documentos legais ainda precisam dos dados reais do controlador e revisão jurídica. SMTP, Google e qualquer provedor de pagamento exigem configuração externa. MySQL real, Docker build e E2E integral devem ficar verdes no CI/staging antes do lançamento.


## v6.3.1 — custo por pessoa e divisão

- custo por pessoa passa a exibir o subtotal conhecido mesmo quando a cesta está parcialmente precificada;
- divisão de custos funciona sobre o subtotal estimado parcial e deixa a base explicitamente marcada como parcial;
- valor real pago continua tendo prioridade quando todo o checklist possui preço real;
- seed demonstrativo passou a cobrir todo o catálogo padrão para desenvolvimento/E2E;
- Docker de desenvolvimento carrega o seed demo por padrão (`LOAD_DEMO_DATA=false` desabilita);
- adicionados scripts `scripts/test_all.ps1` e `scripts/test_all.sh`;
- E2E passa a validar custo por pessoa e alteração da divisão.
