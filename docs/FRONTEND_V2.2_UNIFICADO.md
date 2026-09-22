# Frontend v2.2 — integração com ChurrasPlan_Unificado_Completo

A versão usa `ChurrasPlan_v2.1` como base funcional e o ZIP `ChurrasPlan_Unificado_Completo` como fonte de linguagem visual.

## Preservado
- FastAPI, endpoints e payloads do v2.1;
- localStorage e idempotência do planejamento;
- cálculos e regras de negócio do backend;
- IDs de formulário usados pelos scripts existentes;
- fluxo multipágina Planejamento → Carnes → Bebidas → Extras → Resultado.

## Transplantado/adaptado
- paleta terracota/oliva/papel do projeto unificado;
- fontes locais DM Sans, Manrope e Lora;
- sistema de ícones SVG do projeto unificado;
- home com hero, simulador visual, explicação, cardápio e lista de compras;
- sidebar/topbar do planejador;
- cards, inputs, seletores, botões, tabelas e previews;
- stepper navegável para etapas já alcançadas;
- layout responsivo mobile/desktop.

O JavaScript de cálculo do projeto unificado **não foi usado como fonte de verdade**, evitando duplicar regras que já pertencem ao FastAPI. A simulação da home é apenas demonstrativa e usa as bases atuais de 4h/almoço/perfil normal.
