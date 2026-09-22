# Arquitetura funcional — ChurrasPlan v3.0

## Objetivo de produto

Reduzir a carga de conhecimento necessária para organizar um churrasco: o usuário informa o contexto do evento e o sistema transforma isso em quantidades, compras, orçamento e acompanhamento prático.

## Fases consolidadas

| Fase | Entrega na v3.0 |
|---|---|
| 3.0 | autenticação, sessão HttpOnly, CSRF, verificação/recuperação de e-mail, papéis |
| 3.1 | convidados avançados e restrições alimentares |
| 3.2 | orçamento com tratamento de estimativa parcial |
| 3.3 | Central do Churrasco/resultado consolidado |
| 3.4 | checklist e valor realmente pago |
| 3.5 | divisão opcional de custo |
| 3.6 | histórico e repetir churrasco |
| 4.0 | convite e RSVP público editável/idempotente |
| 4.1 | produtos comerciais/SKUs ligados ao genérico |
| 4.2 | marca, EAN, variante, fabricante e embalagem |
| 4.3 | base de gestão de catálogo comercial |
| 5.0 | painel de parceiro e métricas agregadas |
| 5.1 | ofertas/preços/validade/estoque |
| 5.2 | geolocalização mediante permissão do navegador |
| 5.3 | Google Maps/Places opcional por configuração |
| 5.4 | comparação por preço/distância/avaliação/equilíbrio |
| 5.5 | otimização multiestabelecimento |
| 6.0 | fundação de planos/assinaturas; sem cobrança real |

## Separações de domínio importantes

### Necessidade, compra e dinheiro

Nunca são o mesmo campo:

```text
necessidade física
    ↓
regra de embalagem/incremento
    ↓
quantidade comercial
    ↓
oferta selecionada
    ↓
subtotal estimado
    ↓
valor realmente pago (opcional)
```

### Produto genérico e SKU

```text
Produto genérico: Cerveja
    ↓
Produto comercial: Marca X Lager 350 ml / EAN ...
```

A calculadora não precisa conhecer marcas para calcular litros. A comparação de preço pode conhecer SKUs sem contaminar a regra matemática.

### Estimativa e realidade

- `custo_total_estimado`: snapshot de ofertas disponíveis no momento do cálculo;
- `valor_pago_total`: informado durante o checklist;
- economia real só existe quando estimativa e pagamentos comparáveis estão completos.

### Usuário e convidado

O organizador precisa de conta para histórico, convites administrativos e onde comprar. O convidado acessa o link RSVP sem conta.

## Autorização

Papéis:

```text
usuario  -> recursos pessoais
parceiro -> recursos pessoais + painel comercial próprio
admin    -> operações administrativas
```

Autorização é verificada no backend, não apenas escondida na interface.

## Métricas de parceiro

A métrica é deliberadamente mínima. Não contém usuário, churrasco, sessão, IP ou coordenadas. O dashboard conta visualizações e cliques associados aos estabelecimentos da conta parceira.

Esses números são métricas de produto e não devem ser tratados como auditoria antifraude/analytics avançado. Se o produto futuramente exigir faturamento baseado em impressões/cliques, será necessária uma camada específica de antifraude e medição.

## Onde comprar

Fontes possíveis:

```text
Estabelecimentos ChurrasPlan + ofertas verificadas
                         +
Google Places opcional para descoberta/localização
                         ↓
comparação/otimização
```

O Google não é tratado como fonte dos preços do ChurrasPlan. Preços precisam vir do banco/ofertas/fontes autorizadas.

## Limites intencionais da release

- sem pagamento/assinatura real;
- sem alerta de preço;
- sem previsão do tempo;
- sem substituição automática de carnes/produtos;
- sem coleta automática não autorizada de preços;
- sem tracking pessoal nas métricas de parceiros.
