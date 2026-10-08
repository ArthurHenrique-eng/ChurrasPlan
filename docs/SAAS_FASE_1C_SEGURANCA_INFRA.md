# Fase 1C — hardening de segurança, CI e documentação Docker

## Gate de entrada
Iniciar somente após o CI de push no commit consolidado de PRs #3, #4 e #5: `650467421466c3be16209746447b7197ced64588`.
Execução aprovada: https://github.com/ArthurHenrique-eng/ChurrasPlan/actions/runs/37816767960 (seis jobs, resultado `success`).

## Riscos constatados
1. `FrontEnd/nginx.conf` ainda autorizava `maps.googleapis.com`, `places.googleapis.com`, `maps.gstatic.com` e `googleusercontent.com` apesar da migração para Geoapify. A CSP também bloqueava o JavaScript e CSS de MapLibre em `cdn.jsdelivr.net` e não permitia workers `blob:`.
2. `README.md` documentava `docker-compose.yml`, inexistente na raiz. O Compose de desenvolvimento correto é `docker-compose.dev.yml`. O de produção independente é `docker-compose.production.yml`; `docker-compose.prod.yml` é somente override para uso combinado.
3. O exemplo de produção copia `.env.production`, mas `docker compose` não carrega automaticamente esse nome. É obrigatório `--env-file .env.production` (ou exportar variáveis) para evitar confusão e erros de configuração.
4. Ausência de Dependabot e CodeQL nas rotinas GitHub auditadas.
5. No diagnóstico da Fase 0, o ruleset `ChurrasPlanProtect` não tinha alvo configurado; isso não comprova proteção efetiva da branch SaaS.

## Implementado neste PR
- CSP do Nginx permite somente origem local e CDN jsDelivr para MapLibre JS/CSS; Geoapify/tiles são acessados pelo proxy próprio `/api/`, mantendo `connect-src 'self'`; removes Google Maps/Places.
- Permite `worker-src 'self' blob:` para o worker do MapLibre. Não libera `unsafe-eval` nem `unsafe-inline` em scripts.
- Teste automatizado Node valida as diretivas CSP, bibliotecas referenciadas no HTML e comandos Docker no README.
- Build Docker valida sintaxe Nginx com `nginx -t` dentro da imagem gerada.
- Dependabot: pip, GitHub Actions e imagens Docker, sempre abrindo PRs para `Saas-ChurrasPlan`, nunca direto na `main`.
- CodeQL v4 em Python e JavaScript/TypeScript para PR, push e varredura agendada; `security-extended`.
- README documenta comandos dev/prod com os nomes reais dos arquivos e o carregamento explícito de secrets.

## Comandos de operação
Desenvolvimento:

```bash
cp .env.docker.example .env
docker compose -f docker-compose.dev.yml up --build
```

Produção independente com Caddy e HTTPS, **somente após configurar domínio, senhas e SMTP**:

```bash
cp .env.production.example .env.production
# edite valores e crie senhas distintas/fortes
chmod 600 .env.production
docker compose --env-file .env.production -f docker-compose.production.yml config --quiet
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
```

Não executar `seed_demo.py` em produção nem publicar `.env`, `.env.production` ou senhas. Esta fase não realizou deploy.

## Configuração que exige ação do administrador GitHub
Em **Settings > Rules > Rulesets**, revisar/ajustar ruleset ativo:
- Incluir `refs/heads/Saas-ChurrasPlan` como branch-alvo;
- Impedir push direto, exclusão/force push e exigir PR com revisão;
- Exigir checks `Backend unit/integration (SQLite)`, `MySQL 8 real + Alembic`, `Frontend static checks`, `Security audit`, `Docker configuration and images`, `E2E Chromium + MySQL`; adicionalmente exigir os dois checks CodeQL após estabilizarem;
- Exigir que PR esteja atualizado em relação à base antes de merge.

A conta conectada permite alterações de código, mas não foi identificada ação disponível para configurar rulesets. **Não marcar proteção de branch como concluída sem comprovação na API/Settings.**

## Limites, testes e rollback
- Sem migrations, alteração de preços ou autenticação, deploy, segredos ou monetização.
- O CDN de MapLibre é permitido por origem (domínio), não por hash SRI; considerar self-host/pin de subresource integrity. `style-src 'unsafe-inline'` ainda é dívida técnica para estilos inline existentes.
- `nginx -t` prova validade sintática da configuração, não a presença de todos os headers em produção. Confirmar cabeçalhos e fluxo do mapa em staging HTTPS antes do lançamento.
- Esperado: seis jobs CI principais + análises CodeQL independentes; registrar URLs, resultados e recomendações de alertas.
- Rollback: revert do PR, mantendo a sequência de migrações e dados existente.
