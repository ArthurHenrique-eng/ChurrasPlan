# Validação da release v6.3.1

Validação executada após a correção de custo por pessoa/divisão.

- Backend unit/integration: **92 passed**, 3 testes MySQL marcados para ambiente real.
- `scripts/test_all.sh`: **OK**.
- `python -m compileall`: **OK**.
- `scripts/validate_schema.py`: **21 tabelas alinhadas ao ORM**.
- `scripts/validate_frontend.py`: **20 HTML verificados**.
- JavaScript: `node --check` em todos os arquivos + service worker: **OK**.
- Seed demo em banco migrado: **49 produtos genéricos / 49 preços demo / 0 sem cobertura demo**.
- Fluxo API com seed demo: estimativa completa, custo por pessoa e PATCH de divisão: **OK**.
- OpenAPI: **58 paths / 62 operações**, versão **6.3.1**.

## Fluxo financeiro validado

Com 8 pessoas em um cenário de desenvolvimento precificado:

- custo total estimado retornado pela API;
- custo por pessoa retornado;
- divisão por 2 retornada;
- PATCH para divisão por 4 recalculado corretamente.

Estimativas parciais também foram cobertas por teste automatizado: custo por pessoa e divisão usam o subtotal conhecido e permanecem explicitamente marcados como parciais.

## Limites desta validação local

MySQL 8.4 real e navegador E2E completo continuam sendo jobs do CI/staging quando esses serviços estão disponíveis. O workflow foi atualizado para carregar o seed demo antes do E2E, permitindo validar visualmente custo por pessoa e divisão.
