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

## 5. HERMES_BASE_URL (si VPS OVH en production)

Remplacer `http://localhost:11434` par l'URL publique de ton VPS OVH :
```
https://[IP-OU-DOMAINE-OVH]:11434
```
Vérifier que le port 11434 est ouvert sur le firewall OVH et que Ollama écoute sur `0.0.0.0`.

---

## Récapitulatif

| Variable | Source | Sensibilité |
|---|---|---|
| `DATABASE_URL` | Supabase Dashboard → Connect → Transaction pooler | 🔴 Secret |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Dashboard → API Settings | 🔴 Secret |
| `JWT_SECRET` | Générer localement | 🔴 Secret |
| `APP_ENCRYPTION_KEY` | Générer localement | 🔴 Secret |
| `HERMES_BASE_URL` | IP/domaine VPS OVH | 🟡 Interne |

---

*Généré automatiquement le 20 juillet 2026 — projet Blueseatra `xmsxlochasjauhnxarvc`*
