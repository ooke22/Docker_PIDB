#!/bin/bash
# Run inside WSL at /mnt/c/PI Local Tests/docker
# Dumps LocalTest from Windows MongoDB (listening on 0.0.0.0)

DUMP_DIR="./dump_localtest"

# Check if mongodump is available
if ! command -v mongodump &> /dev/null; then
    echo "[ERROR] mongodump command not found. Please install MongoDB Database Tools."
    echo "Run: sudo apt update && sudo apt install mongodb-database-tools"
    exit 1
fi

echo "[INFO] Dumping LocalTest database from Windows MongoDB..."

# Create dump directory if it doesn't exist
mkdir -p "$DUMP_DIR"

# Use the Windows host IP accessible from WSL
# localhost should work if MongoDB is bound to 0.0.0.0 on Windows
mongodump --uri="mongodb://172.22.0.1:27017/LocalTest" --out="$DUMP_DIR"

if [ $? -eq 0 ]; then
    echo "[SUCCESS] Dump complete. Files stored in $DUMP_DIR"
    echo "[INFO] Dump contents:"
    ls -la "$DUMP_DIR"
else
    echo "[ERROR] Dump failed."
    echo "[INFO] Troubleshooting tips:"
    echo "1. Ensure MongoDB is running on Windows"
    echo "2. Verify MongoDB is bound to 0.0.0.0 in mongod.conf"
    echo "3. Check if port 27017 is accessible from WSL"
    echo "4. Try: telnet localhost 27017"
    exit 1
fi