#!/bin/bash
# Run inside WSL after Docker MongoDB container is running
# Restores LocalTest into the docker container

DUMP_DIR="./dump_localtest"
DOCKER_MONGO_URI="mongodb://localhost:27018/LocalTest"

# Check if mongorestore is available
if ! command -v mongorestore &> /dev/null; then
    echo "[ERROR] mongorestore command not found. Please install MongoDB Database Tools."
    exit 1
fi

# Check if dump directory exists
if [ ! -d "$DUMP_DIR/LocalTest" ]; then
    echo "[ERROR] Dump directory $DUMP_DIR/LocalTest not found."
    echo "[INFO] Please run dump_localtest.sh first to create the dump."
    exit 1
fi

# Test if Docker MongoDB container is accessible
echo "[INFO] Testing connection to Docker MongoDB container..."
timeout 5 bash -c "</dev/tcp/localhost/27018" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[ERROR] Cannot connect to Docker MongoDB on localhost:27018"
    echo "[INFO] Please ensure:"
    echo "1. Docker container is running: docker-compose ps"
    echo "2. Container is listening on port 27018"
    exit 1
fi

echo "[INFO] Docker MongoDB is accessible"
echo "[INFO] Restoring LocalTest database into Docker MongoDB..."
echo "[INFO] Source: $DUMP_DIR/LocalTest"
echo "[INFO] Target: $DOCKER_MONGO_URI"

# Perform the restore
mongorestore --uri="$DOCKER_MONGO_URI" --drop "$DUMP_DIR/LocalTest"

if [ $? -eq 0 ]; then
    echo "[SUCCESS] Restore complete."
    echo "[INFO] You can now access the database via:"
    echo "  - MongoDB Compass: mongodb://localhost:27018"
    echo "  - From Django: mongodb://localhost:27018/LocalTest"
else
    echo "[ERROR] Restore failed."
    echo "[INFO] Troubleshooting tips:"
    echo "1. Check if Docker container is running: docker-compose ps"
    echo "2. Check container logs: docker-compose logs mongodb"
    echo "3. Verify dump files exist: ls -la $DUMP_DIR/LocalTest"
    exit 1
fi