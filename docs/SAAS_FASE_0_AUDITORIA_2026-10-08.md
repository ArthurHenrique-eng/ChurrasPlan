# ChurrasPlan SaaS B2B2C — Fase 0: auditoria técnica e baseline

Data da inspeção: 2026-10-08. Branch auditada: `main` e `Saas-ChurrasPlan`, ambas em `2afa7b0a0780d2c6090b2d2677b6e1b799958d90`. Fonte: árvore e conteúdo do repositório no GitHub, configuração de ruleset e execução de Actions. **Este documento descreve evidências de código e CI, não comprova funcionamento em produção.**

## 1. Inventário do estado atual

- **Backend**: FastAPI, SQLAlchemy, Pydantic, autenticação por sessão/CSRF; `BackEnd/Python/main.py`, `routers/`, `services/`, `models/`, `schemas/`.
- **Persistência**: MySQL 8.4 na integração/produção, SQLite em testes unitários; migrations versionadas de `20260917_0001` a `20260925_0008` em `BackEnd/Python/alembic/versions/`. A migration 0007 carrega catálogo genérico ampliado e a 0008 garante o catálogo de planejamento.
- **Frontend**: HTML/CSS/JS sem framework, PWA e service worker; `FrontEnd/`, `FrontEnd/js/`, `FrontEnd/sw.js`.
- **Recursos existentes**: planejamento e cálculo determinístico, listas, preços estimativos, convites/RSVP, login e privacidade, painel básico de parceiros, cadastro de estabelecimentos/SKUs, mapa/Geoapify, administração.
- **Infraestrutura**: `docker-compose.dev.yml`, `docker-compose.prod.yml` (override) e `docker-compose.production.yml` (stack com Caddy), Dockerfiles, `.github/workflows/ci.yml`, `deploy/Caddyfile`.
- **Qualidade**: `BackEnd/Python/tests/`, `tests_mysql/`, `e2e/`; CI com seis jobs incluindo segurança e browser E2E.

## 2. Evidência real do baseline

GitHub Actions: [execução 36183631867](https://github.com/ArthurHenrique-eng/ChurrasPlan/actions/runs/36183631867), 2026-09-25, evento `push`, commit `2afa7b0a`, conclusão `success`.

| Job | Resultado confirmado | Evidência |
| --- | --- | --- |
| Backend unit/integration (SQLite) | aprovado; **98 passed, 2 warnings** | log do job `108231658908` |
| MySQL 8 real + Alembic | aprovado; **4 passed**; `alembic upgrade head` e `alembic check` executados no workflow | log do job `108231659289` |
| Frontend static checks | aprovado (sintaxe JS e referências) | job `108231659234` |
| Security audit | aprovado; `pip-audit` relatou “No known vulnerabilities found” naquele run | job `108231659393` |
| Docker configuration and images | aprovado | job `108231659385` |
| E2E Chromium + MySQL | aprovado; 5 funções `test_*` no arquivo de cenário | job `108232031982`; `e2e/test_churrasplan_e2e.py` |

**Limites da evidência:** testes acima são históricos, do commit inicial; não são testes recém-executados neste PR, nem demonstram um pagamento real, restauração de backup ou isolamento multi-tenant. A branch `Saas-ChurrasPlan` não tinha execuções próprias de Actions na inspeção. A execução nova de CI neste PR é condição para encerrar a Fase 0. O ambiente de análise local não tinha Docker nem acesso de rede ao GitHub; os logs anteriores foram consultados pelo conector autenticado.

## 3. Diagnóstico dos 30 blocos do prompt mestre

Legenda: **Parcial** = evidência de parte do domínio, sem aceitar o fluxo completo; **Ausente** = sem implementação de domínio correspondente na árvore auditada; **A verificar** = implementação presente, ainda sem validação específica do critério. Prioridades P0 (estabilidade/segurança), P1 (SaaS monetizável), P2 (expansão após núcleo confiável).

| # | Bloco | Situação / evidência concreta | Lacuna ou risco / próximo critério | Prioridade; fase |
| --- | --- | --- | --- | --- |
| 01 | Billing | **Parcial** — `models/assinatura.py`; `routers/planos.py` retorna `pagamentos_habilitados: False` | Checkout, gateway, webhook autenticado, ciclo financeiro, reconciliação e renovação não demonstrados; testes de idempotência | P1; 3 |
| 02 | Entitlements | **Ausente** como serviço centralizado; campo `recursos` no modelo de plano | Verificações no backend e contadores concorrentes; acesso direto não pode furar cotas | P1; 2 |
| 03 | Posicionamento | **Parcial** — `README.md`, `FrontEnd/index.html` apresentam planejador | Narrativa B2B2C e benefícios concretos por público ainda não publicados/verificados | P1; 5 |
| 04 | Planos Free/Pro/Business | **Parcial** — `PlanoAssinatura`, endpoint de planos | Matriz configurável de funcionalidades, públicos e limites com imposição por API | P1; 2–3 |
| 05 | Multi-tenant | **Ausente** — `Estabelecimento.usuario_responsavel_id`, sem modelos de organização/membros | Organizações, papéis, filiais, migração de titularidade e testes IDOR/BOLA | P1; 2 |
| 06 | Leads/CRM | **Ausente** no conjunto de routers/modelos | Formulário/landing, lead, CRM mínimo, antispam, separação de consentimento | P1; 5 |
| 07 | SEO | **Parcial** — HTML público existente; sem `robots.txt` e `sitemap.xml` na árvore | Metadados, páginas úteis, canonical, sitemap e validação em dispositivos | P2; 5 |
| 08 | Referral | **Parcial** — `routers/convites.py`, RSVP/compartilhamento | Atribuição privada de novos cadastros sem vazar dados dos convidados | P2; 5 |
| 09 | Product analytics | **Parcial** — `models/metrica_estabelecimento.py` agrega descoberta | Catálogo de eventos, instrumentação de funis B2C/B2B, retenção limitada | P1; 5 |
| 10 | IA no desenvolvimento | **Ausente** — sem `AGENTS.md` e instruções dedicadas na árvore | Guardrails para cálculos, migrações, segurança e revisão de código | P2; 6 |
| 11 | Supply chain | **Parcial** — `pip-audit` e Bandit no `ci.yml` | Sem arquivos Dependabot/CodeQL na árvore; governança de Actions e imagens | P0; 1 |
| 12 | Proteção CI/branch | **Parcial e configuração a corrigir** — ruleset `ChurrasPlanProtect` (id 23958344) ativo, porém `conditions.ref_name.include=[]` e `required_status_checks=[]`; endpoint de `main` informa `protected=false` | Verificar incidência real das regras e exigir os 6 jobs; modificação das proteções depende de configuração administrativa autorizada | P0; 1 |
| 13 | IA no produto | **Ausente** — sem serviço/provedor de LLM identificado | Extração estruturada/Pydantic, limites de custo, fallback determinístico | P2; 6 |
| 14 | Observabilidade | **Parcial** — request ID em `middleware/security.py` e health/readiness em `main.py` | Logs estruturados, erros, métricas, monitoramento/alertas e redaction | P0; 1 |
| 15 | Filas | **Ausente** — `services/auth.py` tem envio de e-mail por SMTP; sem outbox/worker na árvore | Entrega confiável de e-mail/webhooks e reprocessamento sem novos serviços prematuros | P2; 6 |
| 16 | Geoapify | **Parcial** — `services/geoapify.py` com `urllib`, timeouts e tratamentos a revisar | Cache, fallback, limites, indisponibilidade e privacidade testados | P0; 1 |
| 17 | Backup/restore | **Ausente** como procedimento validado no repositório | Runbook, retenção, criptografia e teste de restauração isolada | P0; 1/7 |
| 18 | MFA | **Ausente** no auth atual (`services/auth.py` e `models/auth.py`) | MFA obrigatório em operações privilegiadas + recuperação segura e testes | P0; 1 |
| 19 | CSP/frontend | **Parcial** — `FrontEnd/nginx.conf` já contém CSP; `middleware/security.py` contém headers | Auditar diretivas legadas do Google Maps, CSP efetiva, PWA, XSS/CSRF | P0; 1 |
| 20 | Parceiros escaláveis | **Parcial** — `routers/parceiros.py`, `FrontEnd/js/parceiro.js`, migrations 0007/0008 | Importação em massa, catálogo, filiais e UX integrada; validar regressões de cadastros | P0; 1 / P1; 4 |
| 21 | Métricas B2B | **Parcial** — `MetricaEstabelecimento` e dashboard de parceiro | CTR por período, deduplicação, impacto por filial/campanha sem simular vendas | P1; 4 |
| 22 | Marketplace assistido | **Parcial** — `routers/onde_comprar.py`, `services/otimizacao.py`, modelos de preços | Separar estimativa, oferta, preço vencido e disponibilidade; validação ponta a ponta | P1; 4–5 |
| 23 | Docs/Compose | **Defeito identificado** — README cita `docker-compose.yml` e `docker compose up`; a árvore contém somente `docker-compose.dev.yml`, `docker-compose.prod.yml` e `docker-compose.production.yml` | Corrigir comandos e matriz de ambientes; reproduzir instalação limpa | P0; 1 |
| 24 | Deploy | **Parcial** — Dockerfiles, Caddy, dois ambientes Compose | Staging, rollback/smoke tests, monitoramento e custos atuais não verificados | P1; 7 |
| 25 | Testes SaaS | **Parcial** — pytest SQLite/MySQL, Playwright, CI seis jobs | Testes de organizações, webhook, billing, MFA, importação, carga e regressões E2E comerciais | P0; todas |
| 26 | Leads e consentimento | **Parcial** — `routers/privacidade.py`, consentimento de marketing no cadastro | Funil de leads separado e descadastro promocional operacional | P1; 5 |
| 27 | Piloto regional | **Ausente** como fluxo dedicado | Onboarding, feedback e métricas de disposição a pagar; clientes reais são externos | P2; 7 |
| 28 | Dashboard fundador | **Parcial** — `routers/admin.py` tem contagens técnicas | Funis, receitas verificadas, MRR/churn e fórmulas documentadas | P1; 5 |
| 29 | Profissionalização GitHub | **Parcial** — README, CI, documentação `docs/` | `SECURITY.md`, `CONTRIBUTING.md`, template de PR, roadmap e runbooks | P1; 0/1/7 |
| 30 | Arquitetura B2B2C | **Parcial** — módulos B2C, parceiro e admin presentes | Compartilhamento seguro com orgs, entitlements e billing integrado; testes intersegmentos | P1; 2–7 |

Arquivos citados neste relatório são relativos a `BackEnd/Python/` quando mencionados como `models/`, `routers/`, `services/` ou `middleware/`.

## 4. Regressões relatadas: achados e testes necessários

1. **Coordenadas**: `schemas/estabelecimento.py::_normalizar_coordenada` converte automaticamente inteiros grandes dividindo por 1.000.000. Os testes existentes confirmam `-19959383 -> -19.959383`. Embora o erro de validação anterior possa não ocorrer nesse caminho, a conversão implícita viola a exigência de não interpretar coordenadas ambíguas sem origem comprovada. A Fase 1 deve estabelecer contrato explícito (graus decimais, formato brasileiro e dados de geocodificação identificados por origem), rejeitar coordenadas inválidas e ajustar testes/API/frontend de parceiro e admin sem perder registros.
2. **Produto genérico**: `migrations 0007/0008` inserem catálogo, `routers/produtos.py` permite filtro `tipo_produto`, `FrontEnd/js/parceiro.js` carrega `tipo_produto: "generico"`. A existência das peças não comprova que o seletor funcione em instalação antiga, sem migração aplicada ou após erro HTTP. Adicionar integração MySQL + Playwright de cadastro de produto; tratar explicitamente vazio, erro e carregamento.
3. **Preços**: `services/precos_referencia.py` contém referência BR-2026-09; `routers/churrascos.py` aplica fallback e `FrontEnd/js/resultado.js` sinaliza fonte. `test_production_readiness.py` e `test_fases_3_a_6.py` incluem regressões. Verificar que todas as combinações de itens/alias/embalagem têm preço estimado ou aviso claro; não inventar ofertas reais.
4. **Matemática**: há testes de cálculo de carne, bebida, extras, integração, custos e divisão. Preservar invariantes entre necessidade física, quantidade comercial e custo; adicionar fixtures douradas para os caminhos afetados.

## 5. Riscos e dependências que impedem lançamento

**Críticos**: falta de isolamento organizacional; ausência de cobrança autenticada e reconciliação; admins sem MFA; ausência de verificação de restauração; proteções/checks obrigatórios não efetivos; possíveis regressões de cadastro e visualização. O CI histórico verde não reduz por si só esses riscos de produto.

**Externos**: conta de gateway em sandbox/produção, contrato e credenciais; domínio e infraestrutura; proteção administrativa de branches/rulesets; SMTP/monitoramento/backup em produção; revisão jurídica e fiscal no Brasil; parceiros reais no piloto. Não são equivalentes a código entregue.

**Mudanças de banco**: nenhuma na Fase 0. Toda fase com migrations deverá documentar objetivo, esquema, índices, constraints, preservação de dados, plano de rollback e teste em MySQL.

## 6. Critérios de aceite e limite desta fase

- [x] Commit inicial das duas branches identificado.
- [x] Árvore e camadas principais inspecionadas, com inventário e diagnóstico dos 30 blocos.
- [x] Resultado histórico do CI do commit inicial verificado pelos logs.
- [x] Riscos P0 e dependências mapeados; roadmap por fases proposto.
- [ ] CI **deste PR** aprovado (aguarda execução GitHub Actions após abertura).
- [ ] PR revisado e integrado à `Saas-ChurrasPlan` antes da próxima fase.

**Fase 0 não altera código de negócio e não encerra nenhuma das 30 frentes de implementação.** É a linha de base para executar P0 com PRs seguintes, auditáveis e reversíveis. Não atribuir notas de maturidade sem validação operacional.
