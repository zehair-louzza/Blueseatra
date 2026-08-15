# Connecteur MCP Blueseatra → Perplexity Computer

Serveur MCP distant (HTTPS, Streamable HTTP) monté sur l’API Render :
`https://blueseatra-api.onrender.com/mcp`

Référence : [Adding Custom Remote Connectors](https://www.perplexity.ai/help-center/en/articles/13915507-adding-custom-remote-connectors)

## 1. Variables Render

Dans `blueseatra-api` → Environment :

| Key | Valeur |
|---|---|
| `MCP_API_KEY` | secret long (générer ci-dessous) |
| `MCP_TENANT_ID` | UUID du tenant **ANELEC Test** |

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Le tenant ANELEC Test se lit dans Supabase (`blueseatra.tenants`). Ne commitez jamais la clé.

Save + redeploy.

## 2. Ajouter le connecteur dans Perplexity

1. [Account settings → Connectors](https://www.perplexity.ai/account/connectors)
2. **+ Custom connector** → **Remote**
3. Name : `Blueseatra`
4. MCP Server URL : `https://blueseatra-api.onrender.com/mcp`
5. Authentication : **API Key** (collez `MCP_API_KEY`)
6. Transport : **Streamable HTTP**
7. Cochez l’accusé de risque → **Add**
8. Cliquez la carte pour activer

Dans un fil Computer, activez la source **Blueseatra**.

## 3. Outils exposés (lecture)

- `blueseatra_list_requests`
- `blueseatra_get_request`
- `blueseatra_list_quotes`
- `blueseatra_search_catalog`

Pas d’écriture (pas de création de devis / suppression) dans cette version.

## 4. Test

```powershell
curl.exe -s -X POST https://blueseatra-api.onrender.com/mcp -H "Authorization: Bearer VOTRE_CLE" -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{}}"
```

Attendu : `serverInfo.name = blueseatra`.
