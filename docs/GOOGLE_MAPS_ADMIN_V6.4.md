# Google Maps / Places e Admin — ChurrasPlan v6.4

## Google Maps Platform

A aplicação usa duas credenciais distintas:

- `GOOGLE_MAPS_JS_API_KEY`: carregada no navegador para Maps JavaScript API;
- `GOOGLE_PLACES_API_KEY`: usada somente pelo backend para Places API (New) / Nearby Search.

Opcionalmente, `GOOGLE_MAP_ID` ativa `AdvancedMarkerElement`; sem Map ID o frontend mantém fallback compatível para marcador clássico.

### Variáveis

```dotenv
GOOGLE_MAPS_JS_API_KEY=
GOOGLE_MAP_ID=
GOOGLE_PLACES_ENABLED=true
GOOGLE_PLACES_API_KEY=
```

Para desenvolvimento local, autorize os referrers `http://127.0.0.1:5500/*` e/ou `http://localhost:5500/*` na chave JavaScript. Em produção, substitua pelos domínios HTTPS reais. A chave de servidor não deve ser enviada ao navegador.

O backend consulta apenas tipos de compra relevantes (`supermarket`, `grocery_store`, `butcher_shop`, `market`, `discount_supermarket`, `hypermarket`, `warehouse_store`). O conteúdo retornado pelo Places não é persistido pelo serviço; a interface identifica resultados externos como “Google Maps”.

A geolocalização é solicitada somente após ação explícita do usuário em “Usar minha localização”.

## Administrador

O repositório não contém senha administrativa fixa. No Windows:

```powershell
.\scripts\set_admin.ps1 -Email "admin@example.com" -Name "Administrador"
```

O script solicita a senha em modo seguro, usa `BackEnd/Python/.venv` quando disponível e chama `scripts/create_admin.py`. A operação:

- cria ou promove a conta para `admin`;
- ativa a conta;
- marca o e-mail administrativo como verificado;
- redefine a senha usando PBKDF2-HMAC-SHA256;
- revoga sessões antigas quando a senha é redefinida.

No Linux/macOS, use `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NAME` e `ADMIN_RESET_PASSWORD=true` apenas no ambiente do processo.

## MySQL / Alembic

O `alembic/env.py` força `InnoDB` na sessão MySQL antes das migrations e confirma essa alteração antes do contexto do Alembic. Isso evita instalações acidentais em MyISAM e mantém `alembic_version` consistente.
