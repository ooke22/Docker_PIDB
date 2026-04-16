#!/bin/bash
# Run inside WSL after Docker MongoDB container is running
# Restores LocalTest into the docker container

DUMP_DIR="./dump_localtest"

echo "[INFO] Restoring LocalTest database into Docker MongoDB..."
mongorestore --uri="mongodb://localhost:27018/LocalTest" "$DUMP_DIR/LocalTest"

if [ $? -eq 0 ]; then
  echo "[SUCCESS] Restore complete."
else
  echo "[ERROR] Restore failed."
  exit 1
fi
