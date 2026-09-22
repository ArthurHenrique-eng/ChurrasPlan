# Correção de custos e divisão — v6.3.1

## Problema observado

Na v6.3.0, `custo_por_pessoa` e a divisão só eram exibidos quando **todos** os itens do churrasco tinham uma oferta cadastrada. Em um ambiente local sem seed completo, bastava um item sem preço para a interface permanecer em “aguardando preços” e a divisão ficar indisponível.

## Regra nova

- Se **nenhum** item tiver preço: custo e divisão permanecem indisponíveis, porque o sistema não inventa valores.
- Se **parte** dos itens tiver preço: o subtotal conhecido é mostrado, `custo_por_pessoa` é calculado sobre esse subtotal e a divisão funciona com a identificação **parcial**.
- Se **todos** os itens tiverem preço: custo por pessoa e divisão aparecem como estimativa completa.
- Se o checklist tiver preço real informado para todos os itens: o valor real pago passa a ser a base prioritária da divisão.

A flag `estimativa_precos_completa` continua sendo a fonte de verdade para distinguir estimativa completa de parcial.

## Dados demonstrativos

`scripts/seed_demo.py` e `sql/seed_data.sql` agora cobrem os 49 produtos do catálogo padrão com preços exclusivamente demonstrativos. O Docker de desenvolvimento executa o seed por padrão. Para desabilitar:

```bash
LOAD_DEMO_DATA=false docker compose up --build
```

Não use valores do seed como preços reais de mercado.

## Testes adicionados

- custo por pessoa em estimativa parcial;
- divisão com estimativa parcial;
- alteração do número de pessoas da divisão;
- prioridade do valor real quando checklist está completo;
- cobertura do seed demo para todo o catálogo;
- fluxo E2E validando custo por pessoa e botão de divisão.
