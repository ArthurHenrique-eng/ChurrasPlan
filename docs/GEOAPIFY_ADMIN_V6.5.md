# Geoapify e Admin — ChurrasPlan v6.5

## Geoapify

A integração usa Geoapify em três partes:

- Places API no backend para estabelecimentos próximos;
- Address Autocomplete API no backend para busca por endereço;
- Map Tiles renderizados com MapLibre GL;
- atualização de pontos conforme o usuário move ou altera o zoom do mapa.

Variáveis:

```dotenv
GEOAPIFY_ENABLED=true
GEOAPIFY_SERVER_API_KEY=
```

A chave Geoapify nunca é retornada ao navegador. O frontend solicita os tiles ao backend autenticado do ChurrasPlan, e o backend consulta a Geoapify usando a chave de servidor.

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
