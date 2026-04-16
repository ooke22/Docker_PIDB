from celery import shared_task
from .models import ImageGroup, Image, Sensor, SensorProcessRelation, ProcessFile
from django.utils import timezone
from django.db import transaction
from datetime import datetime
import logging
from pymongo import MongoClient
import os
import sys

logger = logging.getLogger(__name__)


@shared_task
def create_imagegroups_task(unique_identifiers, sensor_processes):
    """ 
    Background task to create ImageGroups for sensors and processes.
    """
    
    image_groups_to_create = []
    
    for unique_identifier in unique_identifiers:
        for process_data in sensor_processes:
            process_id = process_data.get('process_id')
            if process_id:
                group_key = f"{unique_identifier}|{process_id}"
                image_groups_to_create.append(
                    ImageGroup(
                        sensor_unique_id=unique_identifier,
                        process_id=process_id,
                        group_key=group_key,
                        images_data=[],
                        image_count=0
                    )
                )
                
    # Bulk create with conflict handling
    ImageGroup.objects.bulk_create(image_groups_to_create, batch_size=1000, ignore_conflicts=True)
    return len(image_groups_to_create)


@shared_task(bind=True)
def create_batch_async(self, batch_data):
    """
    Async task to create sensors and process relations
    Returns task status and results
    """
    try:
        # Update task state to PROGRESS
        self.update_state(
            state='PROGRESS',
            meta={'status': 'Starting batch creation...', 'progress': 0}
        )
        
        # Extract data
        batch_location = batch_data.get('batch_location')
        batch_id = batch_data.get('batch_id')
        batch_label = batch_data.get('batch_label', '')
        batch_description = batch_data.get('batch_description', '')
        total_wafers = int(batch_data['total_wafers'])
        total_sensors = int(batch_data['total_sensors'])
        sensor_processes = batch_data.get('sensor_processes', [])
        
        total_operations = 3  # sensors creation, relations creation, completion
        current_operation = 0
        
        # Pre-validate and cache ProcessFiles
        process_files_cache = {}
        valid_process_data = []
        
        if sensor_processes:
            process_ids = [p.get('process_id') for p in sensor_processes if p.get('process_id')]
            if process_ids:
                process_files = ProcessFile.objects.filter(process_id__in=process_ids)
                process_files_cache = {pf.process_id: pf for pf in process_files}
                valid_process_data = [
                    p for p in sensor_processes 
                    if p.get('process_id') in process_files_cache
                ]
        
        with transaction.atomic():
            # Update progress
            current_operation += 1
            self.update_state(
                state='PROGRESS',
                meta={
                    'status': 'Creating sensors...', 
                    'progress': int((current_operation / total_operations) * 100)
                }
            )
            
            # Create sensors
            batch_id_padded = str(batch_id).zfill(3)
            sensors_to_create = []
            
            for wafer_id in range(1, total_wafers + 1):
                wafer_id_padded = str(wafer_id).zfill(2)
                
                for sensor_id in range(1, total_sensors + 1):
                    sensor_id_padded = str(sensor_id).zfill(3)
                    unique_identifier = f"{batch_location}{batch_id_padded}-{wafer_id_padded}-{sensor_id_padded}"
                    
                    sensor = Sensor(
                        batch_location=batch_location,
                        batch_id=batch_id,
                        batch_label=batch_label,
                        batch_description=batch_description,
                        total_wafers=total_wafers,
                        wafer_id=wafer_id,
                        wafer_label=batch_data.get('wafer_label', ''),
                        wafer_description=batch_data.get('wafer_description', ''),
                        wafer_design_id=batch_data.get('wafer_design_id', ''),
                        total_sensors=total_sensors,
                        sensor_id=sensor_id,
                        sensor_description=batch_data.get('sensor_description', ''),
                        unique_identifier=unique_identifier
                    )
                    
                    sensors_to_create.append(sensor)
            
            # Bulk create sensors
            Sensor.objects.bulk_create(sensors_to_create, batch_size=1000)
            
            # Update progress
            current_operation += 1
            self.update_state(
                state='PROGRESS',
                meta={
                    'status': 'Creating process relations...', 
                    'progress': int((current_operation / total_operations) * 100)
                }
            )
            
            # Create process relations
            relations_created = 0
            if valid_process_data:
                relations_created = _create_process_relations_fast(
                    sensors_to_create, valid_process_data, process_files_cache
                )
            
            # Final update
            current_operation += 1
            self.update_state(
                state='PROGRESS',
                meta={
                    'status': 'Finalizing...', 
                    'progress': int((current_operation / total_operations) * 100)
                }
            )
        
        # Return success result
        return {
            'status': 'SUCCESS',
            'sensors_created': len(sensors_to_create),
            'process_relations_created': relations_created,
            'processes_attached': list(process_files_cache.keys()),
            'batch_location': batch_location,
            'batch_id': batch_id
        }
        
    except Exception as e:
        logger.error(f"Async batch creation failed: {str(e)}")
        # Return failure result
        return {
            'status': 'FAILURE',
            'error': str(e)
        }

def _create_process_relations_fast(sensors_to_create, valid_process_data, process_files_cache):
    """
    Optimized process relation creation for async task
    """
    # Get saved sensors
    unique_identifiers = [s.unique_identifier for s in sensors_to_create]
    saved_sensors = Sensor.objects.filter(unique_identifier__in=unique_identifiers)
    sensor_lookup = {s.unique_identifier: s for s in saved_sensors}
    
    relations_to_create = []
    
    for process_data in valid_process_data:
        process_id = process_data.get('process_id')
        timestamp = process_data.get('timestamp')
        
        if timestamp:
            timestamp = timestamp.rstrip('Z')
            timestamp = datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc)
        else:
            timestamp = timezone.now()
        
        process_file = process_files_cache[process_id]
        
        for unique_identifier in unique_identifiers:
            sensor = sensor_lookup.get(unique_identifier)
            if sensor:
                relations_to_create.append(
                    SensorProcessRelation(
                        process_file=process_file,
                        timestamp=timestamp,
                        sensor=sensor,
                        unique_identifier=unique_identifier
                    )
                )
    
    if relations_to_create:
        SensorProcessRelation.objects.bulk_create(relations_to_create, batch_size=1000)
    
    return len(relations_to_create)


@shared_task(bind=True)
def create_batch_async_3(self, batch_data):
    """
    Minimal test version to identify where it's hanging
    """
    try:
        print(f"🚀 TASK STARTED - ID: {self.request.id}")
        
        # Test 1: Basic progress update
        self.update_state(
            state='PROGRESS',
            meta={'status': 'Testing progress update...', 'progress': 25}
        )
        print("✅ Progress update successful")
        
        # Test 2: Database connection
        from django.db import connection
        connection.ensure_connection()
        print("✅ Database connection successful")
        
        # Test 3: Model import
        from .models import Sensor
        print("✅ Model import successful")
        
        # Test 4: Simple query
        sensor_count = Sensor.objects.count()
        print(f"✅ Database query successful - existing sensors: {sensor_count}")
        
        print("🎉 ALL TESTS PASSED - Task completing")
        
        return {
            'status': 'SUCCESS',
            'message': 'All tests passed',
            'existing_sensors': sensor_count
        }
        
    except Exception as e:
        print(f"❌ TASK FAILED at step: {e}")
        import traceback
        traceback.print_exc()
        return {
            'status': 'FAILURE', 
            'error': str(e)
        }


@shared_task(bind=True)
def create_batch_async_2(self, batch_data):
    """
    Debug why LocalTest database shows 0 sensors despite having 20k+ records
    """
    try:
        print(f"🚀 DEBUGGING LocalTest DATABASE - ID: {self.request.id}")
        
        # Check IS_TESTING variable
        IS_TESTING = 'test' in sys.argv or 'pytest' in sys.argv[0]
        print(f"📋 IS_TESTING: {IS_TESTING}")
        print(f"📋 sys.argv: {sys.argv}")
        
        # Check Django database configuration
        from django.conf import settings
        db_config = settings.DATABASES['default']
        expected_db = db_config['CLIENT']['name']
        print(f"🎯 Django configured to use database: {expected_db}")
        
        # Direct MongoDB connection to LocalTest
        print("\n🔍 DIRECT MONGODB CONNECTION TO LocalTest:")
        client = MongoClient('mongodb://localhost:27017')
        localtest_db = client['LocalTest']
        
        collections = localtest_db.list_collection_names()
        print(f"📂 Collections in LocalTest: {collections}")
        
        # Check all collections for documents
        total_docs = 0
        for collection_name in collections:
            collection = localtest_db[collection_name]
            count = collection.count_documents({})
            total_docs += count
            print(f"   📊 {collection_name}: {count} documents")
            
            # Show sample document structure if documents exist
            if count > 0:
                sample = collection.find_one()
                print(f"      Sample document keys: {list(sample.keys()) if sample else 'None'}")
        
        print(f"\n📈 Total documents in LocalTest: {total_docs}")
        
        # Check Django ORM connection
        print("\n🔍 DJANGO ORM CONNECTION:")
        from django.db import connection
        connection.ensure_connection()
        
        # Verify which database Django is actually using
        try:
            # For djongo, get the actual MongoDB database name
            db_name = connection.settings_dict['CLIENT']['name']
            print(f"✅ Django ORM connected to: {db_name}")
        except Exception as e:
            print(f"⚠️  Could not determine Django database name: {e}")
        
        # Check Sensor model and its collection
        print("\n🔍 SENSOR MODEL ANALYSIS:")
        from sensor_4_app.models import Sensor
        
        # Get the collection name that Django/djongo is using
        collection_name = Sensor._meta.db_table
        print(f"📋 Sensor model uses collection: {collection_name}")
        
        # Check if this collection exists in LocalTest
        if collection_name in collections:
            direct_count = localtest_db[collection_name].count_documents({})
            print(f"📊 Direct count in '{collection_name}' collection: {direct_count}")
        else:
            print(f"❌ Collection '{collection_name}' not found in LocalTest!")
            print(f"   Available collections: {collections}")
        
        # Django ORM query
        try:
            orm_count = Sensor.objects.count()
            print(f"📊 Django ORM count: {orm_count}")
            
            # If count is 0 but collection has docs, there might be a schema issue
            if orm_count == 0 and collection_name in collections:
                direct_count = localtest_db[collection_name].count_documents({})
                if direct_count > 0:
                    print("⚠️  MISMATCH: Direct query shows documents, ORM shows 0!")
                    print("   This suggests a model/schema compatibility issue")
                    
                    # Show sample document vs model fields
                    sample_doc = localtest_db[collection_name].find_one()
                    model_fields = [f.name for f in Sensor._meta.fields]
                    
                    print(f"   📝 Sample document fields: {list(sample_doc.keys()) if sample_doc else 'None'}")
                    print(f"   📝 Model fields: {model_fields}")
                    
        except Exception as e:
            print(f"❌ Django ORM query failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Test raw query to understand the issue
        print("\n🔍 RAW QUERY TEST:")
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                # For djongo, we can try a raw MongoDB query
                cursor.execute("db.sensor_4_app_sensor.find().limit(1)")
                print("✅ Raw query executed (djongo)")
        except Exception as e:
            print(f"⚠️  Raw query failed: {e}")
        
        return {
            'status': 'SUCCESS',
            'is_testing': IS_TESTING,
            'configured_database': expected_db,
            'total_documents_in_localtest': total_docs,
            'collections': collections,
            'sensor_collection': collection_name,
            'orm_sensor_count': orm_count if 'orm_count' in locals() else 'failed'
        }
        
    except Exception as e:
        print(f"❌ DEBUG TASK FAILED: {e}")
        import traceback
        traceback.print_exc()
        return {
            'status': 'FAILURE',
            'error': str(e),
            'traceback': traceback.format_exc()
        }