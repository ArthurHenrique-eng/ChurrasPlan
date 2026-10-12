# ChurrasPlan SaaS B2B2C — Memória técnica mestra

> **Documento canônico:** `docs/ChurrasPlanSaaS.md`. **Branch:** `Saas-ChurrasPlan`, nunca confundir com `main`.
> **Atualizado:** 12/10/2026 (UTC). **Base histórica auditada:** commit `208f34954033dc7bb280bdaa72194ba1e37d854c`. **Revisão de lançamento:** API v6.10.0, Alembic head `20261012_0023`; implementação/evidências/gates na seção 19.
> **CI comprovado no commit-base:** [GitHub CI 38004031754](https://github.com/ArthurHenrique-eng/ChurrasPlan/actions/runs/38004031754) e [CodeQL 38004031832](https://github.com/ArthurHenrique-eng/ChurrasPlan/actions/runs/38004031832), ambos success em 09/10/2026; esse resultado não avalia o novo commit documental.
> **Objetivo:** consolidar as **35 notas Markdown** pré-existentes em `docs/` num único contexto de leitura. Os originais permanecem recuperáveis por links imutáveis no Git, listados na seção de histórico, sem manter arquivos obsoletos concorrentes. O README e imagens de `docs/assets/` são preservados.

## 0. Como uma IA deve usar e manter este documento

1. **Ler este arquivo primeiro**, depois o README e os arquivos relevantes de implementação; não confundir memória documental com código executável.
2. **Hierarquia de evidências:** código, migrations e testes da branch examinada > CI e configuração efetiva > este documento > notas históricas > intenção relatada em conversa. Documentar divergências; nunca apagar fatos antigos sem registrar a correção.
3. **Estados de entrega:** IMPLEMENTADO (verificável no repositório), VALIDADO (com teste/ambiente e data explícitos), RELATADO LOCALMENTE (informado pelo desenvolvedor, mas não visto na branch), EM DESENVOLVIMENTO e PLANEJADO. Nunca marcar como pronto apenas porque a rota, tabela ou documentação existe.
4. Antes de qualquer mudança: identificar o commit/branch, investigar dependências, preservar compatibilidade, migrar schema com Alembic, atualizar testes e **atualizar esta memória** com evidência, riscos e próximos passos.
5. **Nunca registrar segredos**, senhas, chaves, tokens, dados pessoais reais ou detalhes de clientes neste arquivo. Usar nomes de variáveis e valores ilustrativos.
6. Mudanças de arquitetura ou requisito devem ser registradas em seções temáticas, não em novos arquivos Markdown de progresso sob docs/. Registrar decisões e mudanças nas seções 15 e 16; evitar repetição e contradições.
7. Não substituir conceitos precisos do domínio por simplificações que percam unidades, arredondamentos, rastreabilidade, autorização ou estados de preço.

## 1. Identidade e proposta de valor

**ChurrasPlan** é um aplicativo web full stack brasileiro para planejar churrascos de ponta a ponta: dimensionamento de participantes, carnes/bebidas/acompanhamentos/insumos, restrições alimentares, orçamento, lista de compras, custo por pessoa, divisão de despesas, histórico, convites/RSVP e escolha de estabelecimentos. A evolução pretendida é um **SaaS B2B2C**:

- **B2C:** organizadores e convidados de churrascos; estimativas transparentes, conveniência e fluxo de planejamento.
- **B2B:** supermercados, açougues e parceiros comerciais; cadastro de estabelecimentos, produtos/SKUs, preços/ofertas e métricas agregadas.
- **Operação da plataforma:** administradores, moderação de parceiros, gestão de usuários, políticas, assinatura e cobrança futura.
- **Monetização pretendida:** planos e benefícios de assinatura, ativação comercial de parceiros e integrações de cobrança. A monetização completa NÃO é inferida de modelos/tabelas existentes.

Princípio central: o backend é a fonte de verdade de cálculos, persistência, identidade e autorização; o frontend coleta entradas, apresenta resultados e administra a interação. Preços de referência e ofertas reais têm semânticas diferentes.

## 2. Stack e organização na branch SaaS

| Camada | Stack e responsabilidades atuais |
|---|---|
| Frontend | HTML/CSS/JavaScript modular e PWA em `FrontEnd/`, SW e MapLibre GL |
| API | FastAPI, API v6.10.0, Pydantic, SQLAlchemy; `BackEnd/Python/main.py`, `routers/`, `schemas/`, `services/` |
| Persistência | MySQL 8.4 em Docker/CI, SQLite para unidade; Alembic até `20261012_0023` |
| Tenant B2B | `models/organizacao.py`, `routers/parceiros.py`, `equipe.py`, `operacao_b2b.py`, `comercial_b2b.py` |
| Direitos | `services/entitlements.py` (B2B) e `entitlements_usuario.py` (B2C) |
| Stripe TEST | `routers/billing.py`, `billing_usuario.py`, `services/billing.py`, `billing_usuario.py` |
| Infra | `docker-compose.dev.yml`, `docker-compose.production.yml`, Nginx, Caddy, CI, CodeQL e Dependabot |

**B2C:** Home → planejamento → carnes/bebidas/extras → resultado/checklist → histórico/convites/RSVP → Onde comprar → conta/planos/benefícios. Calculadora física e comercial é determinística no backend, não no frontend.

**B2B:** parceiro → organização/membros → seleciona tenant → filiais → genéricos/SKU → ofertas/CSV → campanhas moderadas → relatórios e cobrança Test organizacional. Admin global é distinto de proprietário/gestor local.

**Contratos base:** `GET /api/health` e `GET /api/health/ready`; documentação OpenAPI em `/docs` quando exposta. Monólito modular, preferível a microserviços sem necessidade comprovada.

## 3. Modelo de domínio e regras matemáticas invariantes

### 3.1 Pessoas e escolhas

Entradas contemplam homens adultos, mulheres adultas, crianças, quantos adultos consomem álcool, duração, tipo de evento, perfil de consumo, seleção de carnes/bebidas/itens extras, restrições e opções vegetarianas/veganas. A soma de pessoas deve respeitar o limite do contrato de negócio (**até 500**, conforme revisão v0.2); a duração foi alinhada a **1–48 horas** na revisão frontend v2.3. Confirmar validações vigentes antes de alterar limites.

Restrições alimentares e seleções explícitas devem repercutir no cálculo. Bebida alcoólica é desabilitada quando não há consumidores adultos correspondentes; não permitir quantidade de consumidores de álcool maior que adultos do grupo.

### 3.2 Separar necessidade, compra, oferta e pagamento

Fluxo obrigatório:

~~~text
Escolhas do evento
  → quantidade_necessaria (unidade de consumo)
  → arredondamento comercial do produto (embalagem/incremento)
  → quantidade_compra (quantidade física coberta pela compra)
  → quantidade_embalagens, quando aplicável
  → oferta/preço por unidade_venda
  → subtotal_estimado (snapshot histórico do planejamento)
  → valor_pago real no checklist (quando informado)
~~~

**Invariantes:**
- quantidade_necessaria **não** é embalagem.
- quantidade_compra **não** é contagem de pacotes; é a quantidade física coberta, na unidade de consumo.
- quantidade_embalagens armazena a contagem comercial quando a venda é fechada.
- preco_unitario corresponde à unidade_venda do produto.
- subtotal_estimado é calculado sobre **compra comercial**, e não apenas necessidade teórica; valores monetários são DECIMAL/Numeric, não FLOAT.
- Nunca misturar litros de cerveja com número de latas; o exemplo do catálogo é lata de 350 ml. Carvão padrão é saco de 3 kg, água garrafa de 1,5 L e gelo saco de 5 kg.
- Para venda fracionada, aplicar o incremento específico do produto; não aplicar arbitrariamente um pacote global de 2 kg a todas as carnes.
- O usuário precisa selecionar explicitamente extras como gelo; o tipo de evento e perfil influenciam coeficientes; coeficientes personalizados, como carvão por kg de carne, devem ser realmente usados.
- GET/POST/PUT devem conservar significado e snapshot do mesmo item; alterações futuras em catálogo/oferta não reescrevem históricos.
- Churrascos possuem chave_cliente de idempotência; recarregar a página de resultado não deve gerar novo evento.
- A oferta atual de um estabelecimento é a observação mais recente elegível; histórico de observações é separado da seleção de oferta atual.

**Onde estão as regras:** services/calculo_carne.py, calculo_bebidas.py, calculo_extras.py, calculo_precos.py, utils_calculo.py, catalogo_produtos.py e schemas/routers correspondentes. Não inventar coeficientes ou fórmulas sem auditar esses arquivos.

### 3.3 Orçamento completo, parcial e divisão

- Sem qualquer preço elegível/referência: não inventar custo nem habilitar divisão fictícia.
- Precificação **parcial:** exibir subtotal conhecido, custo por pessoa e divisão identificados como parciais.
- Precificação **completa:** estimativa total, custo por pessoa e divisão sobre a base completa.
- Quando o checklist contém valores reais para todos os itens, o total efetivamente pago tem prioridade como base de divisão.
- A flag estimativa_precos_completa distingue os estados. Economia real requer conjuntos comparáveis completos.

A correção v6.3.1 eliminou o comportamento antigo de ocultar custo por pessoa/divisão se faltasse uma única oferta. Usar testes de regressão para não reintroduzir isso.

## 4. Catálogo, referências de preço e ofertas

**Produto genérico ≠ SKU comercial.** A calculadora dimensiona o genérico (ex.: cerveja); o parceiro anuncia produto comercial com produto_pai_id, marca, variante, fabricante, EAN, SKU, embalagem, unidade de venda, venda fracionada e incremento.

O catálogo permite categorias amplas para parceiros (carnes, bebidas, mercearia, laticínios, padaria, hortifruti, congelados, limpeza, higiene, descartáveis etc.). A revisão de setembro/2026 expandiu genéricos; a migration **20260925_0008** garante catálogo básico do planejador em instalações novas. O catálogo de planejamento documentado historicamente tinha **49 itens**, incluindo **23 carnes**; verificar contagens na instalação real.

**Prioridade de fonte de preço para planejar:**
1. Oferta real, atual e elegível de estabelecimento ativo/verificado.
2. Preço de referência nacional de planejamento (**BR-2026-09**, quando o slug está coberto).
3. Item sem preço, com sinalização de estimativa parcial/incompleta.

Preços de referência não são ofertas de lojas, não entram no ranking de estabelecimentos e não são garantia de preço atual. O arquivo de referência contém valores estimativos nacionais por unidade/embalagem (e aliases para frango-generico e linguica-generica). O seed demonstrativo em scripts/seed_demo.py é para desenvolvimento/E2E e **não representa preço comercial real**.

Fontes de calibração originalmente registradas: [PROCON Joinville 2026](https://www.joinville.sc.gov.br/publicacoes/pesquisas-de-precos-procon-churrasco-2026/), [PROCON Patos/PB](https://patos.pb.gov.br/noticias/proconpatos-divulga-preco-a16419.html), [Neogrid](https://neogrid.com/noticias/churrasco-e-bebidas-ficam-caros-na-copa/) e [Carrefour](https://mercado.carrefour.com.br/). Recalibrar com data/fonte e testes ao atualizar referências.

**Publicação de ofertas:** ofertas de estabelecimentos não verificados não devem aparecer como recomendações públicas válidas. Histórico de preço, atualidade, validade, embalagem e disponibilidade precisam ser respeitados; evita-se associar fontes externas de localização a preços inexistentes.

## 5. Usuários, convidados, parceiros e administração

**Papéis:** usuario (planejamentos e dados próprios), parceiro (dados próprios + operação comercial dos seus estabelecimentos), admin (gestão e moderação). Cada permissão tem de ser verificada no **backend**, não apenas pela visibilidade de botões.

**Conta:** cadastro, login/logout, verificação de e-mail, recuperação de senha, sessão por cookie, proteção CSRF, histórico, repetir churrasco, consentimentos e direitos de privacidade.

**Convites/RSVP:** o organizador compartilha convite; convidado responde sem conta. Atualização/idempotência de RSVP e segredo de edição do próprio convidado devem manter seus limites de autorização; não expor o segredo de edição ao organizador.

**Parceiro B2B:** cadastro e gestão de estabelecimentos, catálogo comercial e ofertas; painel de parceiro com métricas agregadas de visualização/clique, sem identificação de usuário/churrasco/sessão/IP/coordenadas. Essas métricas não são prova antifraude apta a cobrança por clique/impressão. Moderação pelo administrador antes de publicação externa elegível.

**Admin:** painel, gestão de contas/papéis/status, moderação de estabelecimentos, auditoria e manutenção de eventos técnicos. Senha em hash, nunca recuperável em claro. O helper Windows scripts/set_admin.ps1 solicita senha de modo seguro, ativa/verifica admin e revoga sessões ao redefinir a senha; scripts/create_admin.py é alternativa por linha de comando com cuidados contra vazamento.

## 6. Onde comprar, otimização e Geoapify

O subsistema combina **estabelecimentos e preços próprios/verificados** com **descoberta geográfica externa opcional**:

- Geoapify Places API: estabelecimentos próximos; Geoapify Address Autocomplete: busca por endereço; Map Tiles Geoapify com dados OpenStreetMap.
- Mapa visual atual utiliza **MapLibre GL** (confirmado em FrontEnd/js/onde-comprar.js), com atualização de pontos no movimento/zoom.
- O backend executa chamadas externas e encaminha tiles; **GEOAPIFY_SERVER_API_KEY nunca deve ser devolvida ao navegador**. Variáveis principais: GEOAPIFY_ENABLED e GEOAPIFY_SERVER_API_KEY.
- Localização por navegador requer autorização do usuário; busca de endereço funciona como alternativa. Coordenadas devem obedecer latitude −90…90 e longitude −180…180, com graus decimais corretos (não confundir valores escalados por 10^6).
- Resultados externos devem ser rotulados como Geoapify/OpenStreetMap; não viram ofertas próprias, nem fontes de preços automaticamente.
- Comparação/otimização contemplam preço, distância, avaliação/equilíbrio e múltiplos estabelecimentos, mas só precificam usando ofertas próprias elegíveis.
- Sem Geoapify configurada, estabelecer fallback para lojas internas e otimização sem camada de mapa/descoberta externa.

**Nota histórica importante:** a v6.4 descrevia Google Maps/Places opcional. A v6.5 o substituiu por Geoapify. A release note antiga de v6.5 citava Leaflet e chave pública separada, mas o **código atual** usa MapLibre e tiles proxied pelo backend com uma chave de servidor. Não reintroduzir Google/Leaflet por leitura descontextualizada das notas antigas.

## 7. Autenticação, segurança, LGPD e limites do PWA

**Controles implementados:** senhas novas em Argon2id e migração de hashes PBKDF2 legados no login; segredos de sessão e tokens opacos persistidos somente por hash; cookie churrasplan_session HttpOnly, SameSite=Lax e Secure em produção; cookie churrasplan_csrf para o frontend; checagem CSRF em mutações autenticadas; rate limiting com identificadores HMAC; headers de segurança/HSTS; CORS e Trusted Hosts explícitos; limite de payload; auditoria admin; validação de configuração de produção; pip-audit e bandit em CI.

**LGPD técnica:** termos/privacidade versionados, aceite de documentos, marketing opcional e separado, exportação JSON e exclusão autenticada/reconfirmada da conta. Dados pessoais envolvidos: cadastro, churrascos salvos, respostas de convidados, restrições voluntárias, dados comerciais e registros técnicos mínimos. Sem cookies de publicidade/analytics habilitados por padrão na base documentada.

**PWA:** manifest, ícones 192/512/maskable, service worker, cache controlado apenas para assets/páginas públicas, fallback offline e indicador de conectividade. **Não** cachear respostas /api nem páginas privadas como fallback. Não existe sincronização offline garantida para escritas, checkout, conta ou checklist.

**Pendências legais/operacionais para produção comercial:** definir controlador/razão social/CNPJ, canal de privacidade e encarregado quando aplicável; bases legais e prazos de retenção; subprocessadores reais e acordos; resposta a incidentes e titulares; backups/retenção; política pública revisada juridicamente. Controles técnicos não equivalem a conformidade organizacional concluída.

## 8. SaaS Stripe TEST e direitos dos planos

**No código SaaS (não na main):** estão implementados Checkout, portal, webhook, reconciliação, faturas e assinaturas Stripe **Test/Sandbox** para usuário Premium e organizações Pro/Business. **Não** há cobrança Stripe Live habilitada. O backend recusa `sk_live_`; `BILLING_ENABLED` é desligado por padrão. A configuração aceita `STRIPE_SECRET_KEY=sk_test_...` ou uma chave restrita Test `rk_test_...`, `STRIPE_WEBHOOK_SECRET=whsec_...` e Price IDs do sandbox, sem versionar segredos.

### Planos mensais configurados e verificados contra Price IDs

| Público | Plano interno | Preço mensal alvo aprovado | Configuração Stripe Test |
|---|---|---:|---|
| Consumidor Premium | `premium` | R$ 9,90 | `STRIPE_PRICE_USER_PREMIUM_MONTHLY` e `STRIPE_EXPECTED_PREMIUM_MONTHLY_CENTS=990` |
| Mercado Básico | `pro` | R$ 49,90 | `STRIPE_PRICE_PRO` e `STRIPE_EXPECTED_PRO_MONTHLY_CENTS=4990` |
| Mercado Pro | `business` | R$ 99,90 | `STRIPE_PRICE_BUSINESS` e `STRIPE_EXPECTED_BUSINESS_MONTHLY_CENTS=9990` |

Preço vem do Stripe Test e é validado no servidor: modo teste, moeda BRL, Price `price_` ativo, recorrência/intervalo compatível e valor esperado; conflito entre IDs ou Price divergente resulta em HTTP 503. Anuais ficam indisponíveis até configurar IDs e `STRIPE_EXPECTED_*_YEARLY_CENTS` positivos, comercialmente aprovados. `prod_` não é Price ID.

**Entitlements pessoais:** `assinaturas_stripe_usuario` reconciliada com status `active` e período futuro é a única fonte de Premium; `usuarios.plano` e `assinaturas_usuario` legados não dão direito. Free permite até **5 eventos novos salvos**; Premium libera ilimitados, exportação PDF/CSV, modelos reutilizáveis, análise de custos e comparação avançada. Usuário Free após downgrade mantém acesso/edição aos registros anteriores, mas não cria novos acima do limite. Criar, repetir ou vincular consome quota; atualização idempotente não. `GET /api/planos/meus-beneficios` devolve direitos, limites e uso.

**Entitlements B2B:** organizações começam em Free; Pro/Business derivam de assinatura Stripe Test reconciliada e vigente ou cortesia administrativa válida e auditada. `services/entitlements.py` aplica quotas no backend, por tenant, inclusive sob concorrência. Somente `proprietario` local contrata/cancela/troca plano empresarial. Gestor/editor/leitor não acessam faturamento alheio. Ter cartão ou link de checkout não altera o tier; é o estado reconciliado que autoriza.

**B2B APIs:** `GET /api/billing/planos-publicos`, `/catalogo`, `/assinatura`, `/faturas`; `POST /api/billing/checkout`, `/sincronizar`, `/portal`, `/cancelar`, `/reativar`, `/trocar-plano`. **B2C APIs:** `GET /api/billing/usuario/catalogo`, `/assinatura`, `/faturas`; `POST /api/billing/usuario/checkout`, `/sincronizar`, `/portal`, `/cancelar`, `/reativar`, `/trocar-periodo`. Mutações privadas exigem sessão, titularidade e CSRF.

**Webhook único:** `POST /api/billing/webhook` valida assinatura HMAC SHA-256 e timestamp, deduplica ID de evento e consulta snapshot Stripe atual; evita ativação por replay, checkout incompleto, Price estranho, tenant divergente e eventos fora de ordem. `active` e período vigente concedem benefício. `past_due` suspende Premium B2C; B2B pode ter grace period limitado a `BILLING_GRACE_DAYS` (máximo 7). `canceled/unpaid/paused/incomplete` não ativam pagos. Cancelamento ao fim do período mantém benefícios enquanto vigente; renovação, troca e reativação passam pelo Stripe, não por flags frontend.

**Navegação:** Premium redireciona a `minha-conta.html?assinatura=retorno`; parceiro a `minha-conta.html?cobranca=retorno&organizacao_id=ID`. Portal retorna à conta. `PUBLIC_APP_URL` deve ser a origem correta, com fluxo de login que conserva retorno permitido.

**Status de homologação:** as notas de 09/10 documentam testes automatizados com transporte simulado e pedem comprovação externa do sandbox. O mantenedor informou posteriormente que **concluiu** um fluxo Premium real no Sandbox, com benefícios/reconciliação e retorno corrigido via `PUBLIC_APP_URL`. Registre como **CONCLUÍDO CONFORME RELATO DO MANTENEDOR, sem comprovação no código/CI desta inspeção**, e verifique para B2B/novos ambientes antes de declarar gates satisfeitos. Produção, Stripe Connect/Tax/Invoicing e obrigações fiscais/NFS-e não estão validados.

## 9. Schema e Alembic — linha completa até 0023

**Head `20261012_0023` na branch SaaS.** Alembic é fonte de verdade e `BackEnd/Python/sql/schema.sql` referência de instalação nova; não aplicar SQL manualmente em banco versionado.

| Migration | O que evoluiu |
|---|---|
| `20260917_0001` | baseline consistente (unidades, dados e integridade) |
| `20260918_0002` | contas, orçamento, RSVP, produtos e parceiros |
| `20260918_0003` | alinhamento do schema |
| `20260918_0004` | métricas de estabelecimentos |
| `20260918_0005` | segurança, LGPD, auditoria e rate limiting |
| `20260922_0006` | timestamps de usuário |
| `20260925_0007` | catálogo genérico ampliado |
| `20260925_0008` | catálogo base do planejador |
| `20261008_0009` | organizações/membros, associação e backfill conservador |
| `20261008_0010` | concessões administrativas e quotas B2B |
| `20261008_0011` | convites, equipe e auditoria de tenant |
| `20261008_0012` | filiais e importações CSV de ofertas |
| `20261008_0013` | catálogo CSV e campanhas |
| `20261008_0014` | Stripe TEST B2B e histórico financeiro local |
| `20261008_0015` | Stripe TEST B2C |
| `20261008_0016` | periodicidade de plano B2B |
| `20261009_0017` | modelos pessoais Premium de eventos |
| `20261012_0018` | MFA, sessões verificadas, rate counters, outbox cifrada e heartbeat |
| `20261012_0019` | leads/CRM, analytics, referral, feedback e custos operacionais |
| `20261012_0020` | clientes/propostas profissionais, favoritos e lembretes |
| `20261012_0021` | cota diária do assistente sem persistir prompts |
| `20261012_0022` | titularidade da outbox e deduplicação HMAC das interações |
| `20261012_0023` | GTIN validado e EAN único por organização |

**Migração/rollback:** preservar FKs e dados legados, não atribuir a uma organização SKUs de dono incerto; ensaiar `upgrade head`, `alembic check`, downgrade/upgrade, MySQL real e dados de cópia em staging. Downgrade das migrações SaaS pode apagar grants, convites, auditorias, campanhas, lotes idempotentes, modelos e registros locais de Billing, **mas não cancela assinatura remota no Stripe**. Realizar backup, avaliação de impacto e conciliação externa antes de reverter. Testes SQLite não substituem FK, charset, InnoDB e concorrência MySQL.

## 10. Desenvolvimento, comandos e ambientes

**Pré-requisitos típicos:** Python 3.11+ (CI usa 3.12), MySQL 8+, Node para checagem JS, Docker/Compose para stack completa e Playwright Chromium para E2E.

**Docker local (arquivo que realmente existe na main):**
~~~bash
cp .env.docker.example .env
docker compose -f docker-compose.dev.yml up --build
# Frontend: http://localhost:8080
# Swagger proxied: http://localhost:8080/docs
~~~

A composição de desenvolvimento cria MySQL 8.4, aguarda readiness, aplica alembic upgrade head, carrega seed demo por padrão (LOAD_DEMO_DATA=false para desabilitar), inicia FastAPI e depois Nginx. Nunca usar senhas/defaults de desenvolvimento na produção.

**Execução separada sem Docker:**
~~~bash
cd BackEnd/Python
python -m venv .venv
# ativar o ambiente virtual conforme SO
pip install -r requirements-dev.txt
# configurar .env e um banco MySQL local
alembic upgrade head
python scripts/seed_demo.py       # opcional, apenas desenvolvimento
uvicorn main:app --reload --port 8000
# Em outro terminal:
cd FrontEnd
python -m http.server 5500
~~~

Frontend local: http://127.0.0.1:5500; API local: http://127.0.0.1:8000. A API no frontend usa /api no mesmo domínio em produção por padrão, com configuração explícita para hosts diferentes. PUBLIC_APP_URL precisa refletir a URL acessada pelo cliente, principalmente para retorno de e-mail/pagamento.

**Variáveis críticas:** APP_ENV, DATABASE_URL ou DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME, AUTO_CREATE_SCHEMA=false, PUBLIC_APP_URL, CORS_ORIGINS, COOKIE_SECURE, REQUIRE_EMAIL_VERIFICATION, SECURITY_PEPPER, TRUSTED_HOSTS, SMTP_*, GEOAPIFY_ENABLED, GEOAPIFY_SERVER_API_KEY, LOAD_DEMO_DATA. Nunca commit de .env/credenciais.

**Produção Docker:** usar **docker-compose.production.yml**, .env.production.example como modelo, domínio DNS A/AAAA, portas 80/443 e Caddy emitindo TLS; frontend Nginx e API/MySQL na rede interna. Verificar compatibilidade das variáveis no compose/config antes de executar. Configuração insegura deve interromper a inicialização da API. Fazer backup, ensaio em staging, migrations e smoke test /api/health/ready. Criar primeiro admin com helper seguro e manter segredo fora do Git.

## 11. CI, testes e evidências

A branch SaaS possui seis jobs GitHub Actions: **Backend unit/integration (SQLite)**, **MySQL 8 real + Alembic**, **Frontend static checks**, **Security audit**, **Docker configuration and images**, **E2E Chromium + MySQL**. CodeQL Python/JavaScript e Dependabot estão configurados. [CI do snapshot 208f349, 38004031754](https://github.com/ArthurHenrique-eng/ChurrasPlan/actions/runs/38004031754) e [CodeQL 38004031832](https://github.com/ArthurHenrique-eng/ChurrasPlan/actions/runs/38004031832): **success**. O registro da Fase 2 informa **167 testes SQLite e 12 testes MySQL** na trilha anterior; para precisão do head atual consultar logs específicos. Nenhum destes jobs certifica checkout externo real, deploy live ou backup produtivo.

**Comandos:** `cd BackEnd/Python && pytest -q tests`; configurar `MYSQL_TEST_URL` de banco descartável e executar `alembic upgrade head && alembic check && pytest -q tests_mysql`; na raiz `python scripts/validate_frontend.py`, `python scripts/validate_schema.py`, `./scripts/test_all.sh` (Windows: `.\scripts\test_all.ps1`), `pytest -q e2e` após instalar Playwright Chromium.

**Regressões SaaS:** `test_tenants_saas.py`, `test_entitlements_saas.py`, `test_equipe_organizacao_saas.py`, `test_operacao_b2b_saas.py`, `test_comercial_b2b_fase4a.py`, `test_billing_saas.py`, `test_billing_usuario_stripe.py`, `test_billing_fase2.py`, `test_entitlements_usuario_fase1.py`: isolamento, quotas/concorrência, webhooks, autenticação, CSRF, replay, assinatura, callbacks e compatibilidade. **Histórico, não resultado atual:** 67 testes v0.2, 83 v3, 90 v6.3, 92 v6.3.1, 96 v6.4.

## 12. Mapa de maturidade nesta branch

| Entrega | Estado verificável |
|---|---|
| Cálculo determinístico, listas, estimativas, convites, LGPD, PWA e Geoapify | Implementado |
| Coordenadas 1A, genéricos/preços 1B, CSP/Compose/CI 1C | Implementado |
| Organizações/multi-tenant, equipes, permissões, quotas e convites 2A–2C | Implementado |
| Filiais, CSV de ofertas, onboarding e relatórios 2D | Implementado; métricas não equivalem a vendas |
| Importação CSV de SKUs e campanhas moderadas 4A | Implementado |
| Stripe Test B2B/B2C, Premium, modelos, PDF/CSV e valores mensais guardados | Implementado para sandbox; não live |
| Pagamento Premium realizado no Sandbox externo | Relatado pelo mantenedor; não verificado no CI/documentação do snapshot |
| MFA admin, observabilidade e outbox | Implementados; exigem configuração/monitoramento no ambiente produtivo |
| Restore em ambiente isolado | Comprovado na revisão 6.10; backup remoto/staging produtivo pendentes |
| Leads/CRM, SEO/referral, analytics e dashboard operacional do fundador | Implementados; métricas financeiras reais dependem de dados comerciais |
| Assistência local e contrato de IA | Implementados e testados; LLM externo não ativado |
| Stripe live, impostos/NFS-e, clientes pagantes e operação comercial | Não homologado |

**Critério:** classificar separadamente código implementado, teste automatizado, Sandbox manual, produção e operação comercial. O sistema pode estar bem estruturado sem estar pronto para lançar.

## 13. Roadmap, riscos e próximos incrementos

**Entregas técnicas existentes:** Fase 0 auditoria; 1A coordenadas sem heurística de micrograus; 1B genéricos e BR-2026-09; 1C CSP/infra/CI; 2A–2D organizações, grants, equipe, filiais e ofertas; 4A catálogo CSV/campanhas; 3 Stripe B2B Test; 1 B2C Premium; Fase 2 de homologação contratual Billing. Há **dois esquemas de numeração de fases** em notas diferentes: seguir o domínio e migration, não o número isolado.

**Prioridade P0:** regras de negócio e isolamento B2B, gates CI/CodeQL, proteção da branch no GitHub, MFA administrativo, monitoramento/alertas de falhas de integração, backup/restore externo, staging e documentação legal. **Próximos incrementos B2B:** testar onboarding de mercado, filial, SKU/genérico, preços/CSV, campanhas, permissões e métricas; leads/CRM, SEO, referral, analytics e assistência local foram acrescentados na revisão 6.10. Os próximos incrementos dependem de staging e validação comercial real.

**Dependências humanas:** chaves/Prices/webhooks sandbox para cada fluxo, preço anual aprovado, domínio/TLS/SMTP, backup real, política jurídica/fiscal, piloto regional e validação de pagamento live. Não inventar vendas por métricas de visualização.

**Política do mantenedor:** evoluir e documentar **Saas-ChurrasPlan**, sem criar novas notas `.md` de fase em `docs/` e sem push/merge na `main` sem pedido expresso. Após cada incremento: revisar código, rodar testes e CI da nova revisão, atualizar a memória central.

## 14. Decisões arquiteturais que não devem regredir

- Backend: regras de cálculo, autorização, preço elegível e estados de assinatura; frontend não duplica essa lógica.
- Sistema identifica produtos por IDs/slugs estáveis; nome é apresentação, não chave primária de domínio.
- Separar genericidade do catálogo de comercialização por SKU; definir semântica explícita de unidades.
- Persistir snapshots de orçamento/preço para reprodutibilidade; não recalcular retrospectivamente o pago real.
- Alembic é o único processo normal de evolução do banco em ambientes já inicializados.
- Cookies/sessões/CSRF, headers, validação de produção, rate limiting e minimização LGPD precisam de testes.
- Convite público não exige conta, mas edição de RSVP é restrita ao segredo do convidado.
- Geoapify é fonte de descoberta, nunca de preços comerciais próprios.
- Métricas agregadas não armazenam identificadores de usuário e não são sistema de faturamento por clique.
- Seeds e preços BR-2026-09 são estimativas/demonstração; não dados comerciais atuais.
- PWA não implica que mutações funcionem offline.
- Releases antigas podem descrever tecnologia substituída; conferir a implementação atual.

## 15. Contratos operacionais SaaS incorporados das fases

### Organizações (2A, 0009)
`organizacoes` e `organizacao_membros` com papéis `proprietario`, `gestor`, `editor`, `leitor`. Backfill atribui lojas e SKUs somente quando proprietário inequívoco; mantém `usuario_responsavel_id` e preços legados. `POST /api/parceiro/ativar` cria tenant inicial idempotentemente. `GET /api/parceiro/organizacoes` lista memberships ativas. `X-Organizacao-ID` obrigatório se múltiplas organizações (409 sem seleção, 404 para alheia); ID informado no navegador nunca substitui checagem de membership.

### Entitlements B2B e membros (2B/2C, 0010/0011)
| Tier | Lojas | SKUs comerciais | Ofertas (histórico incluído) | Equipe/convites válidos |
|---|---:|---:|---:|---:|
| Free | 3 | 100 | 2.000 | 3 |
| Pro | 20 | 1.000 | 20.000 | 15 |
| Business | 200 | 10.000 | 100.000 | 100 |

Cotas técnicas provisórias e não uma promessa de preço; contam inativos/histórico, bloqueiam criação mas não edição de registros antigos, com bloqueio MySQL `SELECT FOR UPDATE` contra corrida. Admin pode conceder `cortesia_admin` de Pro/Business por até 366 dias, auditada, com CSRF; expira para Free. `GET /api/parceiro/entitlements` devolve uso e limites; `PUT /api/admin/organizacoes/{id}/concessao` controla grants. Convites de equipe usam token aleatório com SHA-256 persistido, validade 7 dias, uso único, e-mail idêntico ao login, revogação e auditoria; `dev_token` só em dev/teste. Proprietário gerencia equipe sem remover a si, gestor só leitores/editores, editor pode gerir ofertas e leitor só consulta. Produção exige SMTP para convites; o painel escolhe tenant em `sessionStorage`.

### Filiais e importação de ofertas (2D, 0012)
`estabelecimentos` são filiais com `codigo_filial` único por tenant, `unidade_matriz` transacional; só admin global aprova/valida estabelecimento. `POST /api/parceiro/importacoes/ofertas` aceita CSV de até **200 linhas/100 KB**, `estabelecimento_id,produto_id,preco` obrigatórios, status e original opcionais, vírgula/ponto decimal, validação por linha, chave idempotente por organização, hash/resumo persistido, não CSV completo. Chave repetida mesmo conteúdo reproduz retorno; conteúdo diferente gera 409. `GET /api/parceiro/filiais`, `PATCH /filiais/{id}`, `GET /onboarding`, `GET /relatorios/comercial` (até 365 dias) medem cadastro, aprovação, catálogo e interações; `vendas_confirmadas/receita_confirmada` nulos sem dados de transação.

### Catálogo SKU e campanhas (4A, 0013)
`POST /api/parceiro/importacoes/catalogo`: CSV até **200 linhas/100 KB**, campos obrigatórios `sku,produto_pai_id,nome,marca,unidade_venda,quantidade_embalagem,unidade_embalagem`, opcionais `ean` (GTIN de 8/12/13/14 dígitos, com dígito verificador válido e unicidade por organização), variante/ativo. Produto pai deve ser genérico ativo, upsert preserva ID/histórico e atualizações não gastam quota de novos SKUs. Erros por linha e savepoints; o tenant e autorização são verificados no servidor. Campanha referencia ofertas próprias `precos.id` existentes, não cria cupons ou valores fictícios. Estados `rascunho → em_revisao → aprovada/rejeitada`, cancelamento, até 50 ofertas e 90 dias, aprovação de admin com auditoria; listagem pública revalida vigência, estoque, oferta e verificação da loja.

### Estabilidade inicial (1A/1B/1C)
1A aceita graus decimais com vírgula/ponto (latitude −90 a 90; longitude −180 a 180), rejeita NaN/infinito e evita converter micrograus ambíguos automaticamente. 1B adiciona `GET /api/produtos/genericos`, `preco_referencia`/data base/unidade explícitos e seletor resiliente; preços BR-2026-09 são orçamento, não ofertas reais. 1C corrige Compose/README, CSP de MapLibre (sem Google antigo), CodeQL e Dependabot; o ruleset `ChurrasPlanProtect` deve ser conferido nas configurações reais do GitHub. Os documentos antigos de 0 e do roadmap registram os 30 blocos de melhoria, dependências e gates; planos/Stripe Test são descritos na seção 8.

## 16. Histórico técnico consolidado dos antigos documentos

Os 21 Markdown de releases antigas e as 14 notas SaaS foram consolidados aqui em vez de mantidos como arquivos concorrentes; o histórico Git permite recuperar versões integrais.

| Documento legado | Informação retida nesta memória |
|---|---|
| ARQUITETURA_V3.md | Fluxos fases 3–6, separação de domínios, papéis e limites do produto |
| CORRECAO_CUSTOS_V6.3.1.md | Custo/divisão parcial, valor pago, seed demo e regressões |
| DEPLOY_DOCKER_V6.3.md | Topologia Caddy/Nginx/MySQL, DNS, migrations, backup e segurança |
| E2E_MYSQL_V6.3.md | Testes MySQL real, Playwright, CI e limitações históricas |
| FRONTEND_V2.1.md | Identidade visual, logos, navegação, layout e validações |
| FRONTEND_V2.2_UNIFICADO.md | Layout unificado, tipografia local, stepper e fonte matemática |
| GEOAPIFY_ADMIN_V6.5.md | Proxy da chave, Places, autocomplete, mapa, admin e scripts |
| INSTALACAO_DEPLOY_V3.md | Ambiente, SMTP, proxy, migrations, parceiros e checklist |
| LGPD_SEGURANCA_V6.3.md | Dados pessoais, cookies, controles e pendências jurídicas |
| PRECOS_REFERENCIA_BRASIL_2026.md | Prioridade de preços, metodologia e versão BR-2026-09 |
| PRODUCTION_READINESS_V6.3.md | Hardening, PWA, CI, E2E, MySQL, produção e limitações |
| RELEASE_NOTES_V6.3.md | Entregas v6.3/v6.3.1 |
| RELEASE_NOTES_V6.4.md | Histórico da integração Google (substituída em v6.5) |
| RELEASE_NOTES_V6.5.md | Migração Google → Geoapify e compatibilidade |
| REVISAO_FRONTEND_V2.3.md | Correções de estado/requests, etapas, UX, escaping e testes |
| REVISAO_V0.2.md | 24 correções do MVP e invariantes de cálculo, dinheiro e schema |
| VALIDACAO_V0.2.md | 67 testes históricos e limitações de MySQL |
| VALIDACAO_V3.md | 83 testes, migrations, 18 tabelas da época, paridade |
| VALIDACAO_V6.3.1.md | 92 testes, 49 itens seed, cálculos/divisão e limitações |
| VALIDACAO_V6.3.md | 90 testes, 21 tabelas e limites dos testes locais |
| VALIDACAO_V6.4.md | 96 testes, integrações mockadas e testes pendentes em ambiente real |

**Notas importantes preservadas das revisões históricas:** a v0.2 registrou 24 correções, entre elas cálculo pela compra em vez da necessidade, distinção entre preço histórico/atual e proteção de snapshots, idempotência por chave_cliente, associação de slug/ID, Decimal em moeda, flag de gelo, limites de pessoas, FK/ORM/schema coerentes, Pydantic v2 e migração de estado localStorage. A v2.3 corrigiu respostas assíncronas fora de ordem, persistência de rascunho, etapa_atual, recuperações de localStorage corrompido, validações de álcool, timeouts, escaping e controle de checkbox durante persistência. As versões 6.3–6.4 fortaleceram LGPD/segurança/admin/CI/PWA e a 6.5 consolidou Geoapify.

**Arquivos preservados fora da consolidação:** docs/assets/LogoChurrasPlan.png e docs/assets/LogoTXTChurrasPlan.png são imagens utilizadas pelo README; não são documentos Markdown e não devem ser removidas.

## 17. Protocolo para registrar o próximo avanço

Em cada entrega, atualizar o cabeçalho com **data, branch, commit, versão API, head Alembic**, e acrescentar sob a seção relevante:
- **O que mudou:** fluxos, APIs, tabelas e decisões realmente implementados.
- **Comprovação:** testes executados, ambientes e resultados verificáveis; distinguir teste local, CI, staging e Sandbox.
- **Compatibilidade:** migrations, comportamento de dados antigos, contratos frontend/API e rollback.
- **Pendências:** riscos, integrações externas, documentação legal ou operacional.
- **Próximo passo:** ação objetiva com critério de aceite.

Manter este documento **um único ponto de entrada** para agentes/assistentes; nunca tratar hipóteses, logs de conversa ou notas históricas como prova automática de código entregue.


## 18. Índice verificável dos 35 arquivos anteriores (histórico Git)

Estes documentos foram retirados da pasta ativa, mas **não foram perdidos**: os links abaixo apontam para a versão original imutável, antes da consolidação. Leia-os somente quando for necessário auditar uma fase. As seções 0–17 prevalecem para o estado atual.

- [docs/ARQUITETURA_V3.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/ARQUITETURA_V3.md)
- [docs/CORRECAO_CUSTOS_V6.3.1.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/CORRECAO_CUSTOS_V6.3.1.md)
- [docs/DEPLOY_DOCKER_V6.3.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/DEPLOY_DOCKER_V6.3.md)
- [docs/E2E_MYSQL_V6.3.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/E2E_MYSQL_V6.3.md)
- [docs/FRONTEND_V2.1.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/FRONTEND_V2.1.md)
- [docs/FRONTEND_V2.2_UNIFICADO.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/FRONTEND_V2.2_UNIFICADO.md)
- [docs/GEOAPIFY_ADMIN_V6.5.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/GEOAPIFY_ADMIN_V6.5.md)
- [docs/INSTALACAO_DEPLOY_V3.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/INSTALACAO_DEPLOY_V3.md)
- [docs/LGPD_SEGURANCA_V6.3.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/LGPD_SEGURANCA_V6.3.md)
- [docs/PRECOS_REFERENCIA_BRASIL_2026.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/PRECOS_REFERENCIA_BRASIL_2026.md)
- [docs/PRODUCTION_READINESS_V6.3.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/PRODUCTION_READINESS_V6.3.md)
- [docs/RELEASE_NOTES_V6.3.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/RELEASE_NOTES_V6.3.md)
- [docs/RELEASE_NOTES_V6.4.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/RELEASE_NOTES_V6.4.md)
- [docs/RELEASE_NOTES_V6.5.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/RELEASE_NOTES_V6.5.md)
- [docs/REVISAO_FRONTEND_V2.3.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/REVISAO_FRONTEND_V2.3.md)
- [docs/REVISAO_V0.2.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/REVISAO_V0.2.md)
- [docs/SAAS_FASE_0_AUDITORIA_2026-10-08.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/SAAS_FASE_0_AUDITORIA_2026-10-08.md)
- [docs/SAAS_FASE_1_B2C_PREMIUM.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/SAAS_FASE_1_B2C_PREMIUM.md)
- [docs/SAAS_FASE_1A_COORDENADAS.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/SAAS_FASE_1A_COORDENADAS.md)
- [docs/SAAS_FASE_1B_CATALOGO_PRECOS.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/SAAS_FASE_1B_CATALOGO_PRECOS.md)
- [docs/SAAS_FASE_1C_SEGURANCA_INFRA.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/SAAS_FASE_1C_SEGURANCA_INFRA.md)
- [docs/SAAS_FASE_2_HOMOLOGACAO_BILLING.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/SAAS_FASE_2_HOMOLOGACAO_BILLING.md)
- [docs/SAAS_FASE_2A_ORGANIZACOES.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/SAAS_FASE_2A_ORGANIZACOES.md)
- [docs/SAAS_FASE_2B_ENTITLEMENTS.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/SAAS_FASE_2B_ENTITLEMENTS.md)
- [docs/SAAS_FASE_2C_MEMBROS_CONVITES.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/SAAS_FASE_2C_MEMBROS_CONVITES.md)
- [docs/SAAS_FASE_2D_OPERACAO_B2B.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/SAAS_FASE_2D_OPERACAO_B2B.md)
- [docs/SAAS_FASE_3_BILLING_STRIPE_TEST.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/SAAS_FASE_3_BILLING_STRIPE_TEST.md)
- [docs/SAAS_FASE_4A_CATALOGO_CAMPANHAS.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/SAAS_FASE_4A_CATALOGO_CAMPANHAS.md)
- [docs/SAAS_ROADMAP_PRS.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/SAAS_ROADMAP_PRS.md)
- [docs/STRIPE_TEST_B2B2C_SETUP.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/STRIPE_TEST_B2B2C_SETUP.md)
- [docs/VALIDACAO_V0.2.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/VALIDACAO_V0.2.md)
- [docs/VALIDACAO_V3.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/VALIDACAO_V3.md)
- [docs/VALIDACAO_V6.3.1.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/VALIDACAO_V6.3.1.md)
- [docs/VALIDACAO_V6.3.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/VALIDACAO_V6.3.md)
- [docs/VALIDACAO_V6.4.md](https://github.com/ArthurHenrique-eng/ChurrasPlan/blob/208f34954033dc7bb280bdaa72194ba1e37d854c/docs/VALIDACAO_V6.4.md)

## 19. Auditoria dos 30 blocos e evolução de lançamento (11–12/10/2026)

**Base:** `ac039bd`, branch `Saas-ChurrasPlan`. A primeira execução encontrou 166 testes aprovados e um teste de renovação com comparação de datetime UTC sem fuso contra horário local. A comparação foi corrigida com timezone explícito. A numeração abaixo corresponde aos BLOCOS do prompt mestre, não às numerações históricas de fases.

**Critério de conclusão técnica de cada linha:** código integrado, autorização no backend, migration/schema coerentes, teste de aceitação e documentação. Os estados se referem ao escopo descrito na linha. “Implementado e validado” comprova o comportamento técnico na revisão, não prontidão comercial; pendências ampliadas e requisitos externos continuam explícitos. Configuração externa e resultado comercial não são inferidos dos arquivos. P0 bloqueia lançamento; P1 prepara o piloto; P2 é evolução proporcional à demanda.

| Bloco | Estado da entrega | Diagnóstico na base | Evidência e solução na revisão de lançamento | Risco / prioridade | Dependência ou critério adicional |
|---|---|---|---|---|
| 01 Billing | Implementado, aguardando integração externa | Sandbox implementado | `services/billing*.py`, routers e testes: StripeClient, RAK Test, webhook autenticado e outbox opcional, reconciliação e ciclo de assinatura | Alto / P0 | Live recusado. Homologar ambiente, preços, impostos e pagamento real antes de vender |
| 02 Entitlements | Implementado e validado | Cotas de lojas/SKUs/ofertas/equipe | `entitlements.py`: helpers centralizados, campanhas e importações mensais, locks; cotas pessoais/profissionais/assistente | Alto / P0 | Confirmar valores comerciais; quotas não são promessa de preço |
| 03 Posicionamento | Implementado e validado | Home focada em cálculo | Home e `parceiros.html` comunicam consumidores, profissionais e mercados locais | Médio / P1 | Validar mensagem com entrevistas reais |
| 04 Planos | Parcialmente implementado | Free/Premium pessoal e Free/Pro/Business empresarial | Preservados, sem criar Prices fictícios; ferramentas profissionais com limites gratuitos e benefícios Premium | Médio / P1 | Plano profissional separado e anuais exigem aprovação comercial |
| 05 Multi-tenant | Implementado e validado | Organizações/equipe/filiais/RBAC | Queries por tenant preservadas; transferência com senha, confirmação e membro ativo, auditada | Alto / P0 | Papéis existentes proprietário/gestor/editor/leitor mantidos; restrição individual por filial depende de necessidade validada |
| 06 Leads/CRM | Implementado e validado | Ausente | `models/growth.py`, `routers/growth.py`: interesse público, anti-spam, UTM limitada, pipeline, atividades e vínculo com organização | Médio / P1 | Atendimento e recrutamento são humanos; não enviar promoções sem preferência |
| 07 SEO | Implementado, aguardando integração externa | Incompleto | `build_seo.py`, robots/sitemap, 8 guias originais, canonical/OG/JSON-LD; exemplos derivados do motor | Médio / P1 | Executar build com domínio real; local/staging permanecem noindex |
| 08 Referral | Implementado e validado | Não instrumentado | Indicações com opt-in, códigos aleatórios, atribuição de cadastro consentida e totais sem identidade dos indicados | Médio / P1 | Não transforma RSVP em contato promocional |
| 09 Analytics | Parcialmente implementado | Interações simples | Catálogo allowlist, deduplicação, propriedades mínimas, eventos operacionais transacionais e eventos opcionais do navegador | Médio / P1 | Consentimento reduz cobertura; não chamar essas contagens de censo de visitantes |
| 10 IA na engenharia | Implementado e validado | Sem instrução central | `AGENTS.md`, instruções Copilot, contribuição e templates protegem cálculos, migrations, CSRF, MFA, tenant e preços | Médio / P1 | Revisões humanas permanecem necessárias |
| 11 Supply chain | Implementado e validado | pip-audit/Bandit/CodeQL/Dependabot | Preservados; actions fixadas por SHA e estratégia de atualização documentada | Alto / P0 | Confirmar scanners e permissões efetivas do GitHub; imagem deve ser auditada no CI |
| 12 Proteção de branch | Bloqueado | Ruleset sem branches/checks | Leitura real do ruleset 23958344: `include=[]` e `required_status_checks=[]`; candidato preservado em `deploy/github-ruleset.json` | Alto / P0 | Aplicação requer revisão do proprietário; regras de restrição de update/creation e assinaturas podem bloquear merges sem bypass apropriado |
| 13 Assistência no produto | Parcialmente implementado | Ausente | Extração local, contrato de provedor simulado, schema estrito, fallback, cotas, minimização e confirmação; resultado calculado pelo motor | Médio / P1 | LLM externo não configurado. Selecionar provedor, credencial, timeout e orçamento antes de ativar |
| 14 Observabilidade | Parcialmente implementado | Headers/request IDs | JSON sem corpos/URLs/segredos, request IDs validados, métricas HTTP p50/95/99 por processo, fila/heartbeat/alertas administrativos | Alto / P0 | Coletor externo/alertas fora do painel exigem infraestrutura; quantis não são distribuídos |
| 15 Filas | Implementado, aguardando integração externa | E-mails síncronos | Outbox cifrada, transacional, lease, retries/backoff/dead-letter e reprocessamento; webhooks assíncronos em produção | Alto / P0 | SMTP entrega ao menos uma vez; falha após envio pode gerar duplicata, nunca promessa de exactly-once |
| 16 Geoapify | Implementado, aguardando integração externa | Timeout básico | Cache limitado, orçamento por processo, concorrência limitada, retry GET, circuit breaker, resposta limitada e coordenadas validadas | Médio / P1 | Limites são por processo; configurar quota da conta no provedor |
| 17 Backup/restore | Parcialmente implementado | Estratégia ausente | `backup_mysql.py`: gzip/AES-256-GCM, chave independente, retenção e restore autenticado antes de importar, somente banco isolado vazio | Alto / P0 | Agendar e copiar para armazenamento independente; restauração real de produção é gate separado |
| 18 MFA | Implementado e validado | Ausente | TOTP cifrado, replay atômico, códigos de recuperação hashed/uso único, troca com senha+segundo fator, auditoria e revogação | Alto / P0 | MFA admin obrigatório em produção; cofre da chave e recuperação assistida são operação humana |
| 19 CSP/frontend | Implementado e validado | CSP parcial | Corrigida herança de headers em JS/CSS/imagens/SW/manifest; nenhuma página/API privada em cache; limites reais de body e Origin | Alto / P0 | Validar proxy/TLS/CSP no domínio final |
| 20 Operação B2B | Implementado e validado | CSV/SKU/campanhas implementados | Acrescentadas prévias sem commit, cotas, feedback e transferência; preservados catálogo/categorias/ofertas/filiais | Médio / P1 | CSV é o formato inicial; XLSX/filas de catálogo somente quando volume justificar |
| 21 Métricas comerciais | Implementado e validado | Views/cliques sem dedup | HMAC por conta/dia/loja/tipo; parceiro recebe apenas agregados; relatórios por filial preservados | Médio / P1 | Não são métricas aptas a faturamento por clique nem prova de venda |
| 22 Marketplace | Implementado e validado | Comparação existente | Preservados motor/otimização, elegibilidade de oferta, referência estimativa e histórico | Alto / P0 | Sem e-commerce multi-loja, logística ou split; escopo do piloto é encaminhamento |
| 23 README/Compose | Implementado e validado | Base corrigida, produção incompleta | Atualizados ambientes/keys/worker, Caddy, comandos e memória; schema SQL acompanha Alembic | Médio / P0 | Nunca executar seed demonstrativo em produção |
| 24 Deploy | Bloqueado | Docker/TLS, sem staging comprovado | Compose com worker e segredo obrigatório; smoke/carga básica; procedimento de build SEO, migration e rollback | Alto / P0 | Domínio, TLS/SMTP, hosting, cofre, staging e smoke externos permanecem gates |
| 25 Qualidade SaaS | Implementado e validado | 167 testes na base | Regressões existentes mais MFA, fila, privacy/growth, profissional, assistente, CSV preview, webhook durável; MySQL/Alembic/E2E | Alto / P0 | Resultados finais abaixo devem citar revisão e ambiente exatos |
| 26 Consentimentos | Implementado, aguardando integração externa | Conta técnica existente | Marketing separado de atendimento; métricas/referral opt-in; exportação/exclusão ampliadas; retenção operacional | Alto / P0 | Bases legais, controlador, subprocessadores e retenções precisam de revisão jurídica real |
| 27 Piloto regional | Parcialmente implementado | Onboarding existente | Landing, CRM/pipeline, checklist preservado e feedback/disposição a pagar por organização | Médio / P1 | Recrutar cerca de 5 açougues + 5 mercados reais; não cadastrar clientes fictícios |
| 28 Fundador | Parcialmente implementado | Dashboard básico | Aquisição/ativação/leads/assinaturas sandbox/feedback, custos registrados e alertas; MRR/ARR/CAC/LTV/churn reais nulos | Médio / P1 | Receitas/coortes/custos reais são necessários para calcular indicadores financeiros |
| 29 GitHub | Parcialmente implementado | Manutenção parcial | AGENTS/SECURITY/CONTRIBUTING/CODEOWNERS/PR/issues/Copilot e memória canônica | Médio / P1 | Habilitar private vulnerability reporting e confirmar proprietário/revisão |
| 30 Arquitetura B2B2C | Implementado e validado | Consumer/Business existentes | Professional integrado com dados próprios, propostas e snapshot; serviços Core compartilhados sem reconstrução | Alto / P0 | Monólito modular mantido; provedores externos opcionais continuam explícitos |

### 19.1 Migrations e reversão

- `0018`: MFA/sessão, recuperação, contadores e fila cifrada; índices de consumo e tarefas prontas. Não altera usuários existentes. Downgrade apaga somente novas credenciais/tarefas e a data MFA; exportar antes de reverter.
- `0019`: leads/atividades, eventos mínimos, indicações/atribuição, feedback e custos; índices de status/tempo/titularidade e unicidade de dedup. Sem backfill artificial. Downgrade remove os novos dados de growth.
- `0020`: clientes e propostas pessoais, snapshots imutáveis, favoritos e lembretes; chave idempotente por usuário e FKs de titularidade. Downgrade não remove churrascos/assinaturas.
- `0021`: consumo diário do assistente, sem persistir prompts. Chave composta por usuário/dia, serializada pelo lock do usuário.
- `0022`: titularidade nullable na outbox e HMAC nullable único nas métricas. Mantém registros legados; cascata para tarefas pessoais e deduplicação para novas interações. Reversão preserva tarefas/métricas e remove somente as colunas novas.
- `0023`: EAN deixa de ser globalmente único e passa a ter unicidade por organização; índice global não exclusivo para consulta. Mantém IDs/ofertas e EANs legados. Downgrade recusa duplicatas entre tenants em vez de apagar dados. Testes cobrem compartilhamento entre empresas e colisão dentro do mesmo tenant.

### 19.2 Contratos novos e comportamento

MFA: `GET /api/auth/mfa/status`; `POST /configurar` (senha), `/ativar` (TOTP), `/verificar` (TOTP/recuperação), `/substituir` (senha+segundo fator), `/revogar` (não permitido ao admin quando MFA é obrigatório). As mutações exigem CSRF. As demais APIs falham com `MFA_NECESSARIO` antes da verificação. A UI guia o usuário para `seguranca.html`, inclusive no login privilegiado.

Growth: `POST /api/growth/leads` retorna resposta genérica; honeypot e limites não expõem existência de contato. `POST /api/growth/eventos` aceita somente eventos públicos allowlisted e consentimento explícito. `POST /indicacoes` fornece link de aquisição sem dados privados de eventos. `GET/PATCH /api/admin/growth/leads`, `/dashboard`, `POST /custos` exigem admin e MFA quando aplicável.

Professional: `/api/profissional/clientes`, `/propostas`, `PATCH /propostas/{id}`, `GET /propostas/{id}/pdf`. Cota Free 3 clientes/5 propostas, Premium amplia e autoriza PDF. Proposta exige todos os preços, cliente/evento do mesmo titular e chave idempotente. Margem = `(preco_proposto - custo_estimado) / preco_proposto × 100`; é estimativa, não lucro realizado/documento fiscal. Snapshots não são reescritos ao editar o planejamento.

Retenção: `/api/retencao/favoritos`, `/lembretes`; lembrete somente solicitado, com timezone e data futura até 90 dias, cancelável e sem promoções. Exportação inclui dados profissionais e lembretes. Exclusão cancela/remove tarefas pessoais e exige transferir/encerrar organizações que ainda dependam do proprietário.

Operação: `/api/admin/operacao/metricas`, `/tarefas`, `POST /tarefas/{id}/reprocessar`; nenhuma resposta contém payload da fila. Heartbeat/fila são compartilhados no DB; HTTP/quantis/cache/circuit breaker são por processo. Worker realiza manutenção de retenção: eventos de segurança 7 dias, rate counters 1 dia, analytics/assistente/métricas 90 dias, leads não convertidos 180 dias, lembretes antigos e tarefas concluídas/canceladas 7 dias. Ajustar retenções à operação real e revisar juridicamente.

Prévia CSV: use os endpoints existentes com `?previa=true`; todos os inserts/upserts são revertidos e nenhuma quota mensal/importação é persistida. Os commits normais mantêm compatibilidade e idempotência.

### 19.3 Gates de lançamento e operação

1. **Preparar staging:** banco separado, `AUTO_CREATE_SCHEMA=false`, Alembic, sem seed demonstrativo, domínio/origens/hosts explícitos, HTTPS e secrets fora do Git.
2. **Gerar metadados:** `python scripts/build_seo.py --base-url https://DOMINIO_REAL`. Por padrão, arquivos locais/staging usam noindex. Depois validar robots/sitemap/canonical e ausência de URLs locais no build produtivo.
3. **Cofre:** definir `SECURITY_PEPPER`, `DATA_ENCRYPTION_KEY` compartilhada API/worker e `BACKUP_ENCRYPTION_KEY` independente. Nunca perder chaves cifradas em backups. Gerar chaves fora de logs/repositório.
4. **SMTP/worker/MFA:** verificar cadastro/reset/convite com entrega real, outbox/dead-letter/reprocessamento e segundo fator em todas as contas administrativas. Trocar autenticador exige senha + fator/código de recuperação.
5. **Gateway:** Caddy encaminha `/api/*` diretamente ao backend e demais rotas ao Nginx. Isso preserva HTTPS no backend e evita o loop causado por reescrever `X-Forwarded-Proto` para HTTP no segundo proxy. Banco/backend não expõem portas públicas no Compose produtivo.
6. **Billing:** defaults desligados, chaves `sk_test_`/`rk_test_` e webhook Test. Não inserir Live nesta revisão; é um gate explícito de implementação/homologação, com preços, contratos e requisitos fiscais. Sandbox nunca vira receita real no dashboard.
7. **Backup:** agendar diariamente `python scripts/backup_mysql.py backup --directory CAMINHO_INDEPENDENTE --retention-days 14`, copiar ciphertext+manifest para armazenamento independente e guardar chave em cofre. Meta inicial RPO 24h/RTO 4h é hipótese operacional, não SLA medido. Restaurar em DB vazio `churrasplan_restore_*`, validar tag, Alembic, contagens, app e apenas então planejar recuperação produtiva.
8. **Smoke/carga:** `python scripts/smoke.py https://DOMINIO_REAL`; carga básica `python scripts/load_smoke.py https://STAGING --requests 30 --concurrency 3`. A carga usa calculadora sem persistência, nunca checkout ou mutações financeiras.
9. **Entrega:** backup antes da migration; rodar upgrade uma vez sob coordenação; trocar imagens, smoke e monitorar. Rollback de aplicação usa imagens anteriores identificadas por commit. Downgrade de schema que apaga dados exige exportação/plano de reversão; não executá-lo automaticamente em produção.
10. **GitHub:** revisar `deploy/github-ruleset.json` na interface/API da conta. A configuração inclui main e checks reais, preserva regras existentes; avaliar bypass e restrições de update/creation para evitar bloqueio permanente. Não foi aplicada silenciosamente.
11. **Legal/comercial:** definir responsável/controlador e contatos, revisar políticas/contratos/LGPD/subprocessadores/tributos, recrutar parceiros reais, conferir ofertas e registrar disposição a pagar. Controles técnicos e testes não substituem essas decisões.

### 19.4 Evidências desta execução

Os resultados locais da revisão estão registrados na seção 19.5. Os resultados do GitHub Actions devem citar o commit exato e o ambiente; não reutilizar um pipeline anterior como comprovação de uma revisão posterior.

`0023` preserva IDs/ofertas e troca unicidade global do EAN por unicidade dentro do tenant; novas entradas validam GTIN e dígito verificador. O downgrade bloqueia quando EANs já são compartilhados entre empresas, sem apagar registros. EANs legados inválidos não são apagados automaticamente.

Cenários financeiros em `/api/admin/growth/cenarios` usam hipóteses fornecidas pelo administrador; custos ficam consultáveis por competência em `/custos`. A simulação não cria clientes, assinaturas ou receita. Leads fornecem ao administrador um link de descadastro para incluir em mensagens autorizadas; o descadastro não é revertido pelo reenvio anônimo do formulário. Alterar a preferência autenticada da conta também atualiza o lead do mesmo e-mail. Não reutilizar os números antigos ou um CI de outro commit como evidência de prontidão. O estado correto até esses gates é **pré-lançamento/piloto**, não produção comercial certificada.

Datas de API sem offset em campos de timestamp conhecidos são UTC e normalizadas com `Z` no cliente. Offsets explícitos e campos textuais são preservados. Isso evita exibir eventos/expiração de assinatura três horas fora do horário no Brasil. MySQL dos ambientes Docker usa `+00:00`.

O proprietário pode encerrar uma organização gratuita com senha+confirmação; isso desativa lojas/ofertas e membros e permite excluir a conta. Organização com assinatura existente exige confirmação do término remoto. Logs de acesso Nginx/Uvicorn produtivos são desativados para não registrar query strings com tokens. Erros frontend usam catálogo técnico mínimo, sem mensagens, stack, URLs ou PII, separado de analytics.

Liveness tem limite em memória por processo para continuar funcionando sem DB. As demais rotas usam limite persistido/atômico; readiness confirma o banco e falha com 503 quando indisponível. Limites mais estritos se aplicam a autenticação e ações sensíveis.

### 19.5 Evidência local fechada e limites de prontidão

Ambiente: Python 3.12, MySQL **8.0.46 real** isolado, Chromium **143.0.7499.4**, Nginx 1.24 usado na QA local. CI utiliza MySQL 8.4 e as imagens versionadas do repositório; são ambientes distintos.

- Backend: **208 aprovados** na suíte completa, incluindo consentimento, propriedade, encerramento, telemetria e transporte Stripe; testes críticos suplementares também aprovados. O CI da entrega permanece o gate da revisão publicada.
- MySQL: **12 aprovados**, `alembic check` sem operações pendentes, migração do parceiro/loja/oferta legado, downgrade até 0008 e upgrade até 0023, backfill conferido.
- Navegador: **13 fluxos aprovados**, incluindo os anteriores e mobile/lead, MFA, assistente com confirmação e analytics opt-in.
- Frontend: **35 HTML** e JavaScript/SW verificados, testes Node de formulários/catálogos/tenants/operação/CSP/billing e datas UTC aprovados.
- Smoke: health/readiness/home/parceiros/robots/sitemap/manifest aprovados. Carga básica de 30 requests, concorrência 3, sem gravar eventos: mediana aproximada 25 ms e p95 aproximado 40 ms no ambiente isolado, **não um SLA de produção**.
- Restore: backup gzip/AES-256-GCM restaurado em banco vazio `churrasplan_restore_ci`, tag validada antes do SQL, Alembic e contagens de usuários/eventos/produtos/outbox/versionamento conferidos. Não comprova backup remoto ou recuperação de produção.
- QA visual: desktop 1440 e mobile 390 sem overflow; heads CSP/nosniff conferidos em JS/CSS/logo/manifest/SW. A QA corrigiu o banner de métricas que cobria o botão do planejador e o autosave que sobrescrevia a aplicação do assistente.
- Dependências: `pip-audit` não encontrou vulnerabilidades conhecidas; Bandit no nível alto sem achados. CodeQL/imagens/CI exigem a execução da revisão enviada ao GitHub.

**Avaliação:** implementação técnica adequada para homologação/piloto controlado, com gates explícitos. Não atribuir 9–10/10 a faturamento Live, observabilidade externa, staging, backup remoto, proteção efetiva de branch ou operação comercial sem essa evidência. O próximo incremento é aplicar configuração de staging e homologar esses gates com dados e credenciais reais.

### 19.6 Roadmap residual, dependências e decisões

- **P0 — antes de exposição pública:** aplicar proteção efetiva de main após revisar bypass; preparar staging isolado, domínio/TLS, cofre, SMTP/worker/MFA e alertas externos; agendar backup independente e comprovar restore no ambiente; revisar políticas/contatos/requisitos legais. Para venda recorrente, implementar e homologar a ativação Live com preços, contratos e obrigações fiscais aprovados. Não usar chaves Live nesta revisão.
- **P1 — durante piloto autorizado:** recrutar parceiros reais, medir primeira oferta/ativação/valor percebido, registrar feedback e custos reais; confirmar grade de planos, limites e periodicidade. Funis/coortes financeiras e indicadores SaaS confiáveis dependem de eventos e faturamento reais. Selecionar LLM externo apenas com provedor, credencial, custo máximo e timeout aprovados; a extração local funciona sem essa etapa.
- **P2 — somente com evidência de demanda:** plano profissional independente e documentos personalizados, segmentação/coortes avançadas, importação XLSX/assíncrona para grandes catálogos, limites individuais por filial e agregação distribuída de métricas/quota Geoapify. Microserviços, checkout multi-loja, split e logística estão descartados nesta etapa por complexidade sem necessidade comprovada.

A revisão não executou contatos comerciais, serviços pagos, alteração da proteção de main, deploy real, transações Live nem transmissão de dados a LLM. O próximo incremento executável fora deste ambiente é homologação de staging com configuração fornecida pelo proprietário. Requisitos externos não são marcados como concluídos por existir um script.
