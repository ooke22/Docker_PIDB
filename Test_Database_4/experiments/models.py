from djongo import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from batch_encoder.models import Sensor

# ===========================================================================================
# Model 1: Experiment
# ===========================================================================================
# The main object that represents an experiment.

class Experiment(models.Model):
    """
    The main experiment record.
    EXAMPLE RECORD:
    {
        "experiment_id": "EXP-2024-001",
        "title": "Long Term Drift Test - Batch M021",
        "description": "Testing sensor stability over 7 days",
        "experiment_type": "Long Term Drift",
        "test_date": "2024-11-01",
        "created_by": "Okenwa",
        "sensor_ids: ["M021-03-002"] 
        "sensor_count": 2,
        "user_data": {
            "parameter 1": 25.0,
            "parameter 2 duration_hours": 168,
            "sampling_interval": 60
        },
        "notes": "Using new coating batch C-045"
    }
    
    PURPOSE: Store the "what, when, who, and why" of the experiment
    NOT stored here: Which sensors were used (that's in ExperimentSensor)
    NOT stored here: The actual results (that's in ExperimentResult)
    """
    # Primary Identification
    experiment_id = models.CharField(max_length=50, unique=True, db_index=True, help_text="Unique identifier (e.g., EXP-2024-001)")
    
    # Basic Information
    title = models.CharField(max_length=200, help_text="Short descriptive title of the experiment")
    description = models.TextField(blank=True, null=True, help_text="Detailed description of experiment purpose and methodology")
    
    # Timeline
    test_date = models.DateTimeField(null=True, blank=True, db_index=True, help_text="Date when the experiment was actually performed")
    
    # Ownership
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='experiments', help_text="User who created this experiment record")
    
    # Experiment Type - Helps with filtering and categorization
    experiment_type = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        db_index=True,
        help_text="Type of test (e.g., 'Long Term Drift', 'Short Term Drift', 'Thickness Measurement')"
    )
    
    # Flexible data storage for experiment parameters (CSV Data or additional metadata)
    user_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Flexible storage for experiment parameters, conditions, and measurements"
    )
    
    # Quick metadata for filtering/sorting
    sensor_count = models.IntegerField(default=0, help_text="Number of sensors used in this experiment")
    
    electrode_count = models.IntegerField(default=0, help_text="Total number of electrode assignments")
    
    # Notes field for any additional observations
    notes = models.TextField(blank=True, null=True, help_text="Additional notes or observations from the engineer")
    
    def get_sensors(self):
        """Get all sensors associated with this experiment"""
        return Sensor.objects.filter(experiment_membership__experiment=self).distinct()

    def get_sensors_by_role(self, role):
        """Get sensors with a specific role"""
        return Sensor.objects.filter(
            experiment_memberships__experiment=self,
            experiment_memberships__role=role
        ) #TODO: Where is memberships defined
    
    def validate_sensors_exist(self, sensor_ids):
        """
        Validate that all sensor IDs exist in the database.
        Returns list of missing sensor IDs.
        """
        existing_sensors = Sensor.objects.filter(
            unique_identifier__in=sensor_ids
        ).values_list('unique_identifier', flat=True)
        
        missing = set(sensor_ids) - set(existing_sensors)
        return list(missing)
     
    def update_counts(self):
        """Update sensor and electrode counts"""
        # Count unique sensors
        unique_sensors = self.experiment_sensors.values('sensor').distinct().count()
        self.sensor_count = unique_sensors
        
        # Count total electrode assignments
        self.electrode_count = self.experiment_sensors.count()
        
        Experiment.objects.filter(pk=self.pf).update(
            sensor_count=unique_sensors,
            electrode_count=self.electrode_count
        )
    
    def __str__(self):
        return f"{self.experiment_id} - {self.title}"
    
    class Meta:
        db_table = 'experiment'
        ordering = ['-test_date']
        indexes = [
            models.Index(fields=['experiment_id']),
            models.Index(fields=['test_date']),
            models.Index(fields=['experiment_type']),
            models.Index(fields=['created_by', 'test_date']),
        ]
        
    objects = models.DjongoManager()

# ===========================================================================================
# Model 2: ExperimentSensor
# ===========================================================================================
# This connect Experiments to Sensors (many-to-many relationship)
# One experiment can have multiple sensor, one sensor can be in multiple experiments

class ExperimentSensor(models.Model):
    """
    links sensors to experiments with their roles.
    Keeps the many-to-many relationship clean and queryable.
    
    EXAMPLE RECORDS for experiment EXP-2024-001:
    
    Record 1:
    {
        "experiment": EXP-2024-001,
        "sensor": M021-01-045,
        "electrode": E1,
        "role": "WE",
        "sensor_unique_id": "M021-01-045",  // Cached for speed
        "sensor_batch_location": "M021",     // Cached for speed
        "notes": "Primary test sensor"
    }
    
    Record 2:
    {
        "experiment": EXP-2024-001,
        "sensor": B210-01-100,
        "electrode": E2
        "role": "RE",
        "sensor_unique_id": "B210-01-100",
        "sensor_batch_location": "B210",
        "notes": "Reference electrode"
    }
    
    Record 3:
    {
        "experiment": EXP-2024-001,
        "sensor": M056-05-130,
        "electrode": Both
        "role": "CE",
        "sensor_unique_id": "M056-05-130",
        "sensor_batch_location": "M056",
        "notes": "Counter electrode"
    }
    
    PURPOSE: Answer questions like:
    - Which sensors were used in experiment X?
    - What role did sensor Y play in experiment X?
    - Which experiments has sensor Z been used in?
    
    WHY SEPARATE TABLE: Because the relationship is many-to-many with additional data (role, notes)
    """
    # The Connections
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE, related_name='experiment_sensors')
    
    sensor = models.ForeignKey(
        Sensor,
        on_delete=models.PROTECT,  # Don't allow deletion of sensors used in experiments
        related_name='experiment_memberships'
    )
    
    # Electrode configuration
    ELECTRODE_CHOICES = [
        ('BOTH', 'Both Electrodes (Same Role)'),
        ('E1', 'Electrode 1'),
        ('E2', 'Electrode 2'),
    ]
    
    electrode = models.CharField(
        max_length=10,
        choices=ELECTRODE_CHOICES,
        default='BOTH',
        help_text="Which electrode(s) are used"
    )
    
    # Role of this sensor in the experiment
    ROLE_CHOICES = [
        ('WE', 'Working Electrode'),
        ('RE', 'Reference Electrode'),
        ('CE', 'Counter Electrode')
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, help_text="Role this sensor plays in the experiment")
    
    # Denormalized fields for faster querie
    sensor_unique_id = models.CharField(max_length=20, db_index=True, help_text="Cached sensor unique identifier")
    #TODO: Add signals that updates the sensor u_id if changed
    sensor_batch_location = models.CharField(max_length=5, db_index=True, help_text="Cached batch location")
    
    # Optional: sensor-specific notes for this experiment
    notes = models.TextField(blank=True, null=True, help_text="Specific notes about this sensor's use in this experiment")
    
    group_id = models.IntegerField(default=1, db_index=True, help_text="grouping within the experiment")
    
    group_label = models.CharField(max_length=50, blank=True, null=True, help_text="Optional descriptive label for this group")
    
    def clean(self):
        """Validate electrode configuration"""
        super().clean()
        
        if self.pk: 
            return
        
        existing = ExperimentSensor.objects.filter(
            experiment=self.experiment,
            sensor=self.sensor
        ).exclude(pk=self.pk)
        
        if existing.exists():
            # Check for conflicts
            existing_electrodes = set(existing.values_list('electrode', flat=True))
            
            # Can't use "BOTH" if E1 and E2 are already assigned
            if self.electrode == 'BOTH' and ('E1' in existing_electrodes or 'E2' in existing_electrodes):
                raise ValidationError(
                    "Cannot assign 'Both' electrodes when individual electrodes (E1/E2) are already assigned for this sensor."
                )
                
            # Can't use E1 or E2 if "BOTH" already assigned
            if self.electrode in ('E1', 'E2') and 'BOTH' in existing_electrodes:
                raise ValidationError(
                    f"Cannot assign {self.electrode} when 'Both' electrodes are already assigned for this sensor." 
                )   
                 
    def save(self, *args, **kwargs):
        # Auto-populate denormalized fields
        if self.sensor:
            self.sensor_unique_id = self.sensor.get_unique_identifier()
            self.sensor_batch_location = self.sensor.batch_location
            
        # Validate before saving
        self.clean()
        
        super().save(*args, **kwargs)
        
        # Update experiments counts
        if self.experiment_id:
            self.experiment.update_counts()
            
    def delete(self, *args, **kwargs):
        """Update counts after deletion"""
        experiment = self.experiment
        super().delete(*args, **kwargs)
        experiment.update_counts()
    
    def __str__(self):
        if self.electrode == 'BOTH':
            return f"{self.sensor_unique_id} ({self.get_role_display()}) in {self.experiment.experiment_id}"
        else:
            return f"{self.sensor_unique_id} {self.get_electrode_display()} ({self.get_role_display()}) in {self.experiment.experiment_id}"
    
    class Meta:
        db_table = 'experiment_sensor'
        # Allows same sensor with different electrodes
        unique_together = ('experiment', 'sensor', 'electrode')  # Each sensor can only appear once per experiment
        ordering = ['group_id', 'sensor_unique_id']
        indexes = [
            models.Index(fields=['experiment', 'group_id']),
            models.Index(fields=['experiment', 'role']),
            models.Index(fields=['experiment', 'electrode']),
            models.Index(fields=['sensor_unique_id', 'electrode']),
            models.Index(fields=['sensor_batch_location']),
            models.Index(fields=['electrode', 'role']),
        ]
        
    objects = models.DjongoManager()

# ===========================================================================================
# Model 3: ExperimentResult 
# ===========================================================================================
# This stores the actual experiment results/data
# Separate from Experiment because results are added after the experiment runs/object is created
class ExperimentResult(models.Model):
    """
    Stores the results of an experiment.
    
    EXAMPLE RECORD:
    {
        "experiment": EXP-2024-001,
        "results_data": {
            "drift_measurements": [
                {"time": 0, "voltage": 1.23},
                {"time": 60, "voltage": 1.24},
                ...
            ],
            "statistics": {
                "mean_drift": 0.05,
                "max_drift": 0.12
            }
        },
        "raw_data_file": "experiment-results/2024/11/exp_001_data.csv",
        "summary": "Sensors showed excellent stability with <5% drift",
        "uploaded_date": "2024-11-08"
    }
    
    PURPOSE: Store the actual experimental data and findings
    
    WHY SEPARATE:
    1. Results are added AFTER experiment creation
    2. Can be very large (don't bloat Experiment queries)
    3. Can be updated/verified separately
    4. Keeps Experiment model clean and fast to query
    """
    # OneToOne: Each experiment has exactly 0 or 1 result object
    experiment = models.OneToOneField(
        Experiment,
        on_delete=models.CASCADE,
        related_name='result',
        help_text="Link to parent experiment"
    )
    
    # Result storage - the actual data
    results_data = models.JSONField(default=dict, help_text="Structured results data: parsed CSV, calculated metrics, etc.")
    
    # File attachments
    raw_data_file = models.FileField(upload_to='experiment-results/%Y/%m/', blank=True, null=True, help_text="Original CSV or data file uploaded by engineer")
    
    # Summary fields for quick access
    summary = models.TextField(blank=True, null=True, help_text="Text summary of key findings")
    
    # Timestamps
    uploaded_date = models.DateTimeField(auto_now_add=True, help_text="When results were first uploaded")
    updated_date = models.DateTimeField(auto_now=True,help_text="Last update to results")
    
    def __str__(self):
        return f"Results for {self.experiment.experiment_id}"
    
    class Meta:
        db_table = 'experiment_result'
        
    objects = models.DjongoManager()
    
    
# Helper function for views
def format_electrode_assignments(experiment):
    """
    Format electrode assignments grouped by sensor for API responses.
    
    Returns:
    [
        {
            'sensor_id': 'M032-10-032',
            'sensor_info': {...},
            'assignments': [
                {'electrode': 'E1', 'role': 'WE', 'notes': '...'},
                {'electrode': 'E2', 'role': 'RE', 'notes': '...'}
            ]
        },
        ...
    ]
    """
    from collections import defaultdict
    
    sensors_dict = defaultdict(lambda: {
        'sensor_id': None,
        'sensor_info': None,
        'assignments': []
    })
    
    for assignment in experiment.experiment_sensors.select_related('sensor').all():
        sensor_id = assignment.sensor_unique_id
        
        if sensors_dict[sensor_id]['sensor_id'] is None:
            sensors_dict[sensor_id]['sensor_id'] = sensor_id
            sensors_dict[sensor_id]['sensor_info'] = {
                'unique_id': sensor_id,
                'batch_location': assignment.sensor.batch_location,
                'batch_id': assignment.sensor.batch_id,
                'wafer_id': assignment.sensor.wafer_id,
                'sensor_id': assignment.sensor.sensor_id,
                'label': assignment.sensor.sensor_label
            }
        
        sensors_dict[sensor_id]['assignments'].append({
            'electrode': assignment.electrode,
            'electrode_display': assignment.get_electrode_display(),
            'role': assignment.role,
            'role_display': assignment.get_role_display(),
            'notes': assignment.notes
        })
    
    return list(sensors_dict.values())

def format_sensor_groups(experiment):
    """
    Group sensors by the group_id (configs).
    
    Returns: List of setups with their sensor assignments
    
    Expected output:
    [
        {
            'group_id': 1,
            'group_label': 'Primary Setup',
            'sensors': [
                {
                    'sensor_id': 'M021-02-003',
                    'electrode': 'E1',
                    'role': 'WE',
                },
                {
                    'sensor_id': 'M045-05-042',
                    'electrode': 'E2',
                    'role': 'RE',
                }
            ]
        },
        {
            'group_id': 2,
            'group_label': 'Secondary Setup',
            'sensors': [
                {
                    'sensor_id': 'M056-10-323',
                    'electrode': 'E1',
                    'role': 'RE',
                },
                {
                    'sensor_id': 'M065-07-022',
                    'electrode': 'E2',
                    'role': 'RE',
                }
            ]
        }
    ]
    """
    from collections import defaultdict
    
    groups = defaultdict(lambda: {
        'group_id': None,
        'group_label': '',
        'sensors': []
    })
    
    assignments = experiment.experiment_sensors.select_related('sensor').order_by(
        'group_id', 'sensor_unique_id'
    )
    
    for assignment in assignments:
        group_id = assignment.group_id
        
        if groups[group_id]['group_id'] is None:
            groups[group_id]['group_id'] = group_id
            groups[group_id]['group_label'] = assignment.group_label or ''
            
            groups[group_id]['sensors'].append({
                'sensor_id': assignment.sensor_unique_id,
                'electrode': assignment.electrode,
                'electrode_display': assignment.get_electrode_display(),
                'role': assignment.role,
                'role_display': assignment.get_role_display(),
                'notes': assignment.notes
            })
            
        return sorted(groups.values(), key=lambda x: x['group_id'])


