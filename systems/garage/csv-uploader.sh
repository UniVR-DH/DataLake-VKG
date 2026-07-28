#!/bin/sh
set -eu

echo "[csv-uploader] Waiting for credentials..."
while [ ! -f /credentials/key_id ] || [ ! -f /credentials/secret_key ]; do
  sleep 1
done

AWS_ACCESS_KEY_ID=$(cat /credentials/key_id)
AWS_SECRET_ACCESS_KEY=$(cat /credentials/secret_key)
export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY

echo "[csv-uploader] Uploading CSV files to Garage..."

for csv in /data/*.csv; do
  if [ -f "$csv" ]; then
    filename=$(basename "$csv")
    echo "[csv-uploader] Uploading $filename..."
    aws s3 cp "$csv" "s3://${GARAGE_BUCKET:-csvdata}/" \
      --endpoint-url "${GARAGE_ENDPOINT_URL:-http://garage:3900}" \
      --no-progress
  fi
done

echo "[csv-uploader] Upload complete!"
aws s3 ls "s3://${GARAGE_BUCKET:-csvdata}/" \
  --endpoint-url "${GARAGE_ENDPOINT_URL:-http://garage:3900}"
