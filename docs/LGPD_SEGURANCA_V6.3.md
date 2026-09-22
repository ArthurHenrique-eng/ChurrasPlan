# LGPD e Segurança — ChurrasPlan v6.3

## Dados pessoais relevantes
- nome e e-mail da conta;
- informações dos churrascos salvos;
- respostas voluntárias de convidados;
- restrições/alergias informadas;
- dados de parceiro quando aplicável;
- sessão e registros técnicos mínimos de segurança.

## Decisões de minimização
- senha: nunca armazenada em texto puro;
- sessão/token: banco armazena hash;
- IP de sessão: não é guardado em texto puro;
- rate limiting: chave HMAC;
- métricas de parceiro: sem usuário, churrasco, sessão, IP ou coordenadas;
- chave privada de edição de RSVP não aparece ao organizador;
- service worker não cacheia respostas `/api` nem páginas privadas como fallback.

## Direitos implementados
Na área da conta:
- consulta de consentimentos;
- opt-in/opt-out de marketing;
- exportação em JSON;
- exclusão da conta com senha + confirmação explícita.

## Cookies
- `churrasplan_session`: essencial, HttpOnly, `SameSite=Lax`, Secure em produção;
- `churrasplan_csrf`: essencial à proteção CSRF, legível pelo frontend, Secure em produção.

Não há cookies de anúncios/analytics habilitados por padrão. Se forem adicionados, implemente consentimento correspondente antes da ativação.

## Controles operacionais
- HTTPS/HSTS;
- CORS explícito;
- Trusted Hosts;
- limite de payload;
- rate limiting;
- auditoria admin;
- verificação de e-mail em produção;
- recuperação de senha com token de uso único;
- revogação de sessões após redefinição de senha;
- scanners no CI.

## Pendências organizacionais obrigatórias antes de produção comercial
Código não substitui governança. Defina:
- controlador/razão social/CNPJ;
- canal de privacidade/encarregado quando aplicável;
- base legal e prazos de retenção finais;
- subprocessadores reais (SMTP, hospedagem, Maps etc.);
- procedimento de incidentes;
- procedimento de atendimento a titulares;
- política de backup/retenção;
- revisão jurídica dos documentos públicos.
