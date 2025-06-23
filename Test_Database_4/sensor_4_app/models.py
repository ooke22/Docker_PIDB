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
        # batch_id with zero padding
        batch_id_padded = str(self.batch_id).zfill(3)
        # wafer_id with zero padding
        wafer_id_padded = str(self.wafer_id).zfill(2)
        # sensor_id with zero padding
        sensor_id_padded = str(self.sensor_id).zfill(3)
        return f"{self.batch_location}{batch_id_padded}-{wafer_id_padded}-{sensor_id_padded}"

    objects = models.DjongoManager()
    

class Image(models.Model):
    sensor = models.ForeignKey(Sensor, related_name='images', on_delete=models.CASCADE)
    process_id = models.CharField(max_length=10, blank=True, null=True)
    image = models.ImageField(upload_to='sensor-images/')
