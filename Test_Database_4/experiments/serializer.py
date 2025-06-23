from rest_framework import serializers
from .models import ExperimentTest, ExperimentSensorRelation
from sensor_4_app.models import Sensor

class ExperimentTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExperimentTest
        fields = '__all__'
        
class ExSenRelSerializer(serializers.ModelSerializer):
    sensor_identifier = serializers.CharField(source='sensor.get_unique_identifier', read_only=True)
    sensor = serializers.CharField(write_only=True) # Allow using 'unique_identider' for input
    
    class Meta:
        model = ExperimentSensorRelation
        fields = ['experiment', 'sensor', 'role', 'parameters', 'sensor_identifier']
        
    def validate_sensor(self, value):
        """
        Converts the unique_identifier into a Sensor object.
        """
        try:
            return Sensor.objects.get(batch_location=value[:4], batch_id=int(value[4:7]),
                                      wafer_id=int(value[8:10]), sensor_id=int(value[11:]))
        except Sensor.DoesNotExist:
            raise serializers.ValidationError(f"Sensor with id: '{value}' does not exist.")
        
    def create(self, validated_data):
        sensor = validated_data.pop('sensor')
        experiment_sensor_relation = ExperimentSensorRelation.objects.create(sensor=sensor, **validated_data)
        return experiment_sensor_relation
        
class ExperimentDetailSerializer(serializers.ModelSerializer):
    sensors = ExSenRelSerializer(source='experimentsensorrelation_set', many=True, read_only=True)
    
    class Meta:
        model = ExperimentTest
        fields = [
            'test_id',
            'test_date',
            'sensors'
        ]