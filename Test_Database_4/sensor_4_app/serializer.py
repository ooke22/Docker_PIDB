from rest_framework import serializers
from .models import Sensor, Image, SensorProcessRelation, SensorLabel

class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = ['process_id', 'image']

class SensorProcessRelationSerializer(serializers.ModelSerializer):
    process_id = serializers.CharField(source='process_file.process_id', read_only=True)
    description = serializers.CharField(source='process_file.description', read_only=True)
    timestamp = serializers.DateTimeField()

    class Meta:
        model = SensorProcessRelation
        fields = ['process_id', 'description', 'timestamp']


class BatchSerializer(serializers.ModelSerializer):
    images = ImageSerializer(many=True, read_only=True)
    sensor_processes = SensorProcessRelationSerializer(source='process_relations', many=True, read_only=True)
    
    class Meta:
        model = Sensor
        fields = [
            'batch_location',
            'batch_id',
            'batch_label',
            'batch_description',
            'total_wafers',
            'wafer_id',
            'wafer_label',
            'wafer_description',
            'wafer_design_id',
            #'wafer_process_id',
            #'wafer_build_time',
            'sensor_processes',  # Updated to show each process_id and timestamp
            'sensor_id',
            'total_sensors',
            'sensor_label',
            'sensor_description',
            'images'
        ]
        
class SensorsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sensor
        fields = '__all__'
        
class DetailSerializer(serializers.ModelSerializer):
    #images = ImageSerializer(many=True, read_only=True)
    sensor_processes = SensorProcessRelationSerializer(source='process_relations', many=True, read_only=True)
    
    class Meta:
        model = Sensor
        fields = [
            'batch_location',
            'batch_id',
            'batch_label',
            'batch_description',
            'total_wafers',
            'sensor_processes',  
            'total_sensors',
            #'images'
        ]
        
        
class SearchFuncSerializer(serializers.ModelSerializer):
    images = ImageSerializer(many=True, read_only=True)
    #wafer_processes = ProcessFileSerializer(many=True, read_only=True)
    unique_identifier = serializers.SerializerMethodField()
    sensor_processes = SensorProcessRelationSerializer(source='process_relations', many=True, read_only=True)
    
    class Meta:
        model = Sensor
        fields = ['unique_identifier','batch_location','batch_id','batch_label','batch_description',
                  'wafer_id','wafer_label','wafer_description','wafer_design_id','sensor_id','sensor_label',
                  'sensor_description', 'label', 'images', 'sensor_processes'] # Include related images
    
    def get_unique_identifier(self, obj):
        return obj.get_unique_identifier()
    
class TestSensorSerializer(serializers.ModelSerializer):
    unique_identifier = serializers.SerializerMethodField()
    
    class Meta:
        model = Sensor
        fields = ['unique_identifier']
        
    def get_unique_identifier(self, obj):
        return obj.get_unique_identifier()

# Refactored version of TestSensorSerializer - uses the incluced u_id field from the data model for faster lookups
class UIDSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sensor
        fields = ['unique_identifier']
    
    
class SensorSerializer(serializers.ModelSerializer):
    images = ImageSerializer(many=True, read_only=True)
    sensor_processes = SensorProcessRelationSerializer(source='process_relations', many=True, read_only=True)
    unique_identifier = serializers.SerializerMethodField()
    
    class Meta:
        model = Sensor
        fields = ['unique_identifier','total_wafers','total_sensors','batch_label','batch_description',
                  'wafer_label','wafer_description','wafer_design_id','sensor_label',
                  'sensor_description', 'sensor_processes', 'images']
        
    def get_unique_identifier(self, obj):
        return obj.get_unique_identifier()
        
        
class SensorFilterSerializer(serializers.Serializer):
    batch_location = serializers.CharField(required=False)
    batch_id = serializers.CharField(required=False)
    wafer_id = serializers.CharField(required=False)
    sensor_id = serializers.CharField(required=False)
    process_id = serializers.CharField(required=False)



# TODO: Experiment with this serializer format
class SensorImageSerializer(serializers.ModelSerializer):
    sensor = serializers.PrimaryKeyRelatedField(queryset=Sensor.objects.all())
    class Meta:
        model = Image
        fields = '__all__'
        
        
        
class SensorLabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorLabel
        fields = '__all__'
        
        
class SLSerializer(serializers.ModelSerializer):
    sensor_processes = SensorProcessRelationSerializer(source='process_relations', many=True, read_only=True)
    
    class Meta:
        model = Sensor
        fields = [
            'unique_identifier',
            'sensor_processes',  
        ]
    
    
    

