# Revisão funcional do frontend — v2.3

Esta revisão foi feita sobre o frontend visual unificado da v2.2, preservando o HTML/CSS aprovado e auditando o JavaScript contra o contrato atual do FastAPI.

## Correções aplicadas

- Pré-visualizações de carnes, bebidas e extras agora descartam respostas antigas de requisições assíncronas. Isso evita que uma resposta lenta sobrescreva uma escolha mais recente do usuário.
- O rascunho passa a ser salvo durante a edição das etapas, tornando o texto “Rascunho automático” verdadeiro também na prática.
- O estado registra `etapa_atual`; o botão “Continuar planejamento” da home retorna à etapa mais recente válida.
- Estados antigos de carnes sem `produto_slug` são normalizados pelo catálogo atual quando possível.
- Estado JSON corrompido no `localStorage` é recuperado automaticamente em vez de gerar uma nova chave de planejamento a cada leitura.
- Quantidades de consumidores de álcool são normalizadas para nunca superar os adultos correspondentes.
- Quando ninguém está marcado como consumidor de álcool, a opção de bebida alcoólica é desmarcada e desabilitada, inclusive ao carregar estados antigos.
- A página de bebidas agora exige que a etapa de carnes tenha sido definida antes de continuar.
- A duração do formulário foi alinhada ao backend: 1 a 48 horas.
- A URL da API deixou de depender exclusivamente de `127.0.0.1`: desenvolvimento local continua usando porta 8000; em produção o frontend usa `/api` no mesmo domínio por padrão. É possível sobrescrever com `window.CHURRASPLAN_CONFIG.apiBaseUrl` ou a meta tag `churrasplan-api-url`.
- Requisições da API passaram a ter timeout e mensagens mais claras para falhas de rede.
- A lista de compras bloqueia temporariamente o checkbox enquanto a atualização está sendo persistida, evitando corrida causada por cliques rápidos.
- Resultado mostra nomes amigáveis de tipo de evento e perfil, em vez das chaves internas.
- Campos interpolados no resultado receberam escaping adicional.
- A trilha de quantidade de pessoas da home recebeu estilo próprio para Chromium/WebKit e Firefox e o card deixou de ser rotacionado, removendo o efeito visual de “escadinha/pixelado”.

## Verificações executadas

- `node --check` em todos os arquivos JavaScript.
- Auditoria de IDs usados por `getElementById` contra cada HTML: nenhum ID ausente.
- Auditoria de referências locais de CSS, JavaScript, imagens e favicon: nenhuma referência quebrada.
- Parsing de todos os CSS com `tinycss2`: zero erros de parsing.
- Smoke test em Chromium via Playwright usando DOM real e API simulada para:
  - home;
  - planejamento;
  - carnes;
  - bebidas;
  - extras;
  - resultado e checklist de compras.
- Testes adicionais de estado corrompido, migração de carne legada, álcool desabilitado, continuação de etapa e salvamento durante `pagehide`.
- Catálogo de carnes frontend x backend: 23/23 slugs coincidentes.
- Backend: 67/67 testes `pytest` passando com SQLite de teste.

## Observação de implantação

Para desenvolvimento local padrão:

- frontend: `http://127.0.0.1:5500`
- API: `http://127.0.0.1:8000`

Em produção, a configuração recomendada é publicar o frontend e encaminhar `/api` para o FastAPI por reverse proxy. Se a API estiver em outro domínio, defina antes de `config.js`:

```html
<script>
window.CHURRASPLAN_CONFIG = {
  apiBaseUrl: "https://api.exemplo.com"
};
</script>
```

ou adicione no `<head>`:

```html
<meta name="churrasplan-api-url" content="https://api.exemplo.com">
```
