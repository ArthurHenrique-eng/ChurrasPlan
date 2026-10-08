# Fase 1A — coordenadas explícitas e sem conversão ambígua

## Contexto e objetivo
Regras do prompt mestre §7.1: latitude deve estar entre -90 e 90, longitude entre -180 e 180; **não presumir** que inteiros fora da faixa representem micrograus. O código anterior convertia `-19959383` em `-19.959383` automaticamente no backend e em ambos os painéis. Isso encobria a fonte do erro e podia gravar local errado.

## Mudanças
- `schemas/estabelecimento.py`: valida graus decimais com vírgula ou ponto, rejeita infinitos, NaN, entradas não numéricas e valores fora da faixa. Mantém `null`/omissão para fluxo sem localização.
- `FrontEnd/js/{parceiro,admin}.js`: elimina a divisão por um milhão e fornece orientação sobre o formato.
- `FrontEnd/{parceiro,admin}.html`: campos do tipo texto com teclado decimal para permitir `-19,959383` independentemente do comportamento de `<input type=number>` de cada navegador.
- Testes Pydantic, API autenticada (parceiro/admin), formulários JavaScript via Node; CI inclui esses testes.

## Contrato
- Válidos: `-19.959383`, `"-19,959383"`, `-44.01187`.
- Inválidos: `-19959383`, `-44011870`, latitude 91, longitude -181, NaN/infinito; a API responde HTTP 422 quando enviada coordenada inválida.
- Geocodificação externa continua preenchendo graus decimais, sem depender de heurísticas; usuário pode corrigir manualmente.
- Dados já gravados não são reescritos. Clientes que enviavam micrograus implicitamente agora devem enviar graus decimais válidos. Essa é uma mudança de validação intencional.

## Banco / rollback
Nenhuma migration. Rollback por revert do PR, mas isso restabeleceria a interpretação perigosa de micrograus; dados antigos precisam de auditoria se a origem das coordenadas não estiver comprovada.

## Evidências exigidas
- `pytest -q tests` (backend, inclusive fluxo de parceiro/admin e novos casos)
- `pytest -q tests_mysql` com MySQL 8 real; `alembic upgrade head && alembic check`
- `node scripts/test_coordinates_ui.mjs`; `python scripts/validate_frontend.py`
- CI completo: frontend, segurança, Docker, E2E.
Resultados e URLs de execução devem constar do PR antes de avançar para a próxima subfase P0.

## Fora de escopo
Catálogo genérico, preço de referência, pagamentos, multi-tenancy, MFA e infraestrutura permanecem sem alteração nesta entrega; terão PRs próprios.
