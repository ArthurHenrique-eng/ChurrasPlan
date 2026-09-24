# Geoapify e Admin — ChurrasPlan v6.5

## Geoapify

A integração usa Geoapify em três partes:

- Places API no backend para estabelecimentos próximos;
- Address Autocomplete API no backend para busca por endereço;
- Map Tiles no frontend, renderizados com Leaflet.

Variáveis:

```dotenv
GEOAPIFY_ENABLED=true
GEOAPIFY_SERVER_API_KEY=
GEOAPIFY_MAP_API_KEY=
```

A chave de servidor nunca é retornada ao navegador. A chave de mapa é necessariamente visível no frontend para carregar tiles e deve ser restrita por HTTP referrer/origin. Em produção, prefira duas chaves diferentes.

O mapa usa Geoapify Map Tiles com dados OpenStreetMap. Resultados externos são identificados como Geoapify e não são transformados automaticamente em preços/ofertas próprias.

## Administrador

Senhas administrativas não são recuperáveis em texto puro: o banco guarda apenas hash.

Para listar contas administrativas localmente:

```powershell
cd BackEnd\Python
.\.venv\Scripts\python.exe -c "from database.connection import SessionLocal; from models import Usuario; db=SessionLocal(); [print(u.id, u.nome, u.email, u.papel, u.ativo, u.email_verificado_em, u.ultimo_login_em) for u in db.query(Usuario).filter(Usuario.papel=='admin').all()]; db.close()"
```

Para redefinir a senha com segurança no Windows:

```powershell
.\scripts\set_admin.ps1 -Email "seu-email-admin" -Name "Administrador"
```

O helper redefine a senha, garante papel `admin`, ativa/verifica a conta e revoga sessões antigas.
