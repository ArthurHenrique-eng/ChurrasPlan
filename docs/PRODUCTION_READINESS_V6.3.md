# ChurrasPlan v6.3 — Production Readiness

Esta versão não adiciona um novo “motor de churrasco”; ela endurece a plataforma para testes sérios e posterior publicação.

## Entregas desta etapa

### E2E
- suíte Playwright em `e2e/`;
- fluxo público completo até o resultado;
- cadastro, sessão e área LGPD;
- verificação de manifest/service worker;
- smoke test mobile para overflow horizontal e alvo de toque;
- CI executa os E2E contra **MySQL 8.4**.

### MySQL real
- job dedicado no GitHub Actions com serviço `mysql:8.4`;
- `alembic upgrade head` e `alembic check` contra MySQL;
- testes específicos de charset `utf8mb4`, FKs, cascade, JSON e schema de segurança;
- `sql/schema.sql` alinhado ao ORM no head `20260918_0005`.

> O ambiente usado para preparar este ZIP não possui daemon Docker/MySQL. Por isso a execução MySQL real é automatizada no CI e deve ser repetida em staging antes do lançamento.

### Segurança
- cookies de sessão HttpOnly + Secure em produção;
- CSRF para mutações autenticadas;
- tokens opacos e persistência somente por hash;
- PBKDF2-HMAC-SHA256 com salt aleatório para senhas;
- rate limiting persistido para cadastro/login/recuperação/RSVP;
- IP não é persistido em texto puro nas sessões; usa HMAC quando necessário;
- limite de corpo de requisição;
- headers de segurança, HSTS e Trusted Hosts;
- auditoria de ações administrativas;
- validação de configuração insegura na inicialização;
- CI com `pip-audit` e `bandit`.

### LGPD / privacidade
- aceite versionado de Termos e Política de Privacidade;
- marketing separado e opcional;
- exportação JSON dos dados da conta;
- exclusão autenticada da conta;
- políticas públicas de Privacidade, Termos e Cookies;
- minimização de métricas de parceiros;
- eventos de segurança com retenção configurável.

As páginas legais são uma **base técnica**. Antes de publicação comercial é necessário preencher controlador, CNPJ/razão social, contato do encarregado/canal de privacidade, fornecedores efetivos e obter revisão jurídica.

### Administração
- papel `admin` no backend;
- dashboard administrativo;
- busca e gestão de usuários/papéis/status;
- moderação de estabelecimentos/parceiros;
- trilha de auditoria;
- manutenção de eventos técnicos;
- script seguro para criar/promover o primeiro administrador.

### Docker
- `docker-compose.yml`: desenvolvimento com MySQL + API + frontend;
- `docker-compose.production.yml`: stack isolada com MySQL, backend, frontend e Caddy/HTTPS;
- MySQL e backend não são expostos diretamente na composição de produção;
- migrations rodam antes do processo da API.

### CI/CD
Pipeline em `.github/workflows/ci.yml`:
1. testes backend em SQLite;
2. MySQL 8 real + Alembic;
3. validação frontend;
4. auditoria de dependências e segurança estática;
5. build/validação dos containers;
6. E2E Chromium + MySQL.

Não há etapa automática de deploy para um provedor específico porque ainda não foi escolhido. Adicione-a somente após definir staging/produção e gerenciamento de segredos.

### PWA
- manifest instalável;
- ícones 192/512/maskable;
- service worker;
- cache apenas de páginas públicas/seguras e assets estáticos;
- `/api` nunca é cacheada pelo service worker;
- páginas autenticadas não são usadas como fallback offline;
- tela de indisponibilidade e estado online/offline.

A v6.3 **não promete sincronização offline de mutações**. Checklist, conta e outras escritas continuam exigindo conexão para persistência no servidor.

### Mobile
- safe areas;
- inputs com tamanho que evita zoom acidental em iOS;
- alvos de toque mínimos;
- grids convertidos para uma coluna;
- tabelas administrativas responsivas;
- barras de ação adaptadas;
- redução de movimento respeitada.

## Critério para publicação

Antes de aceitar usuários reais:
1. CI integralmente verde;
2. staging com MySQL da mesma família/versão da produção;
3. domínio + HTTPS reais;
4. SMTP real testado;
5. backup e restauração validados;
6. documentos legais preenchidos/revisados;
7. conta admin inicial criada e senha armazenada em gerenciador de segredos;
8. chaves Google restritas por domínio/API quando a integração for ativada;
9. monitoramento/alertas externos configurados;
10. teste E2E final no domínio de staging.
