#!/bin/bash
# Script to migrate data from Windows MongoDB to Docker MongoDB
# Place in: /mnt/c/PI Local Tests/Test_Database_4/migrate_to_docker.sh

echo "🚀 MIGRATING DATA FROM WINDOWS MONGODB TO DOCKER"
echo "==============================================="

# Step 1: Start Docker MongoDB on port 27018 (so it doesn't conflict)
echo "1️⃣ Starting Docker MongoDB on port 27018..."
docker run -d --name mongodb-docker \
    -p 27018:27017 \
    -v mongodb_data:/data/db \
    mongo:5.0

# Wait for Docker MongoDB to be ready
echo "⏳ Waiting for Docker MongoDB to initialize..."
sleep 10

# Step 2: Test both connections
echo ""
echo "2️⃣ Testing connections..."

echo "Testing Windows MongoDB (port 27017):"
python3 -c "
from pymongo import MongoClient
import sys
import subprocess

# Get Windows IP from WSL
result = subprocess.run(['ip', 'route'], capture_output=True, text=True)
windows_ip = None
for line in result.stdout.split('\n'):
    if 'default' in line:
        windows_ip = line.split()[2]
        break

if not windows_ip:
    print('❌ Could not determine Windows IP')
    sys.exit(1)

print(f'🔍 Detected Windows IP: {windows_ip}')

try:
    # Try Windows IP first
    client = MongoClient(f'mongodb://{windows_ip}:27017', serverSelectionTimeoutMS=5000)
    db = client['LocalTest']
    collections = db.list_collection_names()
    if 'sensor_4_app_sensor' in collections:
        count = db['sensor_4_app_sensor'].count_documents({})
        print(f'✅ Found {count:,} sensors on Windows MongoDB')
        print(f'📍 Connection: mongodb://{windows_ip}:27017')
    else:
        print(f'⚠️  LocalTest database found but no sensors. Collections: {collections}')
    client.close()
except Exception as e:
    print(f'❌ Windows MongoDB connection failed: {e}')
    print('💡 Make sure MongoDB Compass is closed and try again')
    sys.exit(1)
"

# Check if Windows connection test failed
if [ $? -ne 0 ]; then
    echo "❌ Cannot connect to Windows MongoDB. Stopping Docker container..."
    docker stop mongodb-docker
    docker rm mongodb-docker
    exit 1
fi

echo ""
echo "Testing Docker MongoDB (port 27018):"
python3 -c "
from pymongo import MongoClient
try:
    client = MongoClient('mongodb://localhost:27018', serverSelectionTimeoutMS=5000)
    databases = client.list_database_names()
    print(f'✅ Docker MongoDB connected. Databases: {databases}')
    client.close()
except Exception as e:
    print(f'❌ Docker MongoDB connection failed: {e}')
    exit(1)
"

# Check if Docker connection test failed
if [ $? -ne 0 ]; then
    echo "❌ Cannot connect to Docker MongoDB. Stopping..."
    docker stop mongodb-docker
    docker rm mongodb-docker
    exit 1
fi

# Step 3: Perform the migration
echo ""
echo "3️⃣ Starting data migration..."
python3 -c "
from pymongo import MongoClient
import subprocess
import sys

# Get Windows IP
result = subprocess.run(['ip', 'route'], capture_output=True, text=True)
windows_ip = None
for line in result.stdout.split('\n'):
    if 'default' in line:
        windows_ip = line.split()[2]
        break

if not windows_ip:
    print('❌ Could not determine Windows IP')
    sys.exit(1)

try:
    # Connect to both databases
    print(f'🔗 Connecting to Windows MongoDB ({windows_ip}:27017)...')
    source_client = MongoClient(f'mongodb://{windows_ip}:27017', serverSelectionTimeoutMS=10000)
    
    print(f'🔗 Connecting to Docker MongoDB (localhost:27018)...')
    target_client = MongoClient('mongodb://localhost:27018', serverSelectionTimeoutMS=10000)
    
    # Get source database
    source_db = source_client['LocalTest']
    target_db = target_client['LocalTest']
    
    print(f'✅ Connected to both databases')
    
    # Get all collections in LocalTest
    collections = source_db.list_collection_names()
    print(f'📂 Found collections to migrate: {collections}')
    
    if not collections:
        print('⚠️  No collections found in LocalTest database!')
        source_client.close()
        target_client.close()
        sys.exit(1)
    
    total_migrated = 0
    
    for collection_name in collections:
        print(f'\\n📦 Migrating collection: {collection_name}')
        
        source_collection = source_db[collection_name]
        target_collection = target_db[collection_name]
        
        # Get document count
        total_docs = source_collection.count_documents({})
        print(f'   📊 {total_docs:,} documents to migrate')
        
        if total_docs == 0:
            print(f'   ⏩ Skipping empty collection')
            continue
            
        # Clear target collection first (in case of re-run)
        target_collection.drop()
        
        # Migrate in batches to avoid memory issues
        batch_size = 1000
        migrated = 0
        
        # Process in batches
        skip = 0
        while skip < total_docs:
            try:
                batch_docs = list(source_collection.find({}).skip(skip).limit(batch_size))
                
                if not batch_docs:
                    break
                    
                # Insert batch
                target_collection.insert_many(batch_docs)
                migrated += len(batch_docs)
                skip += batch_size
                
                print(f'   ✅ Migrated {migrated:,}/{total_docs:,} documents...')
                
            except Exception as e:
                print(f'   ❌ Error migrating batch: {e}')
                break
        
        print(f'   🎉 Completed: {migrated:,} documents migrated')
        total_migrated += migrated
    
    print(f'\\n🎉 MIGRATION COMPLETE!')
    print(f'📊 Total documents migrated: {total_migrated:,}')
    
    # Verify migration
    print(f'\\n🔍 Verifying migration...')
    if 'sensor_4_app_sensor' in target_db.list_collection_names():
        target_sensor_count = target_db['sensor_4_app_sensor'].count_documents({})
        print(f'✅ Docker MongoDB now has {target_sensor_count:,} sensors')
    else:
        print('⚠️  sensor_4_app_sensor collection not found in target database')
    
    source_client.close()
    target_client.close()
    
except Exception as e:
    print(f'❌ Migration failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

# Check if migration failed
if [ $? -ne 0 ]; then
    echo "❌ Migration failed. Cleaning up..."
    docker stop mongodb-docker
    docker rm mongodb-docker
    exit 1
fi

echo ""
echo "4️⃣ Final verification..."

# Verify the migration worked
echo "Verifying migrated data:"
python3 -c "
from pymongo import MongoClient
try:
    client = MongoClient('mongodb://localhost:27018', serverSelectionTimeoutMS=5000)
    db = client['LocalTest']
    if 'sensor_4_app_sensor' in db.list_collection_names():
        count = db['sensor_4_app_sensor'].count_documents({})
        print(f'✅ SUCCESS: Docker MongoDB has {count:,} sensors!')
        
        # Show sample data
        sample = db['sensor_4_app_sensor'].find_one()
        if sample:
            sample_keys = list(sample.keys())[:10]  # First 10 keys
            print(f'📝 Sample document keys: {sample_keys}')
    else:
        print('❌ sensor_4_app_sensor collection not found!')
    client.close()
except Exception as e:
    print(f'❌ Verification failed: {e}')
"

echo ""
echo "✅ MIGRATION PHASE COMPLETE!"
echo ""
echo "📋 Next steps:"
echo "   1. Review the migration results above"
echo "   2. If successful, run: ./switchover_to_docker.sh"
echo "   3. This will move Docker MongoDB to port 27017"
echo ""
echo "⚠️  Do NOT run the switchover script if migration failed!"