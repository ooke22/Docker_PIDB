from django.db import migrations

def populate_unique_identifiers(apps, schema_editor):
    Sensor = apps.get_model('sensor_4_app', 'Sensor')
    for sensor in Sensor.objects.all():
        batch_id = str(sensor.batch_id).zfill(3)
        wafer_id = str(sensor.wafer_id).zfill(2)
        sensor_id = str(sensor.sensor_id).zfill(3)
        sensor.unique_identifier = f"{sensor.batch_location}{batch_id}-{wafer_id}-{sensor_id}"
        sensor.save()
        
class Migration(migrations.Migration):
    dependencies = [
        ('sensor_4_app', '0003_sensor_unique_identifier'),
    ]
    
    operations = [
        migrations.RunPython(populate_unique_identifiers)
    ]