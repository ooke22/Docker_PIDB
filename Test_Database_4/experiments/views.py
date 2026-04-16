from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404

from .models import Experiment, ExperimentSensor, ExperimentResult
from .serializer import ExperimentListSerializer, ExperimentDetailSerializer, ExperimentCreateSerializer, ExperimentResultSerializer
from batch_encoder.models import Sensor

@api_view(['POST'])
#@permission_classes([IsAuthenticated])
def create_experiment(request):
    """
    POST /api/experiments/
    
    Create experiment with sensors and OPTIONAL results.
    If ANY sensor is missing, the ENTIRE experiment creation fails
    
    Payload:
    {
        "experiment_id": "CE-123",
        "title": "Long Term Drift Test - Batch M021",
        "description": "Testing sensor stability over 7 days at room temperature",
        "experiment_type": "Long Term Drift",
        "test_date": "2024-11-20T09:00:00Z",
        "user_data": {  // Optional - for any additional parameters
            "temperature": 25.0,
            "duration_hours": 168,
            "sampling_interval": 60
        },
        "sensors": [
            // Group 1 - Primary configuration
            {
                "unique_id": "M021-01-045",
                "electrode": "E1",
                "role": "WE",
                "group_id": 1,
                "group_label": "Primary setup"
                "notes": "Main working electrode"
            },
            {
                "unique_id": "B210-01-100",
                "electrode": "E2",
                "role": "RE",
                "group_id": 1,
                "group_label": "Primary setup",
                "notes": ""
            },
            // Group 2 - Secondary Configuration
            {
                "unique_id": "M060-05-030",
                "electrode": "BOTH",
                "role": "RE",
                "group_id": 2,
                "group_label": "Secondary setup,
                "notes": ""
            },
            {
                "unique_id": "M063-08-100",
                "electrode": "E2",
                "role": "WE",
                "group_id": 2,
                "group_label": "Secondary setup,
                "notes": ""
            }
        ],
        "notes": "Comparing different electrode...",
        
        OPTIONAL: Include results if available
        "results": {
            "drift_measurements": [...],
            "statistics": {....}
        },
        "results_summary": "Excellent...."
    }
    
    Response:
    {
        "message": "Experiment created successfully",
        "experiment": {...},
        "warnings": []  // If any sensors were not found
    }
    """
    # Deserialize and validate data
    serializer = ExperimentCreateSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        # validationn passed, create objects
        try:
            # Calls ExperimentCreateSerializer.create() which creates Experiment + ExperimentSensor records
            experiment = serializer.save()
            
            # Return detailed response 
            detail_serializer = ExperimentDetailSerializer(experiment)
            
            return Response({'message': 'Experiment created successfully', 'experiment': detail_serializer.data}, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            return Response({'error': 'Failed to create experiment', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    # Validation failed, return errors    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_experiments(request):
    """
    GET /api/experiments/
    
    List all experiments with optional filtering.
    
    Query Parameters:
    - status: Filter by status (PLANNED, IN_PROGRESS, COMPLETED, CANCELLED)
    - experiment_type: Filter by experiment type
    - search: Search in title/description
    - created_by: Filter by creator user ID
    - date_from: Filter experiments after this date (test_date)
    - date_to: Filter experiments before this date (test_date)
    - page: Page number (deefault: 1)
    - page_size: Items per page (default: 20)
    - has_results: true/false
    
    Example: /api/experiments/?status=COMPLETED&experiment_type=Long%20Term%20Drift
    """
    
    experiments = Experiment.objects.all()
    
    # Apply filters
    if status_filter := request.query_params.get('status'):
        experiments = experiments.filter(status=status_filter.upper())
    
    if exp_type := request.query_params.get('experiment_type'):
        experiments = experiments.filter(experiment_type__icontains=exp_type)
    
    if search := request.query_params.get('search'):
        experiments = experiments.filter(
            Q(title__icontains=search) | 
            Q(description__icontains=search) |
            Q(experiment_id__icontains=search)
        )
    
    if created_by := request.query_params.get('created_by'):
        experiments = experiments.filter(created_by_id=created_by)
    
    if date_from := request.query_params.get('date_from'):
        experiments = experiments.filter(test_date__gte=date_from)
    
    if date_to := request.query_params.get('date_to'):
        experiments = experiments.filter(test_date__lte=date_to)
        
    if has_results := request.query_params.get('has_results'):
        if has_results.lower() == "true":
            experiments = experiments.filter(result__isnull=False)
        elif has_results.lower() == 'false':
            experiments = experiments.filter(result__isnull=True)
    
    # Optimize query
    experiments = experiments.select_related('created_by').prefetch_related('experiment_sensors__sensor')
    
    # Pagination
    page_size = int(request.query_params.get('page_size', 20))
    page = int(request.query_params.get('page', 1))
    start = (page - 1) * page_size
    end = start + page_size
    
    total_count = experiments.count()
    experiments_page = experiments[start:end]
    
    serializer = ExperimentListSerializer(experiments_page, many=True)
    
    return Response({
        'count': total_count,
        'page': page,
        'page_size': page_size,
        'total_pages': (total_count + page_size - 1) // page_size,
        'experiments': serializer.data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_experiment(request, experiment_id):
    """
    GET /api/experiments/{experiment_id}/
    
    Get detailed information about a specific experiment.
    Includes all sensors and their roles, plus results if available.
    
    Example Response: 
    {
        "experiment_id": "EXP-2025-001",
        "title": "Dual Electrode Test",
        "sensor_count": 2,
        "electrode_count": 3,
        "electrode_assignments": [
            {"sensor_unique_id": "M007-12-120", "electrode": "E1", "role": "RE", ...},
            {"sensor_unique_id": "M007-12-120", "electrode": "E2", "role": "WE", ...},
            {"sensor_unique_id": "M060-05-030", "electrode": "BOTH", "role": "CE", ...}
        ],
        "sensors_grouped": [
            {
                "sensor_id": "M007-12-120",
                "sensor_info": {...},
                "assignments": [
                    {"electrode": "E1", "role": "RE", ...},
                    {"electrode": "E2", "role": "WE", ...}
                ]
            },
            {
                "sensor_id": "M060-05-030",
                "sensor_info": {...},
                "assignments": [
                    {"electrode": "BOTH", "role": "CE", ...}
                ]
            }
        ],
        "result": {
            "results_data": {...},
            "summary": "...",
            "uploaded_date": "..."
        }
    }
    """
    
    experiment = get_object_or_404(Experiment.objects.select_related('created_by', 'result').prefetch_related('experiment_sensors__sensors'), experiment_id=experiment_id)
    serializer = ExperimentDetailSerializer(experiment)
    
    return Response(serializer.data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_experiment(request, experiment_id):
    """
    PATCH /api/experiments/{experiment_id}/
    
    Update experiment fields. Can update status, dates, notes, etc.
    Cannot change experiment_id or modify sensors or results (use separate endpoints).
    
    Payload (all fields optional):
    {
        "title": "Updated title",
        "description": "Updated description",
        "status": "IN_PROGRESS",
        "test_date": "2024-11-20T09:00:00Z",
        "completed_date": "2024-11-27T17:00:00Z",
        "user_data": {...},
        "notes": "Additional notes"
    }
    """
    
    experiment = get_object_or_404(Experiment, experiment_id=experiment_id)
    
    # Update allowed fields
    updatable_fields = [
        'title', 'description', 'experiment_type', 'status',
        'test_date', 'completed_date', 'user_data', 'notes'
    ]
    
    updated_fields = []
    for field in updatable_fields:
        if field in request.data:
            setattr(experiment, field, request.data[field])
            updated_fields.append(field)
    
    if updated_fields:
        experiment.save(update_fields=updated_fields)
    
    serializer = ExperimentDetailSerializer(experiment)
    return Response({
        'message': 'Experiment updated successfully',
        'updated_fields': updated_fields,
        'experiment': serializer.data
    })
    
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_experiment(request, experiment_id):
    """
    DELETE /api/experiments/{experiment_id}/delete/
    
    Delete an experiment and all related records.
    """
    
    experiment = get_object_or_404(Experiment, experiment_id=experiment_id)
    exp_id = experiment.experiment_id
    experiment.delete()
    
    return Response({
        'message': f'Experiment {exp_id} deleted successfully'
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_results(request, experiment_id):
    """
    POST /api/experiments/{experiment_id}/results/
    
    Upload results for an experiment. Supports file uploads.
    
    Payload (multipart/form-data for file uploads):
    {
        "results_data": {  // Structured data parsed from CSV or entered manually
            "drift_measurements": [...],
            "calculated_metrics": {...}
        },
        "summary": "Text summary of findings",
        "file": <FILE>  // Optional CSV/Excel file
    }
    
    Or for file upload only:
    - Content-Type: multipart/form-data
    - file: <CSV file>
    """
    
    experiment = get_object_or_404(Experiment, experiment_id=experiment_id)
    
    try:
        # Get or create result object
        result, created = ExperimentResult.objects.get_or_create(
            experiment=experiment,
            defaults={'results_data': {}}
        )
        
        # Update results data if provided
        if 'results_data' in request.data:
            result.results_data = request.data['results_data']
        
        # Update summary if provided
        if 'summary' in request.data:
            result.summary = request.data['summary']
        
        # Handle file upload
        if 'file' in request.FILES:
            result.raw_data_file = request.FILES['file']
        
        result.save()
        
        # Update experiment status
        if experiment.status != 'COMPLETED':
            experiment.status = 'COMPLETED'
            experiment.save(update_fields=['status'])
            
        serializer = ExperimentResultSerializer(result)
        
        return Response({
            'message': 'Results uploaded successfully',
            'created': created,
            'result': serializer.data,
            'file_uploaded': 'file' in request.FILES
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
    
    except Exception as e:
        return Response({
            'error': 'Failed to upload results',
            'detail': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_experiment_results(request, experiment_id):
    """
    GET /api/experiments/{experiment_id}/results/
    
    Retrieve results for a specific experiment.
    """
    
    experiment = get_object_or_404(Experiment, experiment_id=experiment_id)
    
    try:
        result = ExperimentResult.objects.get(experiment=experiment)
        serializer = ExperimentResultSerializer(result)
        return Response(serializer.data)
    except ExperimentResult.DoesNotExist:
        return Response({
            'message': 'No results available for this experiment'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
def validate_sensors(request):
    """
    GET /api/experiments/validate-sensors/?sensor_ids=M021-01-045,B210-01-100
    
    Validate that sensor IDs exist in the database before creating an experiment.
    Useful for form validation in the frontend.
    
    Returns:
    {
        "valid": true/false,
        "sensors": [
            {
                "unique_id": "M021-01-045",
                "exists": true,
                "batch_location": "M021",
                "sensor_label": "..."
            }
        ],
        "missing": ["B210-01-999"]  // If any sensors not found
    }
    """
    
    sensor_ids_param = request.query_params.get('sensor_ids', '')
    sensor_ids = [s.strip() for s in sensor_ids_param.split(',') if s.strip()]
    
    if not sensor_ids:
        return Response({
            'error': 'sensor_ids parameter is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Query sensors
    sensors = Sensor.objects.filter(unique_identifier__in=sensor_ids)
    sensor_map = {s.unique_identifier: s for s in sensors}
    
    # Build response
    sensor_info = []
    for sensor_id in sensor_ids:
        if sensor_id in sensor_map:
            sensor = sensor_map[sensor_id]
            sensor_info.append({
                'unique_id': sensor_id,
                'exists': True,
                'batch_location': sensor.batch_location,
                #'batch_id': sensor.batch_id,
                #'wafer_id': sensor.wafer_id,
                #'sensor_id': sensor.sensor_id,
                #'sensor_label': sensor.sensor_label,
                'process_count': sensor.process_count,
                #'processes': sensor.process_ids
            })
        else:
            sensor_info.append({
                'unique_id': sensor_id,
                'exists': False
            })
    
    missing = [s for s in sensor_ids if s not in sensor_map]
    
    return Response({
        'valid': len(missing) == 0,
        'sensors': sensor_info,
        'missing': missing
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def experiment_statistics(request):
    """
    GET /api/experiments/statistics/
    
    Get overview statistics about experiments.
    Useful for dashboards and reporting.
    """
    
    total = Experiment.objects.count()
    by_status = Experiment.objects.values('status').annotate(count=Count('id'))
    by_type = Experiment.objects.values('experiment_type').annotate(count=Count('id'))
    
    recent = Experiment.objects.order_by('-created_date')[:5].values(
        'experiment_id', 'title', 'status', 'created_date'
    )
    
    return Response({
        'total_experiments': total,
        'by_status': list(by_status),
        'by_type': list(by_type),
        'recent_experiments': list(recent),
        'total_sensors_tested': ExperimentSensor.objects.values('sensor_unique_id').distinct().count()
    })