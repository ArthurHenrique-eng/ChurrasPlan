# Fase 2C — Equipes, convites e seletor multi-organização

Esta implementação foi aplicada **diretamente à `Saas-ChurrasPlan`**, após a Fase 2B, sem criar PR/branch auxiliar ou modificar `main`.

## Fluxos entregues

1. Uma organização ativa oferece gestão de usuários com papéis locais `proprietario`, `gestor`, `editor`, `leitor`. O papel do usuário no tenant é a única autoridade para gerir a equipe; o papel global `admin` **não** permite gerenciar membros de uma organização sem estar filiado a ela. O painel global legado segue acessível a admins sem um tenant.
2. Proprietários podem convidar, alterar o papel e remover outros membros. Não podem alterar/remover a si mesmos: isso impede a perda acidental do único proprietário. Gestores apenas convidam, editam e removem editores/leitores; não criam outro gestor/proprietário nem podem alterar outros gestores. Editores mantêm capacidade de cadastro/edição de lojas, SKUs e preços, sem gerir equipe. Leitores só consultam. Toda permissão é verificada novamente na API.
3. Convites são destinados a **um único e-mail normalizado**, usam token randômico (apenas SHA-256 persistido), expiram em sete dias, são consumíveis uma vez, revogáveis e auditados. O convidado pode criar uma conta ou entrar na existente **com o mesmo e-mail**, abrir `parceiro.html?convite=...` e aceitar. Não há vínculo pelo ID enviado pelo navegador. Não é permitido convidar membro ativo nem gerar dois convites pendentes ao mesmo e-mail.
4. O painel obtém `GET /api/parceiro/organizacoes`, mostra seletor de organizações por aba (sessionStorage) e aplica `X-Organizacao-ID` exclusivamente nas rotas B2B relevantes. No backend, todo cabeçalho exige membership ativo, ou contexto explícito de admin global em rotas de dados legadas. Múltiplas organizações sem cabeçalho são rejeitadas com 409. O token de convite é removido da URL depois da tentativa, jamais guardado no storage.
5. O painel apresenta membros, convites pendentes, permissões, edição e revogação; esconde os formulários de escrita para leitores, mas a proteção **nunca** depende do frontend.
6. Cotas provisórias de equipe: Free **3**, Pro **15**, Business **100** vagas; contabilizam membros ativos **mais convites pendentes válidos**. Uma organização bloqueada por cota mantém leitura/edição dos próprios dados, e convites expirados/revogados não ocupam vagas. São limites técnicos de piloto, não precificação comercial.
7. A migration Alembic `20261008_0011` cria `convites_organizacao` e `auditoria_organizacao`; dados de estabelecimentos, catálogos, usuários e eventos B2C não são migrados/destruídos.

## APIs

| Método | Rota | Regra |
| --- | --- | --- |
| GET | `/api/parceiro/organizacoes` | Organizações ativas do usuário |
| GET | `/api/parceiro/entitlements` | Retorna `equipe` com ativos, convites e capacidade |
| GET | `/api/parceiro/equipe/membros` | Proprietário/gestor, organização selecionada |
| GET | `/api/parceiro/equipe/convites` | Convites pendentes sem token |
| POST | `/api/parceiro/equipe/convites` | Convite; requer CSRF e cota livre |
| DELETE | `/api/parceiro/equipe/convites/{id}` | Revogação por gestor/proprietário autorizado |
| POST | `/api/parceiro/convites/aceitar` | Login + CSRF + e-mail exato, token único |
| PATCH | `/api/parceiro/equipe/membros/{usuario_id}` | Alterar papel com matriz RBAC |
| DELETE | `/api/parceiro/equipe/membros/{usuario_id}` | Remover acesso, sem deletar conta |

Convites retornam `dev_token` **somente em desenvolvimento/teste** e somente na resposta do criador; nunca em produção, consulta posterior, auditoria ou banco. Em produção **SMTP_HOST precisa estar configurado para emitir convites**; falhas de e-mail retornam 503 sem gravar convites. O remetente e o domínio público devem estar corretamente configurados com TLS e política de envio.

## Segurança e consistência

- A verificação de pertencimento é obrigatória em todas as consultas/mutações de equipe; administradores globais também precisam de membership local nesses endpoints.
- Mutações de equipe bloqueiam a linha da organização com `SELECT FOR UPDATE` para serializar contador/convite/membro no MySQL. O token também é validado sob bloqueio na aceitação para impedir replay e disputas.
- Os eventos `convite_criado`, `convite_revogado`, `convite_aceito`, `membro_papel_alterado`, `membro_removido` guardam IDs e mudanças relevantes sem armazenar segredo de convite.
- Revogar um membro desativa sua participação na organização, sem apagar conta, histórico B2C ou dados da empresa. A sessão continua válida para as demais organizações; as verificações de acesso ao tenant ocorrem em todas as requisições.
- Antes de um downgrade em banco real, efetuar backup de `auditoria_organizacao` e `convites_organizacao`: `downgrade` de 0011 é destrutivo para essas tabelas.
- LGPD: e-mails de membros/convites são exibidos apenas a gestores/proprietários; acesso, retenção e exclusão operacional deverão seguir a política de privacidade e o processo de dados do produto. Um mecanismo automático de retenção de convites/auditoria ainda não foi implantado.

## Aceite

CI deve comprovar: testes SQLite de token/replay/email, troca de papéis, leitor, gestor, dono, cancelamento, expiração e cota; MySQL real com concorrência de convites/rollback; paridade `schema.sql` x ORM; sintaxe e testes de interface para seletor de tenant; E2E Chromium e CodeQL. Somente o **último commit da `Saas-ChurrasPlan`** deve ser considerado validado.

**Não incluído:** faturamento real, checkout, automação de retenção/expurgo de audit log, provisionamento de funcionários sem conta, gerenciamento de filiais como entidades independentes, MFA e integrações ERP. Essas entregas seguem fases posteriores; o planejador B2C não mudou.
