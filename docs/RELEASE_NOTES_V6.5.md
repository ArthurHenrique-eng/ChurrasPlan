# Release Notes — ChurrasPlan v6.5.0

A v6.5.0 substitui a integração Google Maps/Places por Geoapify.

## Mudanças principais

- Geoapify Places API para estabelecimentos próximos;
- Geoapify Address Autocomplete API para busca por endereço;
- Geoapify Map Tiles com Leaflet no frontend;
- geolocalização do navegador continua opcional;
- fallback por endereço quando a geolocalização é negada ou indisponível;
- chave de servidor separada da chave pública de mapa;
- remoção do serviço e documentação específicos do Google Maps;
- política de privacidade atualizada para Geoapify/OpenStreetMap;
- testes de configuração e integração atualizados para Geoapify;
- API reporta versão 6.5.0.

## Configuração

```dotenv
GEOAPIFY_ENABLED=true
GEOAPIFY_SERVER_API_KEY=
GEOAPIFY_MAP_API_KEY=
```

A chave real não deve ser gravada no repositório. Em produção, use duas chaves com restrições adequadas.

## Compatibilidade

O schema de banco não recebe nova migration nesta troca. A coluna histórica `google_place_id` permanece apenas para compatibilidade com bases existentes e não é mais exposta pela API nem usada pela integração atual.
