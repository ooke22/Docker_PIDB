from rest_framework import serializers
from .models import SensorLabel, Sensor
from batch_encoder.utils.parse_range_utils import parse_range

class ProcessInfoSerializer(serializers.Serializer):
    """Serializer to process information within batch summary"""
    process_id = serializers.CharField()
    description = serializers.CharField()
    timestamp = serializers.DateTimeField()
    
class BatchSummarySerializer(serializers.Serializer):
    """Serializer for batch summary response"""
    batch_location = serializers.CharField()
    batch_id = serializers.IntegerField()
    total_wafers = serializers.IntegerField()
    total_sensors = serializers.IntegerField()
    batch_label = serializers.CharField(allow_blank=True)
    batch_description = serializers.CharField(allow_blank=True)
    sensors_per_wafer = serializers.IntegerField()
    total_sensors_in_batch = serializers.IntegerField()
    processes = ProcessInfoSerializer(many=True)
    created_date_range = serializers.DictField(child=serializers.DateTimeField(), required=False)

    
class BatchDetailSerializer(serializers.Serializer):
    """Serializer for batch detail summary response"""
    batch_location = serializers.CharField()
    batch_id = serializers.IntegerField()
    batch_label = serializers.CharField(allow_blank=True)
    batch_description = serializers.CharField(allow_blank=True)
    total_wafers = serializers.IntegerField()
    total_sensors = serializers.IntegerField()
    sensor_processes = ProcessInfoSerializer(many=True)

class SensorLabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorLabel
        fields = '__all__'
        
class SLSerializer(serializers.ModelSerializer):
    sensor_processes = ProcessInfoSerializer(many=True, source='processes')
    
    class Meta:
        model = Sensor
        fields = [
            'unique_identifier',
            'sensor_processes'
        ]
        
class BatchSummaryLiteSerializer(serializers.Serializer):
    """Lightweight serializer for batch list - no process data"""
    batch_location = serializers.CharField()
    batch_id = serializers.IntegerField()
    total_wafers = serializers.IntegerField()
    total_sensors = serializers.IntegerField()
    batch_label = serializers.CharField(allow_blank=True)
    batch_description = serializers.CharField(allow_blank=True)
    sensors_per_wafer = serializers.IntegerField()
    total_sensors_in_batch = serializers.IntegerField()
    # NO processes field
        
class SensorFilterSerializer(serializers.Serializer):
    batch_location = serializers.CharField(required=False, max_length=5)
    batch_id = serializers.CharField(required=False)
    wafer_id = serializers.CharField(required=False)  # Changed to CharField
    sensor_id = serializers.CharField(required=False)
    process_id = serializers.CharField(required=False)
    unique_identifier = serializers.CharField(required=False)
    
    def validate_batch_id(self, value):
        """Parse batch_id as comma-separated or range"""
        if not value:
            return None
        
        batch_id_list = parse_range(value)
        if not batch_id_list:
            raise serializers.ValidationError(
                "Invalid batch_id format. Use comma-separated values or ranges (e.g., '1,3,5-7')"
            )
        return batch_id_list
    
    def validate_wafer_id(self, value):
        """Parse wafer_id as comma-separated or range"""
        if not value:
            return None
        
        # If it's already an integer, return it as is
        try:
            return int(value)
        except (ValueError, TypeError):
            pass
        
        # Try to parse as range
        wafer_id_list = parse_range(value)
        if not wafer_id_list:
            raise serializers.ValidationError(
                "Invalid wafer_id format. Use comma-separated values or ranges (e.g., '1,3,5-7')"
            )
        return wafer_id_list
    
    def validate_sensor_id(self, value):
        """Parse sensor_id as comma-separated or range"""
        if not value:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            pass
        
        sensor_id_list = parse_range(value)
        if not sensor_id_list:
            raise serializers.ValidationError(
                "Invalid sensor_id format. Use comma-separated values or ranges (e.g., '1,3,5-7,50-70,100)"
            )
        return sensor_id_list
    
class SensorSerializer(serializers.ModelSerializer):
    processes = ProcessInfoSerializer(many=True)
    
    class Meta:
        model = Sensor
        fields = ['unique_identifier','total_wafers','total_sensors','batch_label','batch_description',
                  'wafer_label','wafer_description','wafer_design_id','sensor_label',
                  'sensor_description', 'processes', 'images']