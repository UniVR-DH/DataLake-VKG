#!/bin/sh
set -eu

echo "[garage-config] Substituting env vars into garage.toml..."

sed \
  "s,\${GARAGE_RPC_SECRET},${GARAGE_RPC_SECRET},g
   s,\${GARAGE_ADMIN_TOKEN},${GARAGE_ADMIN_TOKEN},g" \
  /template/garage.toml > /config/garage.toml

echo "[garage-config] Config written to /config/garage.toml"
