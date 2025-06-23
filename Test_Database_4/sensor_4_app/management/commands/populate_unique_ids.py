from django.core.management.base import BaseCommand
from sensor_4_app.models import Sensor

class Command(BaseCommand):
    help = 'Populates unique_identifier for all existing sensors'

    def handle(self, *args, **kwargs):
        updated = 0
        for sensor in Sensor.objects.all():
            batch_id = str(sensor.batch_id).zfill(3)
            wafer_id = str(sensor.wafer_id).zfill(2)
            sensor_id = str(sensor.sensor_id).zfill(3)

            sensor.unique_identifier = f"{sensor.batch_location}{batch_id}-{wafer_id}-{sensor_id}"
            sensor.save()
            updated += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully updated {updated} sensors.'))
