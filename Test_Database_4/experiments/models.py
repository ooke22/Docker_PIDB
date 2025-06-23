from djongo import models
from sensor_4_app.models import Sensor

class ExperimentTest(models.Model):
    test_id = models.CharField(max_length=20, unique=True, db_index=True)
    test_date = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Experiment {self.test_id}"
    
class ExperimentSensorRelation(models.Model):
    experiment = models.ForeignKey(ExperimentTest, on_delete=models.CASCADE)
    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=[
        ('WE', 'Working Electrode'),
        ('RE', 'Reference Electrode')
    ])
    parameters = models.JSONField(blank=True, null=True)
    
    class Meta:
        unique_together = ('experiment', 'sensor')
        
    def __str__(self):
        return f"{self.sensor.get_unique_identifier()} ({self.role}) in {self.experiment.test_id}"
    
    















