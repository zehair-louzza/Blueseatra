# Render — Checklist des secrets à renseigner manuellement

> Ces variables sont marquées `sync: false` dans `render.yaml`.
> Elles ne doivent **jamais** être committées dans le repo Git.
> Les renseigner dans : **Render Dashboard → ton service → Environment**

---

## 1. DATABASE_URL

**Format Transaction Pooler Supabase (port 6543) :**
```
postgresql+asyncpg://postgres.xmsxlochasjauhnxarvc:[MOT_DE_PASSE]@aws-0-eu-west-1.pooler.supabase.com:6543/postgres
```

**Où trouver :**
Supabase Dashboard → [Connect](https://supabase.com/dashboard/project/xmsxlochasjauhnxarvc/settings/database) → onglet **Transaction pooler** → copier l'URI et remplacer `[YOUR-PASSWORD]`.

---

## 2. SUPABASE_SERVICE_ROLE_KEY

**Où trouver :**
Supabase Dashboard → [API Settings](https://supabase.com/dashboard/project/xmsxlochasjauhnxarvc/settings/api) → section **Project API keys** → `service_role`.

⚠️ Cette clé donne un accès **total** à la base de données, sans restriction RLS. Usage serveur uniquement.

---

## 3. JWT_SECRET

Générer une valeur sécurisée :
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
Ou en ligne : [generate-secret.vercel.app](https://generate-secret.vercel.app/48)

---

## 4. APP_ENCRYPTION_KEY

Clé Fernet pour chiffrer les clés AI des tenants au repos :
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 5. HERMES_BASE_URL + HERMES_API_KEY (VPS OVH / ovh-ai-stack)

Ne plus exposer `:11434`. Pointer Caddy :
```
HERMES_BASE_URL=https://ia.blueseatra.com
HERMES_API_KEY=<même valeur que OLLAMA_API_KEY sur le VPS>
HERMES_EXTRACT_MODEL=qwen2.5:14b
HERMES_REASONING_MODEL=gemma4:26b
```
Infra : dépôt privé `zehair-louzza/ovh-ai-stack`. FastAPI reste sur Ollama (`ia.blueseatra.com`), pas sur le gateway Hermes.

---

## Récapitulatif

| Variable | Source | Sensibilité |
|---|---|---|
| `DATABASE_URL` | Supabase Dashboard → Connect → Transaction pooler | 🔴 Secret |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Dashboard → API Settings | 🔴 Secret |
| `JWT_SECRET` | Générer localement | 🔴 Secret |
| `APP_ENCRYPTION_KEY` | Générer localement | 🔴 Secret |
| `HERMES_BASE_URL` | domaine Caddy OVH (HTTPS) | 🟡 Interne |
| `HERMES_API_KEY` | `.env` ovh-ai-stack | 🔴 Secret |

---

*Généré automatiquement le 20 juillet 2026 — projet Blueseatra `xmsxlochasjauhnxarvc`*
