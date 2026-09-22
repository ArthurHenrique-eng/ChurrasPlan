# Release Notes — ChurrasPlan v6.4.0

A v6.4.0 preserva o schema/Alembic head `20260918_0005`; não há nova migration de dados.

Principais mudanças:

- Google Maps JavaScript API configurável por ambiente;
- Places API (New) / Nearby Search no backend, com chave separada e nunca exposta ao navegador;
- suporte opcional a Map ID e Advanced Markers, com fallback compatível;
- identificação visual de conteúdo “Google Maps” na lista de estabelecimentos;
- filtro de estabelecimentos permanentemente fechados retornados pelo Places;
- Política de Privacidade atualizada para o fluxo de geolocalização/Google Places;
- helper PowerShell `scripts/set_admin.ps1` para definir admin sem senha no Git ou no histórico do shell;
- criação de admin marca e-mail como verificado e revoga sessões quando redefine senha;
- `alembic/env.py` força InnoDB de maneira segura;
- suíte PowerShell agora falha corretamente em comandos externos com exit code diferente de zero;
- teste MySQL adicional garante que todas as tabelas usem InnoDB.

Para ativar Google Maps/Places, ainda é necessário criar projeto/billing/chaves no Google Cloud e preencher as variáveis de ambiente. Nenhuma chave real é distribuída no repositório.
