from djongo import models
from .utils.datetime_utils import ensure_datetime

class SensorLabel(models.Model):
    name = models.CharField(primary_key=True, max_length=10, db_index=True)
    description = models.CharField(max_length=100, blank=True, null=True)

# Remove the separate SensorProcessRelation model entirely
# Embed all process relations directly in the Sensor document

class Sensor(models.Model):
    # Batch Fields
    batch_location = models.CharField(max_length=5, blank=False, db_index=True)
    batch_id = models.IntegerField(blank=False, db_index=True)
    total_wafers = models.IntegerField()
    batch_label = models.CharField(max_length=225, blank=True, null=True)
    batch_description = models.CharField(max_length=1000, blank=True, null=True)
    
    # Wafer Fields
    wafer_id = models.IntegerField(db_index=True)
    wafer_label = models.CharField(max_length=225, blank=True, null=True)
    total_sensors = models.IntegerField()
    wafer_description = models.CharField(max_length=1000, blank=True, null=True)
    wafer_design_id = models.CharField(max_length=50, blank=True, null=True)
    
    # Sensor Fields
    sensor_id = models.IntegerField(db_index=True)
    sensor_label = models.CharField(max_length=10, blank=True, null=True)
    sensor_description = models.CharField(max_length=1000, blank=True, null=True)
    
    # Embedded Sensor Processes - This is the key optimization
    processes = models.JSONField(default=list, blank=True)
    
    # Process metadata for faster queries (denormalized)
    process_ids = models.JSONField(default=list, blank=True)  # List of process IDs for indexing 
    last_process_timestamp = models.DateTimeField(null=True, blank=True, db_index=True) # For time based query
    process_count = models.IntegerField(default=0, db_index=True) # For filtering by process activity

    # Unique identifier for fast lookup
    unique_identifier = models.CharField(max_length=20, blank=True, null=True, db_index=True, unique=True)
    
    def get_unique_identifier(self):
        if self.unique_identifier:
            return self.unique_identifier
        
        # Calculate and cache if not present
        batch_id_padded = str(self.batch_id).zfill(3)
        wafer_id_padded = str(self.wafer_id).zfill(2)
        sensor_id_padded = str(self.sensor_id).zfill(3)
        return f"{self.batch_location}{batch_id_padded}-{wafer_id_padded}-{sensor_id_padded}"
    
    def add_processes(self, process_id, description, timestamp):
        """Add a new process to this sensor"""
        # Check if process already exists
        if process_id not in self.process_ids:
            relation = {"process_id": process_id, "description": description, "timestamp": timestamp}
            self.processes.append(relation)
            
            # Update denormalized fields
            self.process_ids.append(process_id)
            self.process_count = len(self.process_ids)
            
            # Update last process timestamp
            if not self.last_process_timestamp or timestamp > self.last_process_timestamp:
                self.last_process_timestamp = timestamp
            
            self.save()
    
    def remove_process(self, process_id):
        """Remove a process from this sensor"""
        # Remove from embedded array
        self.processes = [
            rel for rel in self.processes 
            if rel["process_id"] != process_id
        ]
        
        # Update denormalized fields
        if process_id in self.process_ids:
            self.process_ids.remove(process_id)
            self.process_count = len(self.process_ids)
            
            # Recalculate last process timestamp
            if self.processes:
                self.last_process_timestamp = max(
                    rel['timestamp'] for rel in self.processes
                )
            else:
                self.last_process_timestamp = None
            
            self.save()
    
    def get_processes_by_timerange(self, start_time=None, end_time=None):
        """Get process relations within a time range"""
        relations = self.processes
        
        if start_time:
            relations = [rel for rel in relations if rel['timestamp'] >= start_time]
        if end_time:
            relations = [rel for rel in relations if rel['timestamp'] <= end_time]
            
        return relations
    
    def save(self, *args, **kwargs):
        # Always ensure unique_identifier is set
        if not self.unique_identifier:
            batch_id_padded = str(self.batch_id).zfill(3)
            wafer_id_padded = str(self.wafer_id).zfill(2)
            sensor_id_padded = str(self.sensor_id).zfill(3)
            self.unique_identifier = f"{self.batch_location}{batch_id_padded}-{wafer_id_padded}-{sensor_id_padded}"
        
        # Update denormalized process metadata
        self.process_count = len(self.processes)
        if self.processes:
            self.process_ids = [rel['process_id'] for rel in self.processes]
            self.last_process_timestamp = max(
                ensure_datetime(rel['timestamp']) for rel in self.processes
            )
        else:
            self.process_ids = []
            self.last_process_timestamp = None
            
        super().save(*args, **kwargs)
    
    class Meta:
        db_table = 'batch_encoder_sensor'
        indexes = [
            models.Index(fields=['batch_location', 'batch_id']),
            models.Index(fields=['wafer_id', 'sensor_id']),
            # Compound indexes for common query patterns
            models.Index(fields=['batch_location', 'process_count']),
            models.Index(fields=['unique_identifier', 'process_count']),
        ]
    
    objects = models.DjongoManager()


# Keep your Image and ImageGroup models as they are - they're already well optimized
class Image(models.Model):
    sensor = models.ForeignKey(Sensor, related_name='images', on_delete=models.CASCADE)
    process_id = models.CharField(max_length=10, blank=True, null=True)
    image = models.ImageField(upload_to='sensor-images/')
    original_file = models.ImageField(upload_to='sensor-images/tiffs', null=True)
    
    # Additional fields for better MongoDB Performance
    sensor_unique_id = models.CharField(max_length=20, blank=True, null=True, db_index=True)
    file_name = models.CharField(max_length=255, blank=True, null=True)
    file_suffix = models.CharField(max_length=10, blank=True, null=True)
    upload_date = models.DateTimeField(auto_now=True, db_index=True)
    
    def save(self, *args, **kwargs):
        # Pre-compute fields for better query performance
        if self.sensor and not self.sensor_unique_id:
            self.sensor_unique_id = self.sensor.get_unique_identifier()
            
        if self.image and not self.file_name:
            import os
            self.file_name = os.path.basename(self.image.name)
            base, ext = os.path.splitext(self.file_name)
            if '_' in base:
                self.file_suffix = base.split('_')[-1]
                
        super().save(*args, **kwargs)
        
    class Meta:
        db_table = 'batch_encoder_image'
        indexes = [
            models.Index(fields=['sensor_unique_id', 'process_id']),
            models.Index(fields=['process_id', 'upload_date']),
            models.Index(fields=['sensor', 'process_id']),
        ]

class ImageGroup(models.Model):
    """
    Denormalized collection to store pre-grouped image data
    This can be populated via background tasks or signals
    """
    sensor_unique_id = models.CharField(max_length=20, db_index=True)
    process_id = models.CharField(max_length=10, blank=True, null=True, db_index=True)
    group_key = models.CharField(max_length=50, unique=True, db_index=True)
    
    images_data = models.JSONField(default=list)
    image_count = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    
    created_date = models.DateTimeField(auto_now_add=True, db_index=True)
    batch_location = models.CharField(max_length=5, blank=True, null=True, db_index=True)
    batch_id = models.IntegerField(blank=True, null=True, db_index=True)
    
    def add_image(self, image_instance):
        import os
        filename = os.path.basename(image_instance.image.name)
        base, ext = os.path.splitext(filename)

        image_data = {
            'id': str(image_instance.id),
            'display_url': image_instance.image.url,
            'original_url': image_instance.original_file.url if image_instance.original_file else None,
            'file_name': filename,
            'suffix': base.split('_')[-1] if '_' in base else '',
            'upload_date': image_instance.upload_date.isoformat() if image_instance.upload_date else None
        }

        if not any(img['id'] == image_data['id'] for img in self.images_data):
            self.images_data.append(image_data)
            self.image_count = len(self.images_data)
            self.save()

    @classmethod
    def get_or_create_group(cls, sensor_unique_id, process_id):
        """Get or create a group for sensor/process combination"""
        group_key = f"{sensor_unique_id}|{process_id or 'Unspecified'}"
        batch_location = sensor_unique_id[:4] if sensor_unique_id else None
        try:
            batch_id = int(sensor_unique_id[5:7]) if len(sensor_unique_id) >= 7 else None
        except (ValueError, TypeError):
            batch_id = None
            
        group, created = cls.objects.get_or_create(
            group_key=group_key,
            defaults={
                'sensor_unique_id': sensor_unique_id,
                'process_id': process_id,
                'images_data': [],
                'image_count': 0,
                'batch_location': batch_location,
                'batch_id': batch_id
            }
        )
        return group
    
    @classmethod
    def bulk_create_for_sensors_and_processes(cls, sensor_unique_ids, process_ids):
        groups_to_create = []
        
        for sensor_unique_id in sensor_unique_ids:
            batch_location = sensor_unique_id[:4] if sensor_unique_id else None
            try:
                batch_id = int(sensor_unique_id[4:7]) if len(sensor_unique_id) >= 7 else None
            except (ValueError, TypeError):
                batch_id = None
                
            for process_id in process_ids:
                group_key = f"{sensor_unique_id}|{process_id}"
                groups_to_create.append(
                    cls(
                        sensor_unique_id=sensor_unique_id,
                        process_id=process_id,
                        group_key=group_key,
                        images_data=[],
                        image_count=0,
                        batch_location=batch_location,
                        batch_id=batch_id
                    )
                )
        
        created_groups = cls.objects.bulk_create(groups_to_create, ignore_conflicts=True)
        return len(groups_to_create)
    
    class Meta:
        db_table = 'batch_encoder_image_group'
        indexes = [
            models.Index(fields=['sensor_unique_id', 'process_id']),
            models.Index(fields=['batch_location', 'batch_id']),
            models.Index(fields=['image_count']),
        ]

# Signal handlers remain the same
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=Image)
def update_image_group_on_save(sender, instance, created, **kwargs):
    """Update ImageGroup when an Image is saved"""
    if created and instance.sensor:
        sensor_id = instance.sensor.get_unique_identifier()
        group = ImageGroup.get_or_create_group(sensor_id, instance.process_id)
        group.add_image(instance)

@receiver(post_delete, sender=Image)
def update_image_group_on_delete(sender, instance, **kwargs):
    """Update ImageGroup when an Image is deleted"""
    if instance.sensor:
        sensor_id = instance.sensor.get_unique_identifier()
        group_key = f"{sensor_id}|{instance.process_id or 'Unspecified'}"
        
        try:
            group = ImageGroup.objects.get(group_key=group_key)
            group.images_data = [
                img for img in group.images_data 
                if img['id'] != str(instance.id)
            ]
            group.image_count = len(group.images_data)
            
            if group.image_count == 0:
                group.delete()
            else:
                group.save()
        except ImageGroup.DoesNotExist:
            pass