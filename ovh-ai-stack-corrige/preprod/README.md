# Blueseatra OVH preproduction

This directory provides an isolated Docker Compose stack for Blueseatra preproduction services on the OVH VPS. It intentionally does not alter the existing OVH AI stack.

## Included services

- PostgreSQL 17 for preproduction data
- Redis 7 with append-only persistence and authentication
- MinIO for non-production object storage

All services are attached only to the `blueseatra_preprod_internal` Docker network. PostgreSQL, Redis and MinIO ports are not published to the host. Access them through application containers on this network or a temporary SSH/Docker tunnel.

## First start

1. Create the real environment file:

   ```bash
   cd ovh-ai-stack-corrige/preprod
   cp .env.preprod.example .env.preprod
   chmod 600 .env.preprod
   ```

2. Replace every placeholder secret in `.env.preprod`. Do not reuse production credentials.

3. Start and validate the stack:

   ```bash
   ./scripts/bootstrap.sh
   ./scripts/healthcheck.sh
   ```

## Commands

```bash
docker compose --env-file .env.preprod up -d
docker compose --env-file .env.preprod ps
docker compose --env-file .env.preprod logs -f
docker compose --env-file .env.preprod down
```

## Reset

`./scripts/reset.sh` permanently deletes all preproduction PostgreSQL, Redis and MinIO volumes. It asks for the exact confirmation value `RESET-PREPROD` before running. Never run it against production resources.

## Security boundaries

- Keep `.env.preprod` off Git and set its permissions to `0600`.
- Never use Supabase production service-role keys, production Stripe keys, or customer data in this environment.
- Use synthetic or irreversibly anonymized data only.
- Do not expose database, Redis or MinIO ports publicly.
- Add any future API or worker container to `preprod_internal`; expose it through the VPS reverse proxy only after authentication and TLS are configured.
