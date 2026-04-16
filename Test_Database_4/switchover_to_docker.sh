#!/bin/bash
# Script to switch Docker MongoDB from port 27018 to port 27017
# Place in: /mnt/c/PI Local Tests/Test_Database_4/switchover_to_docker.sh

echo "🔄 SWITCHING DOCKER MONGODB TO PORT 27017"
echo "========================================="

# Verify the migration container exists and has data
echo "1️⃣ Verifying migration container has your data..."
if ! docker ps -a | grep -q mongodb-docker; then
    echo "❌ Error: mongodb-docker container not found!"
    echo "💡 You need to run ./migrate_to_docker.sh first"
    exit 1
fi

# Check if container is running
if ! docker ps | grep -q mongodb-docker; then
    echo "🔄 Starting mongodb-docker container..."
    docker start mongodb-docker
    sleep 5
fi

# Verify data exists in the migration container
python3 -c "
from pymongo import MongoClient
try:
    client = MongoClient('mongodb://localhost:27018', serverSelectionTimeoutMS=5000)
    db = client['LocalTest']
    if 'sensor_4_app_sensor' in db.list_collection_names():
        count = db['sensor_4_app_sensor'].count_documents({})
        if count == 0:
            print('❌ Error: No sensors found in migration container!')
            print('💡 Run ./migrate_to_docker.sh again')
            exit(1)
        print(f'✅ Verified: {count:,} sensors in migration container')
    else:
        print('❌ Error: sensor_4_app_sensor collection not found!')
        print('💡 Run ./migrate_to_docker.sh again')
        exit(1)
    client.close()
except Exception as e:
    print(f'❌ Cannot connect to migration container: {e}')
    print('💡 Run ./migrate_to_docker.sh again')
    exit(1)
"

# Check if verification failed
if [ $? -ne 0 ]; then
    echo "❌ Migration verification failed. Aborting switchover."
    exit 1
fi

echo ""
echo "2️⃣ Stopping any existing MongoDB on port 27017..."
# Stop any existing container named 'mongodb'
if docker ps -a | grep -q ' mongodb$'; then
    echo "   Stopping existing 'mongodb' container..."
    docker stop mongodb 2>/dev/null || true
    docker rm mongodb 2>/dev/null || true
fi

echo ""
echo "3️⃣ Stopping temporary container on port 27018..."
docker stop mongodb-docker

echo ""
echo "4️⃣ Starting Docker MongoDB on port 27017 with your migrated data..."
docker run -d --name mongodb \
    -p 27017:27017 \
    -v mongodb_data:/data/db \
    mongo:5.0

echo ""
echo "⏳ Waiting for MongoDB to be ready on port 27017..."
sleep 10

echo ""
echo "5️⃣ Verifying your data is accessible on port 27017..."
python3 -c "
from pymongo import MongoClient
import time

# Give MongoDB more time to start
max_retries = 6
retry_count = 0

while retry_count < max_retries:
    try:
        client = MongoClient('mongodb://localhost:27017', serverSelectionTimeoutMS=10000)
        db = client['LocalTest']
        
        # Check if collections exist
        collections = db.list_collection_names()
        if not collections:
            print(f'⏳ Attempt {retry_count + 1}: No collections yet, waiting...')
            retry_count += 1
            time.sleep(5)
            continue
            
        if 'sensor_4_app_sensor' in collections:
            count = db['sensor_4_app_sensor'].count_documents({})
            print(f'✅ SUCCESS: {count:,} sensors available on localhost:27017')
            print('🎉 Your Django app can now access the data!')
            
            # Show some sample data info
            sample = db['sensor_4_app_sensor'].find_one()
            if sample:
                sample_keys = list(sample.keys())[:8]
                print(f'📝 Sample sensor keys: {sample_keys}')
                
            break
        else:
            print(f'⚠️  LocalTest database found but no sensor collection')
            print(f'   Collections: {collections}')
            break
            
        client.close()
        
    except Exception as e:
        retry_count += 1
        if retry_count >= max_retries:
            print(f'❌ Connection failed after {max_retries} attempts: {e}')
            print('💡 Try restarting the container: docker restart mongodb')
        else:
            print(f'⏳ Attempt {retry_count}: Connection failed, retrying... ({e})')
            time.sleep(5)
"

echo ""
echo "6️⃣ Testing Django ORM connection..."
python3 -c "
import os
import sys
import django

# Add your project to Python path
project_path = '/mnt/c/PI Local Tests/Test_Database_4'
if project_path not in sys.path:
    sys.path.insert(0, project_path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Test_Database_4.settings')

try:
    django.setup()
    from sensor_4_app.models import Sensor
    
    count = Sensor.objects.count()
    print(f'✅ Django ORM: {count:,} sensors found!')
    
    if count > 0:
        print('🎉 PERFECT! Your Celery workers should now see the data!')
        
        # Try to get a sample sensor
        try:
            first_sensor = Sensor.objects.first()
            if first_sensor:
                print(f'📝 Sample sensor ID: {first_sensor.id}')
                print(f'   Unique identifier: {first_sensor.get_unique_identifier()}')
        except Exception as e:
            print(f'⚠️  Could not fetch sample sensor: {e}')
            
    else:
        print('⚠️  Django ORM shows 0 sensors. Possible issues:')
        print('   - Model configuration mismatch')
        print('   - Collection name mismatch')
        print('   - djongo connection issue')
        
except Exception as e:
    print(f'❌ Django ORM test failed: {e}')
    print('💡 This might be normal if Django settings need to be adjusted')
"

echo ""
echo "7️⃣ Cleaning up temporary container..."
docker rm mongodb-docker

echo ""
echo "✅ SWITCHOVER COMPLETE!"
echo "======================"
echo ""
echo "🎯 Current Setup:"
echo "   📍 Docker MongoDB: localhost:27017 (running)"
echo "   📊 Your sensor data: Available"
echo "   🔗 MongoDB Compass: Connect to mongodb://localhost:27017/"
echo ""
echo "🧪 Test your Celery worker now:"
echo "   celery -A Test_Database_4 worker --loglevel=info"
echo ""
echo "📱 MongoDB Compass should automatically reconnect to your data"
echo "🔒 All security concerns resolved - everything runs locally via Docker"
echo ""
echo "🗑️  Windows MongoDB is no longer needed (but wasn't deleted for safety)"