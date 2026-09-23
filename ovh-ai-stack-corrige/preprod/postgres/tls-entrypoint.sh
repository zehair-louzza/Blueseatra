#!/bin/sh
# Create a private self-signed TLS certificate on first start, then rotate it
# before expiry. The key lives in a dedicated named volume, not in the image.
set -eu
umask 077
tls_dir=/etc/postgresql/preprod-tls
mkdir -p "$tls_dir"

if [ ! -s "$tls_dir/server.crt" ] || [ ! -s "$tls_dir/server.key" ] ||
   ! openssl x509 -in "$tls_dir/server.crt" -checkend 2592000 -noout >/dev/null 2>&1; then
  openssl req -x509 -newkey rsa:3072 -sha256 -nodes \
    -keyout "$tls_dir/server.key" -out "$tls_dir/server.crt" \
    -days 365 -subj '/CN=postgres' >/dev/null 2>&1
fi
chown postgres:postgres "$tls_dir/server.crt" "$tls_dir/server.key"
chmod 600 "$tls_dir/server.key"
chmod 644 "$tls_dir/server.crt"

exec docker-entrypoint.sh "$@" \
  -c ssl=on \
  -c ssl_cert_file="$tls_dir/server.crt" \
  -c ssl_key_file="$tls_dir/server.key"
