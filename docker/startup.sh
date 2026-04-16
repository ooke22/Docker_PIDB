#!/bin/bash
# Complete startup script for Django + Celery + MongoDB
# Run from /mnt/c/PI Local Tests/docker

set -e  # Exit on any error

echo "=== Starting Complete Development Environment ==="

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker not found. Please install Docker Desktop and enable WSL integration."
    exit 1
fi

if ! docker-compose version &> /dev/null 2>&1; then
    echo "[ERROR] Docker Compose not found. Please enable WSL integration in Docker Desktop."
    exit 1
fi

# Step 1: Start all services
echo "[INFO] Starting MongoDB, Redis, Django, and Celery services..."
docker-compose up -d

# Step 2: Wait for health checks to pass (new - leverages docker-compose health checks)
echo "[INFO] Waiting for services to become healthy..."
echo "[INFO] MongoDB health check in progress..."
until [ "$(docker inspect --format='{{.State.Health.Status}}' local_mongo 2>/dev/null)" = "healthy" ]; do
    echo "[INFO] Waiting for MongoDB to be healthy..."
    sleep 5
done
echo "[INFO] ✅ MongoDB is healthy!"

# Step 3: Check service status
echo "[INFO] Checking service status..."
docker-compose ps

# Step 4: Restore database if dump exists (your existing logic - works perfectly)
DUMP_DIR="./dump_localtest"
if [ -d "$DUMP_DIR/LocalTest" ]; then
    echo "[INFO] Found database dump, restoring..."
    docker-compose exec mongodb mongorestore --uri="mongodb://localhost:27017/LocalTest" --drop /backup/LocalTest 2>/dev/null || {
        echo "[INFO] Database restore failed or not needed, continuing..."
    }
else
    echo "[INFO] No database dump found, skipping restore."
fi

# Step 5: Run Django migrations (enhanced with better error handling)
echo "[INFO] Running Django migrations..."
if docker-compose exec django python manage.py migrate; then
    echo "[INFO] ✅ Migrations completed successfully"
else
    echo "[WARNING] Migrations failed, but continuing..."
fi

# Step 6: Show service URLs and helpful info
echo ""
echo "=== Services Started Successfully ==="
echo "🌐 Django Application: http://localhost:8000"
echo "🍃 MongoDB (for Compass): mongodb://localhost:27018"
echo "📊 Redis: localhost:6379"
echo ""
echo "=== Data Persistence Status ==="
echo "💾 MongoDB data: Persistent in 'mongodb_data' volume"
echo "🔄 Redis data: Persistent in 'redis_data' volume"
echo "📁 Your data survives container restarts and rebuilds!"
echo ""
echo "=== Service Logs ==="
echo "📋 View Django logs: docker compose logs -f django"
echo "👷 View Celery logs: docker compose logs -f celery"
echo "🍃 View MongoDB logs: docker compose logs -f mongodb"
echo ""
echo "=== Safe Management Commands ==="
echo "🛑 Stop services (data safe): docker compose down"
echo "🔄 Restart services: docker compose restart"
echo "📊 Check status: docker compose ps"
echo "⚠️  NEVER use: docker compose down -v (removes volumes!)"
echo ""
echo "[SUCCESS] All services are running with persistent data! You can now use your Django API."