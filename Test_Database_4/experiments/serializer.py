from rest_framework import serializers
from .models import Experiment, ExperimentSensor, ExperimentResult, format_electrode_assignments, format_sensor_groups
from batch_encoder.models import Sensor
        
class ExperimentSensorSerializer(serializers.ModelSerializer):
    """Nested serializer for sensors in an experiment"""
    
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    electrode_display = serializers.CharField(source='get_electrode_display', read_only=True)
    sensor_info = serializers.SerializerMethodField()
    
    class Meta:
        model = ExperimentSensor
        fields = ['id', 'electrode', 'electrode_display', 'role', 'role_display', 'sensor_unique_id', 'sensor_batch_location', 
                  'group_id', 'group_label', 'notes', 'sensor_info']
    
    def get_sensor_info(self, obj):
        """Automatically includes full sensor details"""
        # obj.sensor is already loaded because of prefetch_related
        sensor = obj.sensor
        # No additional query needed!
        return {
            'unique_id': sensor.get_unique_identifier(),
            'batch_location': sensor.batch_location,
            'batch_id': sensor.batch_id,
            'wafer_id': sensor.wafer_id,
            'sensor_id': sensor.sensor_id,
            'label': sensor.sensor_label,
            'process_count': sensor.process_count
        }
        
class ExperimentResultSerializer(serializers.ModelSerializer):
    """Serializer for experiment results"""
    class Meta:
        model = ExperimentResult
        fields = ['id', 'results_data', 'raw_data_file', 'summary', 'uploaded_date']
        read_only_fields = ['uploaded_date']

class ExperimentListSerializer(serializers.ModelSerializer):
    """Basic serializer for experiment listings"""
    
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    has_results = serializers.SerializerMethodField()
    
    class Meta:
        model = Experiment
        fields = [
            'id',
            'experiment_id',
            'title',
            'description',
            'experiment_type',
            'test_date',
            'sensor_count',
            'electrode_count',
            'has_results',
            'notes'
        ]
    
    def get_has_results(self, obj):
        """Check if experiment has results"""
        return hasattr(obj, 'result')

class ExperimentDetailSerializer(serializers.ModelSerializer):
    """Complete experiment with all sensors, electrodes, and results"""
    
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    # This automatically fetches all ExperimentSensor records
    electrode_assignments = ExperimentSensorSerializer(
        source='experiment_sensors',  # Related name from ForeignKey
        many=True,
        read_only=True
    )
    
    groups = serializers.SerializerMethodField()
    group_count = serializers.SerializerMethodField()
    
    # Grouped by sensor
    #sensors_grouped = serializers.SerializerMethodField()
    
    results = ExperimentResultSerializer(source='result', read_only=True)
    
    class Meta:
        model = Experiment
        fields = [
            'id',
            'experiment_id',
            'title',
            'description',
            'experiment_type',
            'test_date',
            'created_by_name',
            'user_data',
            'sensor_count',
            'electrode_count',
            'electrode_assignments',
            #'sensors_grouped',  # All sensors included here!
            'group_count',
            'groups',
            'result',
            'notes'
        ]
    
    def get_sensors_grouped(self, obj):
        """Group electrode assignments by sensor"""
        return format_electrode_assignments(obj)
    
    def get_groups(self, obj):
        """Group sensors by group_ids"""
        return format_sensor_groups(obj)
    
    def get_group_count(self, obj):
        """Count distinct groups"""
        return obj.experiment_sensors.values('group_id').disitinct().count()
    
class ExperimentCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating experiments with sensors and optional results.
    Handles validation and nested creation
    """
    # Experiment fields
    experiment_id = serializers.CharField(max_length=50)
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    experiment_type = serializers.CharField(max_length=50, required=False, allow_blank=True)
    test_date = serializers.DateTimeField(required=False, allow_null=True)
    user_data = serializers.JSONField(required=False, default=dict)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    # Sensor assignments 
    sensors = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        help_text="List of sensor assignments with electrode, role, and group id"
    )

    # Results can also be uploaded at creation time
    results = serializers.DictField(required=False, allow_null=True)
    results_summary = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = Experiment
        fields = [
            'experiment_id',
            'title', 
            'description',
            'experiment_type',
            'test_date',
            'user_data',
            'notes',
            'sensors',
            'results',
            'results_summary'
        ]
    
    def validate_experiment_id(self, value):
        """Check if experiment_id already exists"""
        if Experiment.objects.filter(experiment_id=value).exists():
            raise serializers.ValidationError(
                f"Experiments with ID '{value}' already exists"
            )
        return value
    
    def validate_sensors(self, value):
        """
        Validate sensor assignments and grouping
        Expected format: 
        [
            {
                "unique_id": "M021-02-003",
                "electrode": "E1",
                "role": "WE",
                "group_id": 1,
                "group_label": "Primary",
                "notes": ""
            },
            ...
        ]
        """
        if not value:
            raise serializers.ValidationError("At least one sensor must be specified")
        
        # Extract sensor IDs
        sensor_ids = []
        seen_combinations = set()
        group_ids = set()
        group_labels = {} # Labels per group
        
        for idx, sensor_data in enumerate(value):
            # Validate required fields
            if 'unique_id' not in sensor_data:
                raise serializers.ValidationError(f"Sensor at index {idx}: 'unique_id' is required")
            if 'role' not in sensor_data:
                raise serializers.ValidationError(f"Sensor at index {idx}: 'role' is required")
            
            sensor_id = sensor_data['unique_id']
            electrode = sensor_data.get('electrode', 'BOTH')
            role = sensor_data['role']
            group_id = sensor_data.get('group_id', 1) # Default to 1
            group_label = sensor_data.get('group_label', '')
            
            # Validate roles 
            valid_roles = ['WE', 'RE', 'CE']
            if role not in valid_roles:
                raise serializers.ValidationError(f"Invalid role '{role}'. Must be one of: {valid_roles}")
            
            # Validate electrode
            valid_electrodes = ['BOTH', 'E1', 'E2']
            if electrode not in valid_electrodes:
                raise serializers.ValidationError(f"Invalid electrode '{electrode}' for sensor {sensor_id}. Must be one of: {valid_electrodes}")
            
            # Validate group_id
            if not isinstance(group_id, int) or group_id < 1:
                raise serializers.ValidationError(f"group_id must be a positive integer, got: {group_id}")
            group_ids.add(group_id)
            
            # Track group labels (all sensors in the same group should have the same label)
            if group_label:
                if group_id in group_labels:
                    if group_labels[group_id] != group_label:
                        raise serializers.ValidationError(
                            f"Group {group_id} has inconsistent labels: "
                            f"'{group_labels[group_id]}' vs {group_label}"
                        )
                else:
                    group_labels[group_id] = group_label
            
            # Check for duplicates
            combo = (sensor_id, electrode)
            if combo in seen_combinations:
                raise serializers.ValidationError(f"Duplicate assignment: {sensor_id} with electrode {electrode}")
            
            seen_combinations.add(combo)
            sensor_ids.append(sensor_id)
            
            # Validate group_ids are sequential
            if group_ids:
                max_group = max(group_ids)
                min_group = min(group_ids)
                
                # Check they start at 1
                if min_group != 1:
                    raise serializers.ValidationError(f"Group ids must start at 1, found minimum: {min_group}")
                
                # Check no gaps (1, 2, 3... not 1, 3, 5)
                expected_groups = set(range(1, max_group + 1))
                if group_ids != expected_groups:
                    missing = expected_groups - group_ids
                    raise serializers.ValidationError(f"Group ids must be sequential with no gaps. Missing : {sorted(missing)}")
            
            # Check if all sensors exist
            existing_sensors = Sensor.objects.filter(
                unique_identifier__in=sensor_ids
            ).values_list('unique_identifier', flat=True)
            
            missing = set(sensor_ids) - set(existing_sensors)
            if missing:
                raise serializers.ValidationError({
                    'missing sensors': list(missing),
                    'message': 'These sensors were not found in the database'
                })
                
            return value

    def create(self, validated_data):
        """Create experiment with grouped sensors and optional results"""
        from django.db import transaction
        
        # Extract nested data
        sensors_data = validated_data.pop('sensors')
        results_data = validated_data.pop('results', None)
        results_summary = validated_data.pop('results_summary', None)
        
        # Get current user from context
        user = self.context['request'].user
        
        with transaction.atomic():
            # Create experiment object
            experiment = Experiment.objects.create(created_by=user, **validated_data)
            
            # Fetch all sensors
            sensor_ids = [s['unique_id'] for s in sensors_data]
            sensor_objs = Sensor.objects.filter(unique_identifier__in=sensor_ids)
            sensor_map = {s.unique_identifier: s for s in sensor_objs}
            
            # Track group labels
            group_labels = {}
            for sensor_data in sensors_data:
                group_id =sensor_data.get('group_id', 1)
                group_label = sensor_data.get('group_label', '')
                if group_label and group_id not in group_labels:
                    group_labels[group_id] = group_label
            
            # Create ExperimentSensor records
            experiment_sensors = []        
            for sensor_data in sensors_data:
                sensor_id = sensor_data['unique_id']
                sensor_obj = sensor_map[sensor_id]
                
                group_id = sensor_data.get('group_id', 1)
                # Consistent labelling for each group
                group_label = group_labels.get(group_id, sensor_data.get('group_label', ''))
                
                exp_sensor = ExperimentSensor(
                    experiment=experiment,
                    sensor=sensor_obj,
                    electrode=sensor_data.get('electrode', 'BOTH'),
                    role=sensor_data['role'],
                    group_id=group_id,
                    group_label=group_label,
                    notes=sensor_data.get('notes', '')
                )
                experiment_sensors.append(exp_sensor)
                
            # Bulk create
            ExperimentSensor.objects.bulk_create(experiment_sensors)
            
            # Update counts
            experiment.update_counts()
            
            # Create results if provided
            if results_data or results_summary:
                ExperimentResult.objects.create(
                    experiment=experiment,
                    results_data=results_data or {},
                    summary=results_summary or ''
                )
            
            return experiment