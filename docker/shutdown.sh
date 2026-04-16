#!/bin/bash
# Safe shutdown script
# Run from /mnt/c/PI Local Tests/docker

echo "=== Safely Shutting Down Development Environment ==="

# Optional: Create a quick backup before shutdown
echo "[INFO] Creating quick backup..."
if docker ps -q --filter "name=local_mongo" | grep -q .; then
    docker exec local_mongo mongodump --uri="mongodb://localhost:27017/LocalTest" --out="/backup/shutdown_backup_$(date +%Y%m%d_%H%M%S)" 2>/dev/null || echo "[WARNING] Backup failed, continuing shutdown..."
fi

# Graceful shutdown
echo "[INFO] Stopping all services gracefully..."
docker-compose down

echo "[INFO] ✅ All services stopped safely"
echo "[INFO] Your data is preserved and will be available on next startup"
echo ""
echo "To restart: ./startup.sh"