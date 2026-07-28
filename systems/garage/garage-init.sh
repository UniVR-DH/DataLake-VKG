#!/bin/sh
set -eu

# Use the garage binary from the running garage container (PID namespace shared
# via pid: service:garage). The generated config (with real secrets) is mounted
# at /garageconfig inside the garage container, so it is accessible here via
# /proc/1/root/garageconfig/garage.toml.
G() { chroot /proc/1/root /garage -c /garageconfig/garage.toml "$@"; }

BUCKET="${GARAGE_BUCKET:-csvdata}"

echo "[garage-init] Waiting for Garage RPC..."
for i in $(seq 1 30); do
  if G node id > /dev/null 2>&1; then
    echo "[garage-init] Garage is up."
    break
  fi
  echo "[garage-init]   Not ready yet ($i/30), retrying in 2s..."
  sleep 2
done

NODE_ID=$(G node id 2>/dev/null | head -1 | cut -d'@' -f1)
echo "[garage-init] Node ID: $NODE_ID"

echo "[garage-init] Configuring layout..."
G layout assign -z default -c 10G "$NODE_ID" 2>/dev/null || true
G layout apply --version 1 2>/dev/null || true

echo "[garage-init] Creating bucket '$BUCKET'..."
G bucket create "$BUCKET" 2>/dev/null || true

KEY_NAME="dremio-key"
KEY_ID=""
SECRET_KEY=""

# Reuse credentials if already present in the shared credentials volume.
if [ -f /credentials/key_id ] && [ -f /credentials/secret_key ]; then
  KEY_ID=$(tr -d '[:space:]' < /credentials/key_id)
  SECRET_KEY=$(tr -d '[:space:]' < /credentials/secret_key)
fi

if [ -n "$KEY_ID" ] && [ -n "$SECRET_KEY" ]; then
  echo "[garage-init] Reusing credentials from /credentials/"
else
  if G key list 2>/dev/null | grep -q "[[:space:]]${KEY_NAME}$"; then
    echo "[garage-init] Key '$KEY_NAME' already exists."
    KEY_ID=$(G key list 2>/dev/null | awk -v k="$KEY_NAME" '$2==k{print $1;exit}')
    SECRET_KEY=$(G key info "$KEY_ID" 2>/dev/null | awk '/Secret key:/{print $3}')
  fi

  if [ -z "$KEY_ID" ] || [ -z "$SECRET_KEY" ]; then
    KEY_NAME="dremio-key-$(date +%s)"
    echo "[garage-init] Creating access key '$KEY_NAME'..."
    G key create "$KEY_NAME" 2>&1 | tee /tmp/key-output.txt
    KEY_ID=$(awk '/Key ID:/{print $3}' /tmp/key-output.txt)
    SECRET_KEY=$(awk '/Secret key:/{print $3}' /tmp/key-output.txt)
  fi

  echo "$KEY_ID" > /credentials/key_id
  echo "$SECRET_KEY" > /credentials/secret_key
  echo "$KEY_NAME" > /credentials/key_name
  echo "[garage-init] Credentials saved to /credentials/"
fi

if [ -z "$KEY_ID" ] || [ -z "$SECRET_KEY" ]; then
  echo "[garage-init] ERROR: Missing Garage credentials after bootstrap"
  exit 1
fi

echo "[garage-init] Granting bucket access..."
G bucket allow --read --write "$BUCKET" --key "$KEY_NAME" 2>/dev/null \
  || G bucket allow --read --write "$BUCKET" --key "$KEY_ID" 2>/dev/null \
  || true

echo "[garage-init] Bootstrap complete."
