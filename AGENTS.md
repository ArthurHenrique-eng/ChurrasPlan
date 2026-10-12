# Engenharia do ChurrasPlan

Trabalhe na branch indicada pelo mantenedor. A memória canônica é `docs/ChurrasPlanSaaS.md`; leia-a antes de alterar o código. Não crie notas concorrentes de fases em docs/.

- Preserve o monólito modular FastAPI/SQLAlchemy/MySQL e o frontend/PWA existente.
- Mantenha necessidade física, compra comercial e custo separados; cálculos determinísticos nunca são delegados a IA.
- Novos dados persistentes exigem migration Alembic reversível, índices/constraints, testes MySQL, atualização de schema.sql e memória técnica.
- Cada leitura/escrita B2B valida organização e papel no backend. IDs da interface não concedem acesso. Cotas usam lock até commit.
- Mutações autenticadas exigem CSRF. Admin em produção exige MFA validado. Senhas novas usam Argon2id; hashes PBKDF2 legados são atualizados no login.
- Não registre credenciais, tokens, cookies, corpos, coordenadas ou dados pessoais nos logs. Não exponha chaves no frontend.
- Não transforme referência de orçamento em oferta real, intenção em venda ou faturamento de sandbox em receita.
- Provedor de pagamento exige webhook autenticado, idempotência e snapshot remoto. O redirecionamento de checkout não ativa direitos.
- Preserve acesso aos dados antigos após downgrade. Evite sementes demonstrativas em produção.
- Rode testes backend, scripts frontend, schema parity, Alembic/MySQL e E2E para fluxos modificados. Confira CI/CodeQL da revisão entregue.
- Descreva alterações, evidências e gates externos na memória técnica. Não declare produção pronta sem restore, staging, SMTP, credenciais e configuração reais.
