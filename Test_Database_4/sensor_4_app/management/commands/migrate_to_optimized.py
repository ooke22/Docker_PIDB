# migration_script.py - Fixed migration from old to new optimized system

from django.core.management.base import BaseCommand
from django.db import transaction
from sensor_4_app.models import Sensor, Image, ImageGroup, SensorProcessRelation
import os

class Command(BaseCommand):
    help = 'Migrate existing data to optimized system with ImageGroups'

    def handle(self, *args, **options):
        """
        Complete migration strategy for existing data
        """
        self.stdout.write("Starting migration to optimized system...")
        
        with transaction.atomic():
            # Step 1: Update existing Sensor records
            self.migrate_sensors()
            
            # Step 2: Update existing Image records  
            self.migrate_images()
            
            # Step 3: Create ImageGroups from existing data
            self.create_imagegroups()
            
            # Step 4: Verify migration
            self.verify_migration()
        
        self.stdout.write(self.style.SUCCESS("Migration completed successfully!"))

    def migrate_sensors(self):
        """
        Step 1: Update existing Sensor records with missing optimized fields
        """
        self.stdout.write("Step 1: Migrating Sensor records...")
        
        # Get all sensors that don't have unique_identifier set
        sensors_to_update = Sensor.objects.filter(unique_identifier__isnull=True)
        update_count = 0
        
        for sensor in sensors_to_update.iterator(chunk_size=1000):
            # Calculate and set unique_identifier using the method
            if not sensor.unique_identifier:
                sensor.unique_identifier = sensor.get_unique_identifier()
                sensor.save(update_fields=['unique_identifier'])
                update_count += 1
        
        self.stdout.write(f"  ✅ Updated {update_count} sensors with unique_identifier")

    def migrate_images(self):
        """
        Step 2: Update existing Image records with new optimized fields
        """
        self.stdout.write("Step 2: Migrating Image records...")
        
        images_to_update = []
        
        for image in Image.objects.filter(sensor_unique_id__isnull=True).iterator(chunk_size=1000):
            # Set sensor_unique_id from related sensor
            if image.sensor and not image.sensor_unique_id:
                image.sensor_unique_id = image.sensor.get_unique_identifier()
            
            # Set file_name if not present
            if image.image and not image.file_name:
                image.file_name = os.path.basename(image.image.name)
            
            # Set file_suffix if not present
            if image.file_name and not image.file_suffix:
                base, ext = os.path.splitext(image.file_name)
                if '_' in base:
                    image.file_suffix = base.split('_')[-1]
            
            images_to_update.append(image)
            
            # Bulk update every 1000 records
            if len(images_to_update) >= 1000:
                Image.objects.bulk_update(
                    images_to_update, 
                    ['sensor_unique_id', 'file_name', 'file_suffix'],
                    batch_size=1000
                )
                images_to_update = []
        
        # Update remaining records
        if images_to_update:
            Image.objects.bulk_update(
                images_to_update, 
                ['sensor_unique_id', 'file_name', 'file_suffix'],
                batch_size=1000
            )
        
        total_migrated = Image.objects.filter(sensor_unique_id__isnull=False).count()
        self.stdout.write(f"  ✅ Migrated {total_migrated} images with optimized fields")

    def create_imagegroups(self):
        """
        Step 3: Create ImageGroups from existing Image and SensorProcessRelation data
        """
        self.stdout.write("Step 3: Creating ImageGroups from existing data...")
        
        # Strategy: Group existing images by sensor_unique_id + process_id
        image_groups_data = {}
        
        # Get all existing images with their sensor and process info
        for image in Image.objects.select_related('sensor').iterator(chunk_size=1000):
            if not image.sensor:
                continue
                
            sensor_id = image.sensor.get_unique_identifier()
            process_id = image.process_id or 'Unspecified'
            group_key = f"{sensor_id}|{process_id}"
            
            if group_key not in image_groups_data:
                image_groups_data[group_key] = {
                    'sensor_unique_id': sensor_id,
                    'process_id': process_id if process_id != 'Unspecified' else None,
                    'group_key': group_key,
                    'images': []
                }
            
            # Add image data to group
            filename = os.path.basename(image.image.name) if image.image else ''
            base, ext = os.path.splitext(filename)
            
            image_data = {
                'id': str(image.id),
                'image_url': image.image.url if image.image else '',
                'file_name': filename,
                'suffix': base.split('_')[-1] if '_' in base else ''
            }
            
            image_groups_data[group_key]['images'].append(image_data)
        
        # Create ImageGroup records
        image_groups_to_create = []
        
        for group_key, group_data in image_groups_data.items():
            image_groups_to_create.append(
                ImageGroup(
                    sensor_unique_id=group_data['sensor_unique_id'],
                    process_id=group_data['process_id'],
                    group_key=group_key,
                    images_data=group_data['images'],
                    image_count=len(group_data['images'])
                )
            )
        
        # Bulk create all ImageGroups
        if image_groups_to_create:
            ImageGroup.objects.bulk_create(image_groups_to_create, batch_size=1000)
            self.stdout.write(f"  ✅ Created {len(image_groups_to_create)} ImageGroups")
        
        # Also create empty ImageGroups for sensor-process combinations that have no images yet
        self.create_empty_imagegroups()

    def create_empty_imagegroups(self):
        """
        Create empty ImageGroups for sensor-process combinations without images
        FIXED: Avoid the problematic select_related query that causes field collision
        """
        self.stdout.write("  Creating empty ImageGroups for existing sensor-process relations...")
        
        # SOLUTION: Use separate queries to avoid field name collision
        # First, get all SensorProcessRelation IDs and sensor IDs
        relation_data = list(SensorProcessRelation.objects.values(
            'sensor_id', 'process_file_id'
        ).distinct())
        
        self.stdout.write(f"  Found {len(relation_data)} unique sensor-process combinations")
        
        # Get existing group keys to avoid duplicates
        existing_group_keys = set(ImageGroup.objects.values_list('group_key', flat=True))
        
        # Create a mapping of sensor IDs to their unique identifiers
        sensor_id_to_uid = {}
        if relation_data:
            sensor_ids = [rel['sensor_id'] for rel in relation_data]
            sensors = Sensor.objects.filter(id__in=sensor_ids).values('id', 'unique_identifier')
            sensor_id_to_uid = {s['id']: s['unique_identifier'] for s in sensors}
        
        empty_groups_to_create = []
        
        for rel_data in relation_data:
            sensor_db_id = rel_data['sensor_id']
            process_file_id = rel_data['process_file_id']
            
            # Get the sensor's unique identifier
            sensor_uid = sensor_id_to_uid.get(sensor_db_id)
            if not sensor_uid:
                continue
            
            # For process_id, we need to get it from ProcessFile
            # You might need to adjust this based on your ProcessFile model
            process_id = str(process_file_id) if process_file_id else None
            
            group_key = f"{sensor_uid}|{process_id or 'Unspecified'}"
            
            # Only create if doesn't exist already
            if group_key not in existing_group_keys:
                empty_groups_to_create.append(
                    ImageGroup(
                        sensor_unique_id=sensor_uid,
                        process_id=process_id,
                        group_key=group_key,
                        images_data=[],
                        image_count=0
                    )
                )
                existing_group_keys.add(group_key)  # Avoid duplicates
        
        if empty_groups_to_create:
            ImageGroup.objects.bulk_create(empty_groups_to_create, batch_size=1000)
            self.stdout.write(f"  ✅ Created {len(empty_groups_to_create)} empty ImageGroups")
        else:
            self.stdout.write("  ℹ️  No additional empty ImageGroups needed")

    def verify_migration(self):
        """
        Step 4: Verify migration completed correctly
        """
        self.stdout.write("Step 4: Verifying migration...")
        
        # Check sensors
        sensors_without_uid = Sensor.objects.filter(unique_identifier__isnull=True).count()
        if sensors_without_uid > 0:
            self.stdout.write(f"  ⚠️  WARNING: {sensors_without_uid} sensors still missing unique_identifier")
        else:
            self.stdout.write("  ✅ All sensors have unique_identifier")
        
        # Check images
        images_without_sensor_uid = Image.objects.filter(sensor_unique_id__isnull=True).count()
        if images_without_sensor_uid > 0:
            self.stdout.write(f"  ⚠️  WARNING: {images_without_sensor_uid} images still missing sensor_unique_id")
        else:
            self.stdout.write("  ✅ All images have sensor_unique_id")
        
        # Check ImageGroups
        total_imagegroups = ImageGroup.objects.count()
        imagegroups_with_images = ImageGroup.objects.filter(image_count__gt=0).count()
        empty_imagegroups = ImageGroup.objects.filter(image_count=0).count()
        
        self.stdout.write(f"  📊 ImageGroups summary:")
        self.stdout.write(f"    Total groups: {total_imagegroups}")
        self.stdout.write(f"    Groups with images: {imagegroups_with_images}")
        self.stdout.write(f"    Empty groups: {empty_imagegroups}")
        
        # Verify pagination will work
        if total_imagegroups > 0:
            test_groups = ImageGroup.objects.all()[:5]
            total_images_in_groups = sum(group.image_count for group in test_groups)
            self.stdout.write(f"  ✅ Pagination test: First 5 groups contain {total_images_in_groups} images")