#!/usr/bin/env bash
# Validation complète de la préproduction OVH, en une commande (tickets #95, #96, #97).
#
#   cd ~/Blueseatra/ovh-ai-stack-corrige/preprod && ./scripts/validation-vps.sh
#
# Enchaîne, uniquement sur la pile de PRÉPRODUCTION isolée (jamais Supabase ni
# la pile IA existante) :
#   1. prérequis et .env.preprod (créé avec des secrets aléatoires s'il manque) ;
#   2. démarrage postgres/redis, migrations (essai à blanc puis application) ;
#   3. démarrage API + worker, test de fumée de bout en bout            (#95) ;
#   4. sauvegarde chiffrée puis restauration dans une base jetable     (#96) ;
#   5. rotation d'un secret non critique (REDIS_PASSWORD) puis contrôle (#97) ;
#   6. rapport sans aucun secret dans validation-vps-<date>.txt, à copier dans
#      les tickets.
# S'arrête à la première étape en échec, avec un message clair.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DATE=$(date -u +%Y%m%dT%H%M%SZ)
RAPPORT="validation-vps-$DATE.txt"
DC="docker compose --env-file .env.preprod"
etape() { printf '\n=== %s ===\n' "$1" | tee -a "$RAPPORT"; }
ok() { printf '  OK  %s\n' "$1" | tee -a "$RAPPORT"; }
ko() { printf '  ÉCHEC  %s\n' "$1" | tee -a "$RAPPORT"; printf '\nRapport partiel : %s\n' "$RAPPORT"; exit 1; }
aleatoire() { openssl rand -hex "$1"; }

{
  echo "Validation préproduction Blueseatra — $DATE (UTC)"
  echo "Hôte : $(hostname) · Commit : $(git rev-parse --short HEAD 2>/dev/null || echo inconnu)"
} > "$RAPPORT"

etape "1. Prérequis"
command -v docker >/dev/null || ko "docker absent"
docker compose version >/dev/null 2>&1 || ko "docker compose absent"
command -v openssl >/dev/null || ko "openssl absent"
ok "docker $(docker --version | cut -d' ' -f3 | tr -d ,) et compose disponibles"
FREE_GO=$(df -BG --output=avail . | tail -1 | tr -dc 0-9)
[ "${FREE_GO:-0}" -ge 5 ] || ko "moins de 5 Go libres sur le disque (${FREE_GO} Go)"
ok "espace disque libre : ${FREE_GO} Go"

if [ ! -f .env.preprod ]; then
  [ -n "${HERMES_BASE_URL_PREPROD:-}" ] || ko ".env.preprod absent : relancer avec HERMES_BASE_URL_PREPROD=<url de la passerelle IA de préprod> (jamais celle de production)"
  sed -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(aleatoire 24)|" \
      -e "s|^PREPROD_APP_DB_PASSWORD=.*|PREPROD_APP_DB_PASSWORD=$(aleatoire 24)|" \
      -e "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=$(aleatoire 24)|" \
      -e "s|^JWT_SECRET=.*|JWT_SECRET=$(aleatoire 32)|" \
      -e "s|^APP_ENCRYPTION_KEY=.*|APP_ENCRYPTION_KEY=$(openssl rand -base64 32 | tr '+/' '-_')|" \
      -e "s|^HERMES_BASE_URL=.*|HERMES_BASE_URL=${HERMES_BASE_URL_PREPROD}|" \
      .env.preprod.example > .env.preprod
  echo "BACKUP_ENCRYPTION_PASSPHRASE=$(aleatoire 32)" >> .env.preprod
  echo "BACKUP_RETENTION_DAYS=30" >> .env.preprod
  chmod 600 .env.preprod
  ok ".env.preprod créé avec des secrets aléatoires propres à la préproduction (droits 600)"
else
  ok ".env.preprod présent"
  grep -q '^BACKUP_ENCRYPTION_PASSPHRASE=' .env.preprod || { echo "BACKUP_ENCRYPTION_PASSPHRASE=$(aleatoire 32)" >> .env.preprod; ok "phrase de chiffrement des sauvegardes ajoutée"; }
fi
chmod +x scripts/*.sh
./scripts/validate-env.sh >/dev/null 2>&1 || ko "validate-env.sh refuse .env.preprod (valeur de production détectée ou secret manquant) : lancer ./scripts/validate-env.sh pour le détail"
ok "validate-env.sh : aucune valeur de production"

etape "2. Base, cache et migrations"
./scripts/bootstrap.sh > /tmp/bs-bootstrap.log 2>&1 || ko "bootstrap.sh (voir /tmp/bs-bootstrap.log)"
# Les contrôles de santé Docker mettent quelques secondes à passer à « healthy ».
sain=0; for i in $(seq 1 30); do ./scripts/healthcheck.sh > /tmp/bs-health.log 2>&1 && { sain=1; break; }; sleep 3; done
[ "$sain" = 1 ] || ko "healthcheck.sh après 90 s (voir /tmp/bs-health.log)"
ok "postgres et redis démarrés et sains"
./scripts/migrate.sh > /tmp/bs-migrate-dry.log 2>&1 || ko "migrations à blanc (voir /tmp/bs-migrate-dry.log)"
ok "migrations rejouées à blanc sur une base jetable"
./scripts/migrate.sh --apply > /tmp/bs-migrate.log 2>&1 || ko "application des migrations (voir /tmp/bs-migrate.log)"
ok "migrations appliquées sur la base de préproduction"

etape "3. API, worker et test de fumée (#95)"
$DC --profile app up -d --build > /tmp/bs-app.log 2>&1 || ko "démarrage api/worker (voir /tmp/bs-app.log)"
for i in $(seq 1 30); do $DC ps api 2>/dev/null | grep -q healthy && break; sleep 4; done
if ./scripts/smoke-test.sh > /tmp/bs-smoke.log 2>&1; then
  ok "smoke-test.sh : inscription, connexion, demande, extraction consommée par le worker, nettoyage"
  sed -n '1,40p' /tmp/bs-smoke.log | grep -viE 'token|password|secret|bearer' | sed 's/^/      /' >> "$RAPPORT"
else
  $DC logs --tail 40 api worker > /tmp/bs-app-logs.log 2>&1
  ko "smoke-test.sh (voir /tmp/bs-smoke.log et /tmp/bs-app-logs.log)"
fi

etape "4. Sauvegarde et restauration (#96)"
./scripts/backup-preprod.sh > /tmp/bs-backup.log 2>&1 || ko "backup-preprod.sh (voir /tmp/bs-backup.log)"
DUMP=$(ls -1t backups/*.dump.enc 2>/dev/null | head -1)
[ -n "$DUMP" ] || ko "aucun fichier de sauvegarde produit"
ok "sauvegarde chiffrée : $(basename "$DUMP") ($(du -h "$DUMP" | cut -f1)), SHA-256 vérifiée"
./scripts/restore-preprod.sh "$DUMP" > /tmp/bs-restore.log 2>&1 || ko "restauration dans une base jetable (voir /tmp/bs-restore.log)"
ok "restauration réussie dans une base jetable (la base de préproduction n'est pas touchée)"
grep -iE 'tables|migrations|restaur' /tmp/bs-restore.log | tail -5 | sed 's/^/      /' >> "$RAPPORT"
printf '| %s | %s | restauration jetable OK | validation-vps.sh |\n' "$(date -u +%Y-%m-%d)" "$(basename "$DUMP")" >> BACKUP.md
ok "restauration consignée dans BACKUP.md"

etape "5. Rotation d'un secret non critique : REDIS_PASSWORD (#97)"
ANCIEN_HASH=$(grep '^REDIS_PASSWORD=' .env.preprod | cut -d= -f2- | sha256sum | cut -c1-8)
cp .env.preprod ".env.preprod.avant-rotation-$DATE" && chmod 600 ".env.preprod.avant-rotation-$DATE"
sed -i "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=$(aleatoire 24)|" .env.preprod
NOUVEAU_HASH=$(grep '^REDIS_PASSWORD=' .env.preprod | cut -d= -f2- | sha256sum | cut -c1-8)
$DC up -d --force-recreate redis > /tmp/bs-rot.log 2>&1 && $DC --profile app up -d --force-recreate api worker >> /tmp/bs-rot.log 2>&1 \
  || { cp ".env.preprod.avant-rotation-$DATE" .env.preprod; $DC --profile app up -d --force-recreate redis api worker >/dev/null 2>&1; ko "redémarrage après rotation : ancien secret restauré (voir /tmp/bs-rot.log)"; }
for i in $(seq 1 30); do $DC ps api 2>/dev/null | grep -q healthy && break; sleep 4; done
sain=0; for i in $(seq 1 30); do ./scripts/healthcheck.sh >/dev/null 2>&1 && { sain=1; break; }; sleep 3; done
if [ "$sain" = 1 ] && ./scripts/smoke-test.sh > /tmp/bs-smoke2.log 2>&1; then
  ok "REDIS_PASSWORD changé (empreinte $ANCIEN_HASH → $NOUVEAU_HASH), redis, api et worker recréés, test de fumée à nouveau vert"
  rm -f ".env.preprod.avant-rotation-$DATE"
else
  cp ".env.preprod.avant-rotation-$DATE" .env.preprod; $DC --profile app up -d --force-recreate redis api worker >/dev/null 2>&1
  ko "contrôle après rotation : ancien secret restauré (voir /tmp/bs-smoke2.log)"
fi

etape "Résultat"
ok "préproduction validée : test de fumée, sauvegarde/restauration et rotation de secret"
printf '\nRapport complet (sans secret) : %s\nCopie hors VPS (règle 3-2-1) : scp ubuntu@<vps>:%s/%s .\n' \
  "$PWD/$RAPPORT" "$PWD" "$DUMP" | tee -a "$RAPPORT"
