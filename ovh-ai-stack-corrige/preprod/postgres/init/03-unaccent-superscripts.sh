#!/bin/sh
# Patch unaccent.rules so superscript characters map like on Supabase:
#   ² -> 2, ³ -> 3, ¹ -> 1
# The Debian/Alpine PostgreSQL packages omit these mappings, but migration
# 20260912070000 normalizes designations like "2,5 mm²" and self-checks the
# result — without this patch it fails on a vanilla PostgreSQL instance.
#
# Idempotent: safe on every container start and from scripts/migrate.sh.
# Note: the dictionary only reloads rules when the extension is (re)created;
# scripts/migrate.sh handles that right after running this patch.
set -eu

rules="$(pg_config --sharedir)/tsearch_data/unaccent.rules"
if [ ! -f "$rules" ]; then
  echo "03-unaccent-superscripts: active unaccent.rules not found: $rules" >&2
  exit 1
fi

add_if_missing() {
  if ! grep -qxF "$1" "$rules"; then
    printf '%s\n' "$1" >> "$rules"
    echo "03-unaccent-superscripts: added rule: $1"
  fi
}

add_if_missing '² 2'
add_if_missing '³ 3'
add_if_missing '¹ 1'
