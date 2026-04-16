from djongo import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from process_encoder.models import ProcessFile

class SensorLabel(models.Model):
    name = models.CharField(primary_key=True, max_length=10, db_index=True)
    description = models.CharField(max_length=100, blank=True, null=True)

class SensorProcessRelation(models.Model): # Previously WaferProcessRelation
    process_file = models.ForeignKey(ProcessFile, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    sensor = models.ForeignKey('Sensor', on_delete=models.CASCADE, related_name='process_relations', db_column='sensor')  # Renamed 'electrode' to 'sensor'
    unique_identifier = models.CharField(max_length=100, db_index=True)
    
    class Meta:
        unique_together = ('process_file', 'sensor')


class Sensor(models.Model): # Previously Electrode
    # Batch Fields
    batch_location = models.CharField(max_length=5, blank=False, db_index=True)  # Indexed
    batch_id = models.IntegerField(blank=False, db_index=True)  # Indexed
    total_wafers = models.IntegerField()
    batch_label = models.CharField(max_length=225, blank=True, null=True)
    batch_description = models.CharField(max_length=1000, blank=True, null=True)

    # Wafer Fields
    wafer_id = models.IntegerField(db_index=True)  # Indexed
    wafer_label = models.CharField(max_length=225, blank=True, null=True)
    total_sensors = models.IntegerField()
    wafer_description = models.CharField(max_length=1000, blank=True, null=True)
    wafer_design_id = models.CharField(max_length=50, blank=True, null=True)
  

    # Sensor Fields
    sensor_id = models.IntegerField(db_index=True)  # Indexed
    sensor_label = models.CharField(max_length=225, blank=True, null=True)
    sensor_description = models.CharField(max_length=1000, blank=True, null=True)

    # Relationships
    sensor_process_relations = models.ManyToManyField(ProcessFile, through=SensorProcessRelation, related_name='related_processes')  # Rename related_name and through
    
    # Label
    label = models.ForeignKey(SensorLabel, on_delete=models.SET_NULL, null=True, blank=True, related_name='sensors')
    
    # New field for faster lookup
    unique_identifier = models.CharField(max_length=20, blank=True, null=True, db_index=True)

    def get_unique_identifier(self):
        if self.unique_identifier:
            return self.unique_identifier
        
        # Calculate and cache if not present
        # batch_id with zero padding
        batch_id_padded = str(self.batch_id).zfill(3)
        # wafer_id with zero padding
        wafer_id_padded = str(self.wafer_id).zfill(2)
        # sensor_id with zero padding
        sensor_id_padded = str(self.sensor_id).zfill(3)
        return f"{self.batch_location}{batch_id_padded}-{wafer_id_padded}-{sensor_id_padded}"
        
    
    def save(self, *args, **kwargs):
        # Always ensure unique_identifier is set
        if not self.unique_identifier:
            batch_id_padded = str(self.batch_id).zfill(3)
            wafer_id_padded = str(self.wafer_id).zfill(2)
            sensor_id_padded = str(self.sensor_id).zfill(3)
            self.unique_identifier = f"{self.batch_location}{batch_id_padded}-{wafer_id_padded}-{sensor_id_padded}"
        super().save(*args, **kwargs)
        
    class Meta:
        db_table = 'sensor_4_app_sensor'
        # MongoDB-friendly indexes
        indexes = [
            models.Index(fields=['unique_identifier']),
            models.Index(fields=['batch_location', 'batch_id']),
            models.Index(fields=['wafer_id', 'sensor_id']),
        ]
        

    objects = models.DjongoManager()
    

class Image(models.Model):
    sensor = models.ForeignKey(Sensor, related_name='images', on_delete=models.CASCADE)
    process_id = models.CharField(max_length=10, blank=True, null=True)
    image = models.ImageField(upload_to='sensor-images/')
    original_file = models.ImageField(upload_to='sensor-images/tiffs')
    
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
        db_table = 'sensor_4_app_image'
        # Compound indexes for MongoDB efficiency
        indexes = [
            models.Index(fields=['sensor_unique_id', 'process_id']),
            models.Index(fields=['process_id', 'upload_date']),
            models.Index(fields=['sensor', 'process_id']),
        ]

# Denormalized model for even better performance
class ImageGroup(models.Model):
    """
    Denormalized collection to store pre-grouped image data
    This can be populated via background tasks or signals
    """
    sensor_unique_id = models.CharField(max_length=20, db_index=True)
    process_id = models.CharField(max_length=10, blank=True, null=True, db_index=True)
    group_key = models.CharField(max_length=50, unique=True, db_index=True)
    
    # Store as embedded document (Djongo supports this)
    images_data = models.JSONField(default=list)  # List of image metadata
    image_count = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    
    # New fields to improve query performance
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

        # Check if image with this id already exists
        if not any(img['id'] == image_data['id'] for img in self.images_data):
            self.images_data.append(image_data)
            self.image_count = len(self.images_data)
            self.save()

    
    @classmethod
    def get_or_create_group(cls, sensor_unique_id, process_id):
        """Get or create a group for sensor/process combination"""
        group_key = f"{sensor_unique_id}|{process_id or 'Unspecified'}"
        # Batch info for denormilization
        batch_location = sensor_unique_id[:4] if sensor_unique_id else None
        try:
            batch_id = int(sensor_unique_id[4:7]) if len(sensor_unique_id) >= 7 else None
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
    
    # Bulk operations for PUT functions
    @classmethod
    def bulk_create_for_sensors_and_processes(cls, sensor_unique_ids, process_ids):
        """ 
        Efficiently create ImageGroups fpr multiple sensor+process combinations
        Used by PUT functions
        """
        groups_to_create = []
        
        for sensor_unique_id in sensor_unique_ids:
            # Extract batch info once per sensor
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
        
        # Bulk create with conflict handling
        created_groups = cls.objects.bulk_create(groups_to_create, ignore_conflicts=True)
        return len(groups_to_create) # Return count for reporting
    
    class Meta:
        db_table = 'image_group'
        indexes = [
            models.Index(fields=['sensor_unique_id', 'process_id']),
            models.Index(fields=['group_key']),
            models.Index(fields=['batch_location', 'batch_id']), # For batch-level queries
            models.Index(fields=['created_date']), # For time-based queries
            models.Index(fields=['image_count']), # For finding empty groups
        ]


# Signal to maintain ImageGroup denormalized data
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
            # Remove the image from the group
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
        

