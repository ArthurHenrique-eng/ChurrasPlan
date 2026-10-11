# ChurrasPlan SaaS — Memória técnica mestra

> **Documento canônico:** docs/ChurrasPlanSaaS.md  
> **Atualizado em:** 11/10/2026 (America/Sao_Paulo)  
> **Base inspecionada:** GitHub ArthurHenrique-eng/ChurrasPlan, branch main, commit 2afa7b0a0780d2c6090b2d2677b6e1b799958d90.  
> **Estado do código nessa referência:** API FastAPI v6.5.0; Alembic head 20260925_0008.  
> **Escopo:** memória operacional para humanos e IAs, consolidando os 21 documentos Markdown históricos que existiam em docs/. O README da raiz permanece uma apresentação pública resumida.

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

## 2. Stack, estrutura e pontos de entrada

| Camada | Implementação na main inspecionada | Caminho de referência |
|---|---|---|
| Frontend | HTML/CSS/JavaScript modular, multipágina, responsivo; PWA | FrontEnd/, FrontEnd/js/, FrontEnd/css/, FrontEnd/sw.js |
| Backend/API | Python, FastAPI, Pydantic, SQLAlchemy | BackEnd/Python/main.py, routers/, schemas/, services/ |
| Banco | MySQL 8.x em produção; MySQL 8.4 em Docker/CI; SQLite para parte dos testes | BackEnd/Python/database/, models/, alembic/ |
| Migrations | Alembic, fonte oficial do schema | BackEnd/Python/alembic/versions/ |
| Infraestrutura | Docker Compose dev/prod, Nginx estático, Caddy/HTTPS na produção | docker-compose.dev.yml, docker-compose.production.yml, deploy/Caddyfile |
| CI | GitHub Actions: backend, MySQL, frontend, auditoria, Docker e Playwright | .github/workflows/ci.yml |
| Mapas | Geoapify Places/Autocomplete/Tiles via backend; MapLibre GL no navegador | services/geoapify.py, routers/onde_comprar.py, FrontEnd/js/onde-comprar.js |
| Preços de referência | Tabela de preços nacionais estimados, versão BR-2026-09 | services/precos_referencia.py |
| Identidade visual | Logos e recursos públicos da aplicação | FrontEnd/assets/ e docs/assets/ |

**Rotas de entrada:** /api/health (liveness); /api/health/ready (readiness com banco); /docs e /openapi.json quando expostos pelo ambiente. A versão retornada pela API na main inspecionada é **6.5.0**. Os agrupamentos FastAPI confirmados são: auth, calculadora, churrascos, convites, produtos, estabelecimentos, preços, lista_compras, parceiros, onde_comprar, planos, privacidade e admin.

**Fluxo web típico:** Home → Planejamento → Carnes → Bebidas → Extras → Resultado/Central do Churrasco → Checklist/Divisão → Histórico/Convites/Onde comprar. A home pode apresentar simulação demonstrativa, mas **não** constitui motor alternativo de cálculos.

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

**Controles implementados na base v6.3+:** PBKDF2-HMAC-SHA256 com salt para senhas; segredos de sessão e tokens opacos persistidos somente por hash; cookie churrasplan_session HttpOnly, SameSite=Lax e Secure em produção; cookie churrasplan_csrf para o frontend; checagem CSRF em mutações autenticadas; rate limiting com identificadores HMAC; headers de segurança/HSTS; CORS e Trusted Hosts explícitos; limite de payload; auditoria admin; validação de configuração de produção; pip-audit e bandit em CI.

**LGPD técnica:** termos/privacidade versionados, aceite de documentos, marketing opcional e separado, exportação JSON e exclusão autenticada/reconfirmada da conta. Dados pessoais envolvidos: cadastro, churrascos salvos, respostas de convidados, restrições voluntárias, dados comerciais e registros técnicos mínimos. Sem cookies de publicidade/analytics habilitados por padrão na base documentada.

**PWA:** manifest, ícones 192/512/maskable, service worker, cache controlado apenas para assets/páginas públicas, fallback offline e indicador de conectividade. **Não** cachear respostas /api nem páginas privadas como fallback. Não existe sincronização offline garantida para escritas, checkout, conta ou checklist.

**Pendências legais/operacionais para produção comercial:** definir controlador/razão social/CNPJ, canal de privacidade e encarregado quando aplicável; bases legais e prazos de retenção; subprocessadores reais e acordos; resposta a incidentes e titulares; backups/retenção; política pública revisada juridicamente. Controles técnicos não equivalem a conformidade organizacional concluída.

## 8. Planos, Stripe e distinção entre repositório e ambiente local

**Fato verificável na main de 11/10/2026:** routers/planos.py lista planos e consulta assinatura, mas retorna pagamentos_habilitados: false; main.py registra API v6.5.0. Na árvore desta branch não há implementação Stripe de checkout/webhook/billing sob routers/services. Portanto **não marcar faturamento em produção ou Stripe homologado no GitHub main**.

**Contexto de desenvolvimento relatado em 08/10/2026:** houve trabalho em integração Stripe/Billing, criação/validação de três preços e conclusão informada de uma homologação Sandbox Premium, incluindo conciliação, benefícios e redirecionamento após correção de PUBLIC_APP_URL. Isso é **RELATADO LOCALMENTE**, e pode estar em checkout local, branch não mesclada ou versão ainda não publicada. Exigir comparação de commit/branch, migrations, webhooks, testes e fluxos reais antes de promover para IMPLEMENTADO/VALIDADO no repositório.

A direção SaaS B2B2C prevê verificar, quando o código de billing estiver disponível: clientes e assinaturas Stripe, Checkout/Portal, ciclo de vida e estados, eventos por webhook com assinatura/idempotência, reconciliação, benefícios por plano, cancelamento/renovação/falhas, testes Sandbox e passagem segura para produção. Não presumir Stripe Connect, Tax ou Invoicing operantes só porque são objetivos comerciais.

## 9. Schema e histórico Alembic

**Alembic é a fonte da verdade.** Na main inspecionada, a revisão head está em **20260925_0008**. Nunca aplicar sql/schema.sql manualmente por cima de banco já versionado. Histórico:

| Migration | Resumo |
|---|---|
| 20260917_0001 | baseline consistente; separação compra/necessidade, idempotência e adequações de schema |
| 20260918_0002 | contas, orçamento, convidados/RSVP, SKU e parceiros |
| 20260918_0003 | alinhamento de schema |
| 20260918_0004 | métricas agregadas de estabelecimentos |
| 20260918_0005 | LGPD, rate limiting, auditoria e hardening |
| 20260922_0006 | restauração de defaults de timestamps em usuários |
| 20260925_0007 | catálogo genérico ampliado para parceiros |
| 20260925_0008 | catálogo de base do planejador garantido via migration |

Histórico antigo apontava heads 0004/0005 por representar releases anteriores; **não usá-los como head atual**. A referência SQL é BackEnd/Python/sql/schema.sql, voltada a instalação nova, mas validar paridade com ORM e migrations. Produção exige MySQL/PyMySQL; os testes SQLite não substituem testes MySQL para FKs, engine InnoDB, charset utf8mb4, JSON e migrations com dados existentes.

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

## 11. Testes, CI e interpretação de evidências

**Comandos principais:**
~~~bash
cd BackEnd/Python
pytest -q tests
# Com MYSQL_TEST_URL e DATABASE_URL apontando para banco descartável:
alembic upgrade head
alembic check
pytest -q tests_mysql
# Na raiz do repositório:
python scripts/validate_frontend.py
python scripts/validate_schema.py
./scripts/test_all.sh
# Windows: .\scripts\test_all.ps1
# Playwright: python -m playwright install chromium; pytest -q e2e
~~~

**Workflow verificado na main:** backend-unit (SQLite), mysql-real (MySQL 8.4 + Alembic), frontend-static (JS, service worker, links), security-static (pip-audit/bandit), docker-build (Compose/config e imagens), e2e (Chromium + MySQL). O CI valida desenvolvimento/qualidade, **não realiza deploy automático**.

**Resultados históricos, NÃO garantias de execução atual:**

| Marco | Evidência registrada na época |
|---|---|
| v0.2 | 67 testes SQLite, compileall, migração SQLite de vazio/legado, paridade SQL/ORM e 23 carnes |
| Frontend v2.3 | JavaScript/HTML/CSS, Playwright com API simulada e 67 testes backend |
| v3.0 (18/09/2026) | 83 testes; migrations até 0004 com preservação de dados; alembic check |
| v6.3.0 | 90 testes; 21 tabelas; 20 HTML; 58 paths/62 operações OpenAPI; migrations até 0005 |
| v6.3.1 | 92 testes; seed de 49 itens; custo/divisão parcial; 21 tabelas; 58 paths/62 operações |
| v6.4.0 | 96 testes; 21 tabelas; 20 HTML; 58 paths/64 operações; MySQL real dependia de CI/staging |

Várias validações históricas ocorreram sem daemon Docker/MySQL ou browser Chromium acessível no ambiente local e **não devem ser descritas como testes reais de produção**. O job CI/staging é responsável por comprovar testes dependentes desses serviços. Nunca inventar aprovação de CI ou implantações posteriores a partir desses números.

## 12. Resumo funcional e maturidade para comercialização

| Capacidade | Estado na main de referência | Observação |
|---|---|---|
| Motor de cálculo e lista de compras | IMPLEMENTADO | Backend autoritativo; distinguir compra/necessidade |
| Conta, sessão, convites/RSVP, histórico | IMPLEMENTADO | Revisar autorização/regressões em cada alteração |
| Orçamento, referência nacional, checklist/divisão | IMPLEMENTADO | Diferenciar referência, ofertas e dinheiro real |
| Catálogo genérico, SKU, ofertas e parceiros | IMPLEMENTADO | Verificação e qualidade de cadastro são requisitos operacionais |
| Admin/moderação/auditoria | IMPLEMENTADO | Operação e segregação de acesso devem ser homologadas |
| Geoapify e otimização | IMPLEMENTADO, dependente de configuração | Descoberta externa não é preço externo |
| CI, PWA, Docker/staging | BASE IMPLEMENTADA | CI/deploy/ambiente real exigem confirmação |
| Cobrança Stripe e entitlements pagos | NÃO PRESENTE na main examinada | Sandbox Premium relatado localmente; verificar branch/merge |
| Stripe Connect, Tax e Invoicing | NÃO CONFIRMADOS | Planejamento não equivale a entrega |
| LGPD organizacional, documentos finais, produção comercial | PENDENTE DE VALIDAÇÃO | Responsáveis, políticas, fornecedores, operação |
| Hospedagem/domínio/SMTP em produção | NÃO CONFIRMADOS | Configuração de deploy existe, operação não demonstrada |

Não declarar o SaaS pronto para comercialização apenas por haver controles técnicos. Avaliar faturamento real, governança, observabilidade, suporte, atendimento, antifraude, dados de parceiros e resiliência.

## 13. Backlog orientador / riscos

**Alta prioridade:** sincronizar o estado de Billing/Stripe realmente implementado em desenvolvimento com uma branch rastreável e testes; confirmar webhooks e concessão/revogação de benefícios; staging end-to-end; SMTP; CI verde e release documentada. Revisar múltiplos papéis, autorização de parceiro, criação e moderação de mercado, persistência de produtos genéricos/comerciais e preços elegíveis.

**Antes da abertura comercial:** acordos/documentos LGPD definitivos, domínio e HTTPS, gestão de segredos, backups e ensaio de restore, monitoramento/alertas, limites antiabuso, processo de suporte, política de moderação, qualidade da lista de estabelecimentos e observação das taxas/custos de provedores.

**Futuro/opcional:** performance e caching, processos B2B de onboarding e acompanhamento, dados analíticos com privacidade, otimização da cobertura local, alertas meteorológicos/de preço somente se incorporados ao backlog, integração financeira adicional, CI/CD deploy automatizado após provedor escolhido.

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

## 15. Histórico técnico consolidado dos antigos documentos

Os 21 Markdown anteriores de docs/ foram consolidados aqui em vez de mantidos como arquivos concorrentes; o histórico Git permite recuperar versões integrais.

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

## 16. Protocolo para registrar o próximo avanço

Em cada entrega, atualizar o cabeçalho com **data, branch, commit, versão API, head Alembic**, e acrescentar sob a seção relevante:
- **O que mudou:** fluxos, APIs, tabelas e decisões realmente implementados.
- **Comprovação:** testes executados, ambientes e resultados verificáveis; distinguir teste local, CI, staging e Sandbox.
- **Compatibilidade:** migrations, comportamento de dados antigos, contratos frontend/API e rollback.
- **Pendências:** riscos, integrações externas, documentação legal ou operacional.
- **Próximo passo:** ação objetiva com critério de aceite.

Manter este documento **um único ponto de entrada** para agentes/assistentes; nunca tratar hipóteses, logs de conversa ou notas históricas como prova automática de código entregue.
