#!/usr/bin/env python3
"""
Simple test to find your Windows MongoDB
"""

from pymongo import MongoClient
import subprocess

def test_mongodb_connections():
    print("🔍 TESTING MONGODB CONNECTION METHODS")
    print("====================================")
    
    # Get possible IPs
    possible_connections = []
    
    # Method 1: Try localhost (sometimes works in WSL)
    possible_connections.append(('127.0.0.1', 27017))
    
    # Method 2: Get Windows IP from WSL
    try:
        result = subprocess.run(['ip', 'route'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'default' in line:
                windows_ip = line.split()[2]
                possible_connections.append((windows_ip, 27017))
                break
    except:
        pass
    
    # Method 3: Try common WSL Windows IPs
    common_ips = ['172.22.0.1', '172.20.0.1', '192.168.1.1', '10.0.0.1']
    for ip in common_ips:
        possible_connections.append((ip, 27017))
    
    # Remove duplicates
    unique_connections = list(set(possible_connections))
    
    print(f"Testing {len(unique_connections)} possible connections...\n")
    
    successful_connections = []
    
    for ip, port in unique_connections:
        print(f"🔍 Testing {ip}:{port}")
        try:
            client = MongoClient(f'mongodb://{ip}:{port}', serverSelectionTimeoutMS=10000)
            
            # Test connection
            databases = client.list_database_names()
            print(f"   ✅ Connected! Databases: {databases}")
            
            # Check for LocalTest
            if 'LocalTest' in databases:
                db = client['LocalTest']
                collections = db.list_collection_names()
                print(f"   📂 LocalTest collections: {collections}")
                
                # Check for sensors
                if 'sensor_4_app_sensor' in collections:
                    count = db['sensor_4_app_sensor'].count_documents({})
                    print(f"   🎯 SENSORS FOUND: {count:,}")
                    successful_connections.append((ip, port, count))
                else:
                    print(f"   ⚠️  No sensor_4_app_sensor collection")
            else:
                print(f"   ⚠️  No LocalTest database")
                
            client.close()
            
        except Exception as e:
            print(f"   ❌ Failed: {str(e)[:60]}...")
        
        print()
    
    print("=" * 50)
    if successful_connections:
        print("✅ SUCCESSFUL CONNECTIONS WITH SENSOR DATA:")
        for ip, port, count in successful_connections:
            print(f"   🎯 {ip}:{port} - {count:,} sensors")
        
        # Use the first successful connection
        best_connection = successful_connections[0]
        print(f"\n💡 RECOMMENDED CONNECTION: {best_connection[0]}:{best_connection[1]}")
        
        return f"{best_connection[0]}:{best_connection[1]}"
    else:
        print("❌ NO SUCCESSFUL CONNECTIONS FOUND")
        print("\n💡 TROUBLESHOOTING:")
        print("1. Make sure MongoDB Windows service is running")
        print("2. Close MongoDB Compass completely")
        print("3. Check Windows Services for 'MongoDB' service")
        print("4. Try restarting MongoDB service in Windows")
        
        return None

if __name__ == "__main__":
    result = test_mongodb_connections()
    if result:
        print(f"\n✅ Use this connection string in migration: mongodb://{result}")
    else:
        print(f"\n❌ Unable to connect to Windows MongoDB")