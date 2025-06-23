from djongo import models
from rest_framework.decorators import api_view
from rest_framework.response import Response 
from rest_framework import status

class Electrode(models.Model):
    #Batch Field
    batch_location = models.CharField(max_length=5, blank=False, db_index=True) # Indexed
    batch_id = models.IntegerField(blank=False, db_index=True) # Indexed
    total_wafers = models.IntegerField()
    batch_label = models.CharField(max_length=225, blank=True, null=True)
    batch_description = models.CharField(max_length=1000, blank=True, null=True)
    # Wafer fields
    wafer_id = models.IntegerField(db_index=True) # Indexed
    wafer_label = models.CharField(max_length=225, blank=True, null=True)
    total_sensors = models.IntegerField()
    wafer_description = models.CharField(max_length=1000, blank=True, null=True)
    wafer_design_id = models.CharField(max_length=50, blank=True, null=True)
    wafer_process_id = models.CharField(max_length=50, blank=True, null=True)
    wafer_build_time = models.CharField(max_length=200, blank=True, null=True)

    # Sensor fields
    sensor_id = models.IntegerField(db_index=True) # Indexed
    sensor_label = models.CharField(max_length=225, blank=True, null=True)
    sensor_description = models.CharField(max_length=1000, blank=True, null=True)
    
    def get_unique_identifier(self):
        # batch_id with zero padding
        batch_id_padded = str(self.batch_id).zfill(3)
        # wafer_id with zero padding
        wafer_id_padded = str(self.wafer_id).zfill(2)
        # sensor_id with zero padding
        sensor_id_padded = str(self.sensor_id).zfill(3)
        return f"{self.batch_location}{batch_id_padded}-{wafer_id_padded}-{sensor_id_padded}"
    
    # Adding the DjongoManager. A custom manager provided by Djongo which helps Django understand how to interact with MongoDB by translating Django ORM calls to MongoDB-native operations.
    objects = models.DjongoManager()
class Image(models.Model):
    electrode = models.ForeignKey(Electrode, related_name='images', on_delete=models.CASCADE)
    process_id = models.CharField(max_length=10, blank=True, null=True)
    image = models.ImageField(upload_to='electrode-images/')
    
    
    
# Initial Update logic:
@api_view(['PUT'])
def electrodeupdate(request, batch_location, batch_id):
    if request.method == 'PUT':
        data = request.data
        print("Recieved Data:", data)
        print("wafer_ids:", str(request.data.get('wafer_ids', '')))
        print("sensor_ids:", str(request.data.get('sensor_ids', '')))
        
    try:
        wafer_ids = parse_range(str(request.data.get('wafer_ids', '')))
        sensor_ids = parse_range(str(request.data.get('sensor_ids', '')))
        
        update_data = request.data.get('update_data', {})
        electrodes = Electrode.objects.filter(batch_location=batch_location, batch_id=batch_id)
        for wafer_id in wafer_ids or get_all_wafer_ids():
            for sensor_id in sensor_ids or get_all_sensor_ids():
                
                    try:
                        electrode_queryset = electrodes.filter(wafer_id=wafer_id, sensor_id=sensor_id)
                        for electrode in electrode_queryset:
                             #update variables based on the provided data:
                            for variable, value in update_data.items():
                                setattr(electrode, variable, value)
                            electrode.save()
                    except Electrode.DoesNotExist:
                        pass
        return Response({'message': 'Update Success'})
    except Exception as e:
        # Log the error to the terminal
        print(f"Error in electrodeupdate: {e}")
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
def parse_range(range_str):
    if range_str:
        result = []
        for ids in range_str.split(','):
            if '-' in ids:
                start, end = map(int, ids.split('-'))
                result.extend(range(start, end + 1))
            else:
                result.append(int(ids))
        return result
    return []

def get_all_wafer_ids():
    """Returns a list of all wafer IDs in the database."""
    return list(Electrode.objects.values_list('wafer_id', flat=True).distinct())

def get_all_sensor_ids():
    return list(Electrode.objects.values_list('sensor_id', flat=True).distinct())
