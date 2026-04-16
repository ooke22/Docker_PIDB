from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from .models import Sensor, SensorLabel, Image, ImageGroup
from process_encoder.models import ProcessFile
from .tasks import create_sensor_batch_task, unified_sensor_update_task, update_batch_task
from celery.result import AsyncResult
from django.conf import settings
from collections import defaultdict, Counter
from django.db.models import Q
from .serializer import BatchSummarySerializer, BatchDetailSerializer, SensorLabelSerializer, SLSerializer, BatchSummaryLiteSerializer, SensorFilterSerializer, SensorSerializer
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
import time, traceback, logging
import os, io
from .utils.datetime_utils import ensure_datetime
from django.core.files.base import ContentFile
from PIL import Image as PilImage
from celery import current_app
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.core.cache import cache

logger = logging.getLogger(__name__)

@api_view(['POST'])
def create_batch_api(request):
    """
    Trigger Celery task to create sensor batch asynchronously.
    Returns a task_id that frontend can poll for status/result.
    """
    try:
        required_fields = ['batch_location', 'batch_id', 'total_wafers', 'total_sensors', 'sensor_processes']
        for field in required_fields:
           if field not in request.data:
               return Response({'error': f'Missing required field: {field}'}, status=status.HTTP_400_BAD_REQUEST)

        batch_data = {
            'batch_location': request.data['batch_location'].strip().upper(),
            'batch_id': int(request.data['batch_id']),
            'total_wafers': int(request.data['total_wafers']),
            'total_sensors': int(request.data['total_sensors']),
            'batch_label': request.data.get('batch_label', '').strip(),
            'batch_description': request.data.get('batch_description', '').strip(),
            'wafer_label': request.data.get('wafer_label', '').strip(),
            'wafer_description': request.data.get('wafer_description', '').strip(),
            'wafer_design_id': request.data.get('wafer_designID', '').strip(),
            'sensor_description': request.data.get('sensor_description', '').strip(),
        }

        # Validate positive integers 
        if batch_data['batch_id'] <= 0 or batch_data['total_wafers'] <= 0 or batch_data['total_sensors'] <= 0:
            return Response({'error': 'batch_id, total_wafers, and total_sensors must be positive integers'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate and parse processes
        processes_data = request.data['sensor_processes']
        if not processes_data:
            return Response({'error': 'At least one process must be specified'}, status=status.HTTP_400_BAD_REQUEST)

        sensor_processes = []
        process_ids_set = set()

        for i, process_data in enumerate(processes_data):
            process_id = process_data.get('process_id', '').strip()
            description = process_data.get('description', '')
            timestamp = process_data.get('timestamp', '')

            if not process_id or not description or not timestamp:
                return Response({'error': f'Process {i+1} missing process_id, description, or timestamp'}, status=status.HTTP_400_BAD_REQUEST)
            if process_id in process_ids_set:
                return Response({'error': f'Duplicate process_id: {process_id}'}, status=status.HTTP_400_BAD_REQUEST)
            process_ids_set.add(process_id)

            # Validate process exists
            if not ProcessFile.objects.filter(process_id__in=process_ids_set):
                return Response({'error': f'Process {process_id} does not exist'}, status=status.HTTP_400_BAD_REQUEST)

            sensor_processes.append({
                'process_id': process_id,
                'description': description,
                'timestamp': timestamp
            })

        # Prevent duplicate batch creation
        if Sensor.objects.filter(batch_location=batch_data['batch_location'], batch_id=batch_data['batch_id']).exists():
            return Response({'error': f'Batch {batch_data["batch_location"]}{batch_data["batch_id"]:03d} already exists'}, status=status.HTTP_409_CONFLICT)

        # Trigger Celery Task
        task = create_sensor_batch_task.delay(batch_data, sensor_processes)
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "global_tasks", 
            {
                "type": "task_update", 
                "data": {
                "task_id": str(task.id),
                "progress": 0,
                "state": "STARTED",
                "message": f"Creating Batch {batch_data['batch_location']}{batch_data['batch_id']}!" 
                }
            }
        )
        
        return Response({"task_id": task.id, "message": "Batch creation started"}, status=status.HTTP_202_ACCEPTED)
    except Exception as e:
        return Response({'error': f'Unexpected error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['GET'])
def check_batch_status(request, task_id):
    """
    Check Celery task status and return result if completed.
    """
    try:
        from celery.result import AsyncResult
        
        task = AsyncResult(task_id)
        
        if task.state == 'PENDING':
            response = {
                'status': 'PENDING',
                'message': 'Task is waiting to be processed...'
            }
        elif task.state == 'PROGRESS':
            response = {
                'status': 'PROGRESS',
                'progress': task.info.get('progress', 0),
                'message': task.info.get('status', 'Processing...')
            }
        elif task.state == 'SUCCESS':
            result = task.result
            response = {
                'status': 'SUCCESS',
                'message': 'Batch created successfully!',
                'details': result,
                'ready_for_summary': True
            }
        elif task.state == 'FAILURE':
            response = {
                'status': 'FAILURE',
                'error': str(task.info),
                'message': 'Batch creation failed'
            }
        else:
            response = {
                'status': task.state,
                'message': f'Unknown status: {task.state}'
            }
            
        return Response(response)
        
    except Exception as e:
        return Response({'error': str(e)}, status=500)

    
# ===== Helper Functions ========
def parse_range(range_str):
    """Parse comma-separated ranges like '1,3,5-7' into [1,3,5,6,7]"""
    if not range_str or not range_str.strip():
        return []
    
    result = []
    try:
        for ids in range_str.split(','):
            id = ids.strip()
            if '-' in id:
                start, end = map(int, id.split('-'))
                result.extend(range(start, end + 1))
            else:
                result.append(int(id))
    except (ValueError, TypeError):
        return []
    
    return result


# ====== GET BATCHES =========
class BatchPaginator(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 150

@api_view(['GET'])
def batches(request):
    try:
        filters = Q()
        batch_location = request.query_params.get('batch_location')
        if batch_location:
            filters &= Q(batch_location=batch_location.strip().upper())
        
        batch_id_param = request.query_params.get('batch_id')
        if batch_id_param:
            batch_id_list = parse_range(batch_id_param)
            if batch_id_list:
                filters &= Q(batch_id__in=batch_id_list)

        queryset = Sensor.objects.filter(filters).only(
            'batch_location', 'batch_id', 'total_wafers', 'total_sensors',
            'batch_label', 'batch_description', 'processes'
        )

        batch_aggregation = {}

        for sensor in queryset.iterator(chunk_size=1000):
            batch_key = (sensor.batch_location, sensor.batch_id)
            
            if batch_key not in batch_aggregation:
                batch_aggregation[batch_key] = {
                    'batch_location': sensor.batch_location,
                    'batch_id': sensor.batch_id,
                    'total_wafers': sensor.total_wafers,
                    'total_sensors': sensor.total_sensors,
                    'batch_label': sensor.batch_label or '',
                    'batch_description': sensor.batch_description or '',
                    'processes_set': {}
                }

            for rel in sensor.processes:
                process_id = rel.get('process_id')
                description = rel.get('description', '')
                timestamp = rel.get('timestamp')

                if not process_id or not timestamp:
                    continue  # skip invalid entries

                key = (process_id, description, timestamp)
                batch_aggregation[batch_key]['processes_set'][key] = {
                    'process_id': process_id,
                    'description': description,
                    'timestamp': timestamp,
                }

        # Build response
        batch_summaries = []
        for batch_key, batch_data in batch_aggregation.items():
            processes_sorted = sorted(
                batch_data['processes_set'].values(),
                key=lambda x: x['timestamp']
            )

            batch_summaries.append({
                'batch_location': batch_data['batch_location'],
                'batch_id': batch_data['batch_id'],
                'total_wafers': batch_data['total_wafers'],
                'total_sensors': batch_data['total_sensors'],
                'batch_label': batch_data['batch_label'],
                'batch_description': batch_data['batch_description'],
                'sensors_per_wafer': batch_data['total_sensors'],
                'total_sensors_in_batch': batch_data['total_wafers']*batch_data['total_sensors'],
                'processes': [
                    {'process_id': p['process_id'], 'description': p['description'], 'timestamp': p['timestamp']}
                    for p in processes_sorted
                ]
            })

        batch_summaries.sort(key=lambda x: (x['batch_location'], x['batch_id']))
        paginator = BatchPaginator()
        paginated_data = paginator.paginate_queryset(batch_summaries, request)
        serializer = BatchSummarySerializer(paginated_data, many=True)
        return paginator.get_paginated_response(serializer.data)
         
    except Exception as e:
        logger.error(f"Error retrieving batches with timestamps: {str(e)}")
        return Response({'error': 'An error occurred while retrieving batch data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    
# ======= GET BATCHES 2: Uses MongoDB Aggregate Operation ========
# Use the ORM version for simplicity:
@api_view(['GET'])
def batches_2(request):
    try:
        filters = Q()
        
        batch_location = request.query_params.get('batch_location')
        if batch_location:
            filters &= Q(batch_location=batch_location.strip().upper())
        
        batch_id_param = request.query_params.get('batch_id')
        if batch_id_param:
            batch_id_list = parse_range(batch_id_param)
            if batch_id_list:
                filters &= Q(batch_id__in=batch_id_list)

        # Get ONE sensor per batch (they all have same batch metadata)
        batch_representatives = {}
        for sensor in Sensor.objects.filter(filters).only(
            'batch_location', 'batch_id', 'total_wafers', 
            'total_sensors', 'batch_label', 'batch_description'
        ).iterator(chunk_size=500):
            key = (sensor.batch_location, sensor.batch_id)
            if key not in batch_representatives:
                batch_representatives[key] = sensor

        # Build response
        batch_summaries = [
            {
                'batch_location': s.batch_location,
                'batch_id': s.batch_id,
                'total_wafers': s.total_wafers,
                'total_sensors': s.total_sensors,
                'batch_label': s.batch_label or '',
                'batch_description': s.batch_description or '',
                'sensors_per_wafer': s.total_sensors,
                'total_sensors_in_batch': s.total_wafers * s.total_sensors
            }
            for s in sorted(
                batch_representatives.values(), 
                key=lambda x: (x.batch_location, x.batch_id)
            )
        ]

        paginator = BatchPaginator()
        paginated_data = paginator.paginate_queryset(batch_summaries, request)
        serializer = BatchSummaryLiteSerializer(paginated_data, many=True)
        return paginator.get_paginated_response(serializer.data)
         
    except Exception as e:
        logger.error(f"Error retrieving batches: {str(e)}", exc_info=True)
        return Response(
            {'error': 'An error occurred while retrieving batch data'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
            
@api_view(['GET'])
def batches_3(request):
    """
    Optimized batch list retrieval - returns only batch metadata.
    Process details are fetched on-demand via batch_detail endpoint.
    
    Performance: ~100-500ms (vs 10+ seconds with process aggregation)
    """
    try:
        # Build match filters
        match_stage = {}
        
        batch_location = request.query_params.get('batch_location')
        if batch_location:
            match_stage['batch_location'] = batch_location.strip().upper()
        
        batch_id_param = request.query_params.get('batch_id')
        if batch_id_param:
            batch_id_list = parse_range(batch_id_param)
            if batch_id_list:
                match_stage['batch_id'] = {'$in': batch_id_list}

        # MongoDB aggregation - group by batch WITHOUT processing process arrays
        pipeline = [
            # Stage 1: Filter documents
            {'$match': match_stage} if match_stage else {'$match': {}},
            
            # Stage 2: Group by batch (take first sensor as representative)
            {'$group': {
                '_id': {
                    'batch_location': '$batch_location',
                    'batch_id': '$batch_id'
                },
                'batch_location': {'$first': '$batch_location'},
                'batch_id': {'$first': '$batch_id'},
                'total_wafers': {'$first': '$total_wafers'},
                'total_sensors': {'$first': '$total_sensors'},
                'batch_label': {'$first': '$batch_label'},
                'batch_description': {'$first': '$batch_description'}
            }},
            
            # Stage 3: Calculate computed fields
            {'$addFields': {
                'sensors_per_wafer': '$total_sensors',
                'total_sensors_in_batch': {
                    '$multiply': ['$total_wafers', '$total_sensors']
                },
                'batch_label': {'$ifNull': ['$batch_label', '']},
                'batch_description': {'$ifNull': ['$batch_description', '']}
            }},
            
            # Stage 4: Sort batches
            {'$sort': {
                'batch_location': 1,
                'batch_id': 1
            }},
            
            # Stage 5: Project final shape (no processes field)
            {'$project': {
                '_id': 0,
                'batch_location': 1,
                'batch_id': 1,
                'total_wafers': 1,
                'total_sensors': 1,
                'batch_label': 1,
                'batch_description': 1,
                'sensors_per_wafer': 1,
                'total_sensors_in_batch': 1
            }}
        ]

        # Execute aggregation
        collection = Sensor.objects.mongo_aggregate(pipeline)
        batch_summaries = list(collection)

        # Paginate results
        paginator = BatchPaginator()
        paginated_data = paginator.paginate_queryset(batch_summaries, request)
        
        # Use simplified serializer (without processes field)
        serializer = BatchSummaryLiteSerializer(paginated_data, many=True)
        
        return paginator.get_paginated_response(serializer.data)
         
    except Exception as e:
        logger.error(f"Error retrieving batches: {str(e)}", exc_info=True)
        return Response(
            {'error': 'An error occurred while retrieving batch data'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
@api_view(['GET'])
def batches_4(request):
    try:
        match_stage = {}
        batch_location = request.query_params.get('batch_location')
        if batch_location:
            match_stage['batch_location'] = batch_location.strip().upper()
        
        batch_id_param = request.query_params.get('batch_id')
        if batch_id_param:
            batch_id_list = parse_range(batch_id_param)
            if batch_id_list:
                match_stage['batch_id'] = {'$in': batch_id_list}

        # MongoDB aggregation pipeline
        pipeline = [
            {'$match': match_stage} if match_stage else {'$match': {}},
            # Unwind processes to aggregate them
            {'$unwind': {'path': '$processes', 'preserveNullAndEmptyArrays': True}},
            # Group by batch and collect unique processes
            {
                '$group': {
                    '_id': {
                        'batch_location': '$batch_location',
                        'batch_id': '$batch_id'
                    },
                    'batch_location': {'$first': '$batch_location'},
                    'batch_id': {'$first': '$batch_id'},
                    'total_wafers': {'$first': '$total_wafers'},
                    'total_sensors': {'$first': '$total_sensors'},
                    'batch_label': {'$first': '$batch_label'},
                    'batch_description': {'$first': '$batch_description'},
                    'processes': {
                        '$addToSet': {
                            'process_id': '$processes.process_id',
                            'description': '$processes.description',
                            'timestamp': '$processes.timestamp'
                        }
                    }
                }
            },
            # Sort processes by timestamp within each batch
            {
                '$project': {
                    '_id': 0,
                    'batch_location': 1,
                    'batch_id': 1,
                    'total_wafers': 1,
                    'total_sensors': 1,
                    'batch_label': 1,
                    'batch_description': 1,
                    'sensors_per_wafer': '$total_sensors',
                    'total_sensors_in_batch': {
                        '$multiply': ['$total_wafers', '$total_sensors']
                    },
                    'processes': {
                        '$sortArray': {
                            'input': '$processes',
                            'sortBy': {'timestamp': 1}
                        }
                    }
                }
            },
            # Sort batches
            {'$sort': {'batch_location': 1, 'batch_id': 1}}
        ]

        # Execute aggregation
        batch_summaries = list(Sensor.objects.mongo_aggregate(pipeline))
        
        # Clean up None values
        for batch in batch_summaries:
            batch['batch_label'] = batch.get('batch_label') or ''
            batch['batch_description'] = batch.get('batch_description') or ''
            # Filter out None processes (from empty arrays)
            batch['processes'] = [
                p for p in batch.get('processes', [])
                if p.get('process_id') and p.get('timestamp')
            ]

        paginator = BatchPaginator()
        paginated_data = paginator.paginate_queryset(batch_summaries, request)
        serializer = BatchSummarySerializer(paginated_data, many=True)
        return paginator.get_paginated_response(serializer.data)
         
    except Exception as e:
        logger.error(f"Error retrieving batches with timestamps: {str(e)}")
        return Response({'error': 'An error occurred while retrieving batch data'}, 
                       status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ======= BATCH UPDATE ===========
@api_view(['PUT'])
def update_batch_optimized(request, batch_location, batch_id):
    """
    Fully optimized batch update for sensors using JSONField processes.
    Supports:
      - Range-based wafer and sensor selection
      - Bulk sensor field updates
      - Add/remove process associations
    """
    data = request.data
    print(f"Request Data: {data}")

    wafer_ids = parse_range(str(data.get('wafer_ids', '')))
    sensor_ids = parse_range(str(data.get('sensor_ids', '')))
    new_process_data = data.get('new_process_data', [])
    delete_list = data.get('delete_list', [])
    update_data = data.get('updates', {})

    response_details = {
        "updated_items": 0,
        "created_processes": 0,
        "deleted_processes": 0,
        "performance_metrics": {}
    }

    try:
        start_time = time.time()

        with transaction.atomic():
            # Step 1: Retrieve sensors in batch with filters
            sensors_qs = Sensor.objects.filter(batch_location=batch_location, batch_id=batch_id)
            if wafer_ids:
                sensors_qs = sensors_qs.filter(wafer_id__in=wafer_ids)
            if sensor_ids:
                sensors_qs = sensors_qs.filter(sensor_id__in=sensor_ids)

            # Only fetch necessary fields to reduce memory usage
            sensors_data = list(sensors_qs.only(
                'id', 'processes', 'process_ids', 'unique_identifier'
            ))

            if not sensors_data:
                return Response({'error': 'No sensors found matching criteria'},
                                status=status.HTTP_404_NOT_FOUND)

            response_details["performance_metrics"]["query_time"] = f"{time.time() - start_time:.3f}s"

            # Step 2: Bulk update sensor fields
            if update_data:
                allowed_fields = {
                    'batch_label', 'batch_description', 'wafer_label', 'wafer_description',
                    'wafer_design_id', 'sensor_label', 'sensor_description',
                    'total_wafers', 'total_sensors'
                }
                update_fields = {
                    field: value for field, value in update_data.items()
                    if field in allowed_fields and hasattr(Sensor, field)
                }
                if update_fields:
                    sensors_qs.update(**update_fields)
                    response_details["updated_items"] = len(sensors_data)

            # Step 3: Add new process associations
            if new_process_data:
                creation_start = time.time()
                valid_process_ids = [p['process_id'] for p in new_process_data if p.get('process_id')]
                valid_process_files = {
                    pf.process_id: pf
                    for pf in ProcessFile.objects.filter(process_id__in=valid_process_ids)
                }

                created_count = 0
                for sensor in sensors_data:
                    updated = False
                    for process_entry in new_process_data:
                        process_id = process_entry.get('process_id')
                        description = process_entry.get('description')
                        timestamp = process_entry.get('timestamp')
                        if not process_id or process_id not in valid_process_files:
                            continue
                        if not description:
                            continue
                        if not timestamp:
                            continue
                        # Parse timestamp string to datetime
                        timestamp = ensure_datetime(timestamp)

                        if process_id not in sensor.process_ids:
                            sensor.processes.append({"process_id": process_id, "description": description, "timestamp": timestamp})
                            sensor.process_ids.append(process_id)
                            updated = True

                    if updated:
                        # Update last_process_timestamp
                        if sensor.processes:
                            sensor.last_process_timestamp = max(
                                ensure_datetime(rel['timestamp']) for rel in sensor.processes
                            )
                        sensor.process_count = len(sensor.process_ids)
                        sensor.save(update_fields=['processes', 'process_ids', 'process_count', 'last_process_timestamp'])
                        created_count += 1

                response_details["created_processes"] = created_count
                response_details["performance_metrics"]["creation_time"] = f"{time.time() - creation_start:.3f}s"

            # Step 4: Remove process associations
            if delete_list:
                deletion_start = time.time()
                deleted_count = 0
                for sensor in sensors_data:
                    updated = False
                    for process_entry in delete_list:
                        process_id = process_entry.get('process_id')
                        if not process_id:
                            continue
                        original_count = len(sensor.processes)
                        sensor.processes = [
                            rel for rel in sensor.processes if rel["process_id"] != process_id
                        ]
                        sensor.process_ids = [rel["process_id"] for rel in sensor.processes]
                        if len(sensor.processes) != original_count:
                            updated = True
                    if updated:
                        # Update last_process_timestamp
                        if sensor.processes:
                            sensor.last_process_timestamp = max(
                                ensure_datetime(rel['timestamp']) for rel in sensor.processes)
                        else:
                            sensor.last_process_timestamp = None
                        sensor.process_count = len(sensor.process_ids)
                        sensor.save(update_fields=['processes', 'process_ids', 'process_count', 'last_process_timestamp'])
                        deleted_count += 1

                response_details["deleted_processes"] = deleted_count
                response_details["performance_metrics"]["deletion_time"] = f"{time.time() - deletion_start:.3f}s"

        response_details["performance_metrics"]["total_time"] = f"{time.time() - start_time:.3f}s"
        return Response(response_details, status=status.HTTP_200_OK)

    except Exception as e:
        traceback.print_exc()
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
def update_batch_async(request, batch_location, batch_id):
    """
    Trigger async batch update via Celery.
    Returns task_id immediately so client can poll for status/result.
    """
    data = request.data
    wafer_ids = parse_range(str(data.get('wafer_ids', '')))
    sensor_ids = parse_range(str(data.get('sensor_ids', '')))
    new_process_data = data.get('new_process_data', [])
    delete_list = data.get('delete_list', [])
    update_data = data.get('updates', {})

    task = update_batch_task.delay(
        batch_location, batch_id, wafer_ids, sensor_ids,
        new_process_data, delete_list, update_data
    )
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "global_tasks", 
        {
            "type": "task_update", 
            "data": {
            "task_id": str(task.id),
            "progress": 0,
            "state": "STARTED",
            "message": f"Updating Batch {batch_location}{batch_id}!" 
            }
        }
    )

    return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)

@api_view(['PUT'])
def unified_sensor_update_endpoint(request):
    """
    Unified API endpoint for sensor updates supporting both batch and individual strategies.
    
    Expected payload structure:
    {
        "selection_strategy": "batch" | "individual",
        
        // For batch strategy:
        "batch_location": "M001",
        "batch_id": 123,
        "wafer_ids": "1,3,5-7",  // Will be parsed to ranges
        "sensor_ids": "1-10,15", // Will be parsed to ranges
        
        // For individual strategy:
        "u_ids": ["M001123-01-001", "M001123-01-002"],
        
        // Common update operations:
        "updates": {
            "label": "GOOD",
            "sensor_description": "Updated description",
            "batch_label": "New batch label"
        },
        "new_process_data": [
            {
                "process_id": "P001",
                "description": "Process description",
                "timestamp": "2024-01-01T10:00:00Z"
            }
        ],
        "delete_list": [
            {"process_id": "P002"}
        ]
    }
    """
    
    data = request.data
    selection_strategy = data.get('selection_strategy')
    
    if not selection_strategy:
        return Response(
            {'error': 'selection_strategy is required ("batch" or "individual")'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        if selection_strategy == 'batch':
            # Parse range strings for batch strategy
            wafer_ids_str = data.get('wafer_ids', '')
            sensor_ids_str = data.get('sensor_ids', '')
            
            wafer_ids = parse_range(wafer_ids_str) if wafer_ids_str else None
            sensor_ids = parse_range(sensor_ids_str) if sensor_ids_str else None
            
            # Launch unified task with batch parameters
            task = unified_sensor_update_task.delay(
                selection_strategy='batch',
                batch_location=data.get('batch_location'),
                batch_id=data.get('batch_id'),
                wafer_ids=wafer_ids,
                sensor_ids=sensor_ids,
                update_data=data.get('updates', {}),
                new_process_data=data.get('new_process_data', []),
                delete_list=data.get('delete_list', [])
            )
            
        elif selection_strategy == 'individual':
            # Launch unified task with individual parameters
            task = unified_sensor_update_task.delay(
                selection_strategy='individual',
                unique_identifiers=data.get('u_ids', []),
                update_data=data.get('updates', {}),
                new_process_data=data.get('new_process_data', []),
                delete_list=data.get('delete_list', [])
            )
            
        else:
            return Response(
                {'error': 'Invalid selection_strategy. Must be "batch" or "individual"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            'task_id': task.id,
            'status': 'Task started',
            'selection_strategy': selection_strategy,
            'message': f'Sensor update task initiated with {selection_strategy} strategy'
        }, status=status.HTTP_202_ACCEPTED)
        
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT']) 
def update_sensors_by_batch_endpoint(request, batch_location, batch_id):
    """
    Backward-compatible batch update endpoint (URL parameters).
    Maps to unified task with batch strategy.
    """
    data = request.data
    
    # Parse range strings from request data
    wafer_ids = parse_range(data.get('wafer_ids', ''))
    sensor_ids = parse_range(data.get('sensor_ids', ''))
    
    task = unified_sensor_update_task.delay(
        selection_strategy='batch',
        batch_location=batch_location,
        batch_id=int(batch_id),
        wafer_ids=wafer_ids if wafer_ids else None,
        sensor_ids=sensor_ids if sensor_ids else None,
        update_data=data.get('updates', {}),
        new_process_data=data.get('new_process_data', []),
        delete_list=data.get('delete_list', [])
    )
    
    return Response({
        'task_id': task.id,
        'status': 'Batch update task started',
        'batch_location': batch_location,
        'batch_id': batch_id
    }, status=status.HTTP_202_ACCEPTED)


@api_view(['PUT'])
def update_sensors_by_identifiers_endpoint(request):
    """
    Backward-compatible individual update endpoint.
    Maps to unified task with individual strategy.
    """
    data = request.data
    
    task = unified_sensor_update_task.delay(
        selection_strategy='individual',
        unique_identifiers=data.get('u_ids', []),
        update_data=data.get('updates', {}),
        new_process_data=data.get('new_process_data', []),
        delete_list=data.get('delete_list', [])
    )
    
    return Response({
        'task_id': task.id,
        'status': 'Individual sensor update task started',
        'sensor_count': len(data.get('u_ids', []))
    }, status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
def get_task_status(request, task_id):
    """Get the status of a running sensor update task."""
    from celery.result import AsyncResult
    
    try:
        task = AsyncResult(task_id)
        
        if task.state == 'PENDING':
            response = {
                'state': task.state,
                'status': 'Task is waiting to be processed'
            }
        elif task.state == 'PROGRESS':
            response = {
                'state': task.state,
                'current': task.info.get('current', 0),
                'total': task.info.get('total', 1),
                'percent': task.info.get('percent', 0),
                'status': f"Processing sensor {task.info.get('current', 0)} of {task.info.get('total', 1)}"
            }
        elif task.state == 'SUCCESS':
            response = {
                'state': task.state,
                'result': task.info,
                'status': 'Task completed successfully'
            }
        else:  # FAILURE
            response = {
                'state': task.state,
                'error': str(task.info),
                'status': 'Task failed'
            }
            
        return Response(response)
        
    except Exception as e:
        return Response(
            {'error': f'Could not get task status: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



@api_view(['GET'])
def batch_update_status(request, task_id):
    """
    Check Celery task status for batch update.
    """
    result = AsyncResult(task_id)
    if result.state == "PENDING":
        return Response({"status": "PENDING"}, status=status.HTTP_200_OK)
    elif result.state == "SUCCESS":
        return Response({"status": "SUCCESS", "result": result.result}, status=status.HTTP_200_OK)
    elif result.state == "FAILURE":
        return Response({"status": "FAILURE", "error": str(result.result)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        return Response({"status": result.state}, status=status.HTTP_200_OK)

@api_view(['GET'])
def batch_detail(request, batch_location, batch_id):
    try:
        # Fetch only one representative sensor document for the batch
        sensor = (
            Sensor.objects
            .filter(batch_location=batch_location, batch_id=batch_id)
            .only(
                'batch_location',
                'batch_id',
                'batch_label',
                'batch_description',
                'total_wafers',
                'total_sensors',
                'processes'  # include the JSONField
            )
            .first()
        )

        if not sensor:
            return Response({'error': 'Batch not found'}, status=status.HTTP_404_NOT_FOUND)

        # Build response manually for performance (skip serializer overhead if desired)
        batch_data = {
            "batch_location": sensor.batch_location,
            "batch_id": sensor.batch_id,
            "batch_label": sensor.batch_label,
            "batch_description": sensor.batch_description,
            "total_wafers": sensor.total_wafers,
            "total_sensors": sensor.total_sensors,
            # Directly include embedded JSONField
            "sensor_processes": sensor.processes or []
        }

        serializer = BatchDetailSerializer(batch_data)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": f"Error retrieving batch details: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ====== Sensor Labels =========
@api_view(['POST'])
def sensor_labels(request):
    serializer = SensorLabelSerializer(data=request.data)
    if serializer.is_valid():
        label = serializer.save()
        print(f"Label created: {label.name}")
        return Response({'message': 'Labels created successfully!'}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def labels(request):
    labels = SensorLabel.objects.all()
    serializer = SensorLabelSerializer(labels, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def labels_lst(request):
    s_labels = SensorLabel.objects.values('name')
    labels_list = [{'name': label['name']} for label in s_labels]
    return Response(labels_list)

# ===== Sensor Verification =====
@api_view(['POST'])
def veryify_sensor(request):
    """ 
    Verifies a list of sensor uniue ids (e.g. 'M001-02-102)
    """
    identifiers = request.data.get('sensors', [])
    if not identifiers:
        return Response({'error': 'No sensors provided'}, status=status.HTTP_400_BAD_REQUEST)
    sensors = Sensor.objects.filter(unique_identifier__in=identifiers).only('unique_identifier', 'sensor_description', 'processes')
    
    if not sensors.exists():
        return Response({'error': 'No matching sensors found.'}, status=status.HTTP_404_NOT_FOUND)
    
    serializer = SLSerializer(sensors, many=True)
    return Response({'validated_sensors': serializer.data}, status=status.HTTP_200_OK)

# =============================================================================
# OPTIMIZED SL_WITH_PROCESSES FUNCTION (Djongo-compatible)
# =============================================================================

@api_view(['PUT'])
def sl_with_processes_optimized(request):
    """
    Optimized sensor-level update for specific sensors by unique_identifier.
    Handles:
    - Updating sensor metadata (label, description)
    - Adding embedded processes
    - Deleting embedded processes
    """
    data = request.data
    u_ids = data.get('u_ids', [])
    new_process_data = data.get('new_process_data', [])
    delete_list = data.get('delete_list', [])
    update_data = data.get('updates', {})

    if not u_ids:
        return Response({'error': 'u_ids parameter required'}, status=status.HTTP_400_BAD_REQUEST)

    response_details = {
        "updated_items": 0,
        "created_items": 0,
        "deleted_items": 0,
        "invalid_u_ids": [],
        "performance_metrics": {}
    }

    try:
        start_time = time.time()

        with transaction.atomic():
            # Step 1: Fetch matching sensors
            sensors = list(Sensor.objects.filter(unique_identifier__in=u_ids))
            found_u_ids = {s.unique_identifier for s in sensors}
            invalid_u_ids = set(u_ids) - found_u_ids
            response_details['invalid_u_ids'] = list(invalid_u_ids)

            if not sensors:
                return Response({'error': 'No valid sensors found.'}, status=status.HTTP_404_NOT_FOUND)

            # Step 2: Update allowed sensor fields
            if update_data:
                allowed_fields = ['sensor_label', 'sensor_description']
                for sensor in sensors:
                    for field in allowed_fields:
                        if field in update_data:
                            setattr(sensor, field, update_data[field])

                    # Handle label (foreign key)
                    if 'label' in update_data:
                        try:
                            label_obj = SensorLabel.objects.get(name=update_data['label'])
                            sensor.sensor_label = label_obj
                        except SensorLabel.DoesNotExist:
                            return Response({'error': f"Label '{update_data['label']}' does not exist."},
                                            status=status.HTTP_400_BAD_REQUEST)

                    sensor.save()
                response_details["updated_items"] = len(sensors)

            # Step 3: Add new processes
            if new_process_data:
                created_count = 0
                for sensor in sensors:
                    for process_entry in new_process_data:
                        pid = process_entry.get("process_id")
                        desc = process_entry.get("description")
                        ts = process_entry.get("timestamp")
                        if not pid or not ts:
                            continue

                        # Ensure timestamp is datetime
                        ts = ensure_datetime(ts)

                        before_count = len(sensor.processes)
                        sensor.add_processes(pid, desc, ts)
                        after_count = len(sensor.processes)
                        if after_count > before_count:
                            created_count += 1

                response_details["created_items"] = created_count

            # Step 4: Delete processes
            if delete_list:
                deleted_count = 0
                for sensor in sensors:
                    for process_entry in delete_list:
                        pid = process_entry.get("process_id")
                        if pid:
                            before_count = len(sensor.processes)
                            sensor.remove_process(pid)
                            after_count = len(sensor.processes)
                            if after_count < before_count:
                                deleted_count += 1

                response_details["deleted_items"] = deleted_count

        total_time = time.time() - start_time
        response_details["performance_metrics"]["total_time"] = f"{total_time:.3f}s"

        return Response(response_details, status=status.HTTP_200_OK)

    except Exception as e:
        traceback.print_exc()
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['GET'])
def sensors_dropdown(request):
    sensors = Sensor.objects.values_list('unique_identifier', flat=True)
    return Response(list(sensors))

    
    
# ======== TIFF File COnverision =========
@api_view(['POST'])
def upload_image_with_imagegroups(request):
    u_ids = request.data.getlist('u_ids')
    process_ids = request.data.getlist('process_ids')
    image_files = request.FILES.getlist('image_files')

    if not (len(image_files) == len(process_ids) == len(u_ids)):
        return Response({'error': 'Array length mismatch'}, status=400)

    with transaction.atomic():
        unique_u_ids = list(set(u_ids))
        sensors_lookup = {
            sensor.unique_identifier: sensor
            for sensor in Sensor.objects.filter(unique_identifier__in=unique_u_ids)
        }

        success_count = 0
        failure_details = []

        for i in range(len(image_files)):
            u_id = u_ids[i]
            process_id = process_ids[i]
            uploaded_file = image_files[i]

            try:
                sensor = sensors_lookup.get(u_id)
                if not sensor:
                    failure_details.append({'index': i, 'u_id': u_id, 'reason': 'Sensor not found'})
                    continue

                file_name, ext = os.path.splitext(uploaded_file.name)
                ext = ext.lower()

                converted_file = uploaded_file
                original_file_ref = None

                # ====================================================
                # Handle TIFF Conversion
                # ====================================================
                if ext in [".tif", ".tiff"]:
                    try:
                        pil_img = PilImage.open(uploaded_file)
                        pil_img = pil_img.convert("RGB")

                        buffer = io.BytesIO()
                        pil_img.save(buffer, format="PNG")  # always safe for web
                        buffer.seek(0)

                        converted_file = ContentFile(buffer.read(), name=f"{file_name}.png")
                        original_file_ref = uploaded_file
                    except Exception as e:
                        failure_details.append({'index': i, 'u_id': u_id, 'reason': f'TIFF conversion failed: {str(e)}'})
                        continue

                # ====================================================
                # Save Image model
                # ====================================================
                image_obj = Image.objects.create(
                    sensor=sensor,
                    process_id=process_id,
                    image=converted_file,       # always displayable
                    original_file=original_file_ref,  # only if TIFF
                    sensor_unique_id=u_id
                )

                # ====================================================
                # Update ImageGroup (extended schema)
                # ====================================================
                group_key = f"{u_id}|{process_id or 'Unspecified'}"
                group, created = ImageGroup.objects.get_or_create(
                    group_key=group_key,
                    defaults={
                        'sensor_unique_id': u_id,
                        'process_id': process_id,
                        'images_data': [],
                        'image_count': 0
                    }
                )

                filename = os.path.basename(image_obj.image.name)
                base, _ = os.path.splitext(filename)

                image_data = {
                    'id': str(image_obj.id),
                    'display_url': image_obj.image.url,   # converted (frontend safe)
                    'original_url': image_obj.original_file.url if image_obj.original_file else None,
                    'file_name': filename,
                    'suffix': base.split('_')[-1] if '_' in base else '',
                    'upload_date': image_obj.upload_date.isoformat() if image_obj.upload_date else None
                }

                if not any(img['id'] == image_data['id'] for img in group.images_data):
                    group.images_data.append(image_data)
                    group.image_count = len(group.images_data)
                    group.save()

                success_count += 1

            except Exception as e:
                failure_details.append({'index': i, 'u_id': u_id, 'reason': str(e)})

        return Response({
            'message': f'{success_count} image(s) uploaded and groups updated!',
            'failures': failure_details
        }, status=status.HTTP_201_CREATED if success_count > 0 else status.HTTP_400_BAD_REQUEST)           
        
# =============================================================================
# MAIN PAGINATION FUNCTION - This replaces your get_images_2 function
# =============================================================================

@api_view(['GET'])
def get_images_optimized_final(request):
    """
    Final optimized image pagination using ImageGroup for perfect grouping
    This ensures groups never split across pages
    """
    # Get filter parameters
    sensor_query = request.GET.get('sensor', '').lower().strip()
    process_query = request.GET.get('process', '').lower().strip()
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 5))
    
    print(f"Query params - Sensor: '{sensor_query}', Process: '{process_query}', Page: {page}")
    
    # Start with all ImageGroups
    groups_query = ImageGroup.objects.all()
    
    # Apply filters to groups (not individual images!)
    if sensor_query:
        groups_query = groups_query.filter(sensor_unique_id__icontains=sensor_query)
    
    if process_query:
        if process_query == 'all':
            # Don't filter by process for "all"
            pass
        else:
            groups_query = groups_query.filter(process_id__icontains=process_query)
    
    # Order for consistent pagination
    groups_query = groups_query.order_by('sensor_unique_id', 'process_id')
    
    # Get total count for pagination metadata
    total_groups = groups_query.count()
    print(f"Found {total_groups} groups matching filters")
    
    # Paginate the GROUPS (not individual images)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_groups = groups_query[start_idx:end_idx]
    
    print(f"Returning groups {start_idx} to {end_idx}")
    
    # Convert groups back to flat structure for frontend compatibility
    flattened_results = []
    total_images_on_page = 0
    
    for group in paginated_groups:
        for image_data in group.images_data:
            flattened_results.append({
                'sensor': group.sensor_unique_id,
                'process_id': group.process_id,
                'image': image_data['display_url'],
                'file_name': image_data['file_name'],
                'suffix': image_data['suffix'],
                'download_url': image_data['original_url'],
            })
            total_images_on_page += 1
    
    # Pagination metadata
    has_next = end_idx < total_groups
    has_previous = start_idx > 0
    
    next_url = f"?page={page + 1}"
    if sensor_query:
        next_url += f"&sensor={sensor_query}"
    if process_query and process_query != 'all':
        next_url += f"&process={process_query}"
    
    prev_url = f"?page={page - 1}"
    if sensor_query:
        prev_url += f"&sensor={sensor_query}"
    if process_query and process_query != 'all':
        prev_url += f"&process={process_query}"
    
    response_data = {
        'count': sum(group.image_count for group in ImageGroup.objects.filter(
            sensor_unique_id__icontains=sensor_query if sensor_query else '',
            process_id__icontains=process_query if process_query and process_query != 'all' else ''
        )),
        'next': next_url if has_next else None,
        'previous': prev_url if has_previous else None,
        'results': flattened_results,
        
        # Extra metadata for debugging/monitoring
        'page_info': {
            'current_page': page,
            'total_groups': total_groups,
            'groups_on_page': len(paginated_groups),
            'total_images_on_page': total_images_on_page,
            'page_size': page_size
        }
    }
    
    print(f"Returning {len(flattened_results)} images from {len(paginated_groups)} groups")
    return Response(response_data)

# ========== DASHBOARD METRICS ===============
# No longer in use. Replaced by methods in consumers.py for faster synchronized loads.
@api_view(['GET'])
def dashboard_core_stats(request):
    """
    Core production statistics for the dashboard - MongoDB/Djongo compatible
    """
    try:
        # Core metrics using basic queries
        total_sensors = Sensor.objects.count()
        
        # Get unique batches by iterating (MongoDB compatible)
        unique_batches = set()
        unique_wafers = set()
        batch_sensor_counts = []
        active_locations = set()
        
        for sensor in Sensor.objects.only('batch_location', 'batch_id', 'wafer_id'):
            batch_key = (sensor.batch_location, sensor.batch_id)
            unique_batches.add(batch_key)
            unique_wafers.add((sensor.batch_location, sensor.batch_id, sensor.wafer_id))
            active_locations.add(sensor.batch_location)
        
        total_batches = len(unique_batches)
        total_wafers = len(unique_wafers)
        
        # Calculate average sensors per batch
        if unique_batches:
            batch_counts = defaultdict(int)
            for sensor in Sensor.objects.only('batch_location', 'batch_id'):
                batch_key = (sensor.batch_location, sensor.batch_id)
                batch_counts[batch_key] += 1
            avg_sensors_per_batch = sum(batch_counts.values()) / len(batch_counts)
        else:
            avg_sensors_per_batch = 0
        
        # Weekly growth calculation
        week_ago = timezone.now() - timedelta(days=7)
        sensors_this_week = Sensor.objects.filter(
            last_process_timestamp__gte=week_ago
        ).count()
        
        # Count unique batches this week
        batches_this_week_set = set()
        for sensor in Sensor.objects.filter(last_process_timestamp__gte=week_ago).only('batch_location', 'batch_id'):
            batches_this_week_set.add((sensor.batch_location, sensor.batch_id))
        batches_this_week = len(batches_this_week_set)
        
        return Response({
            'total_sensors': total_sensors,
            'total_batches': total_batches,
            'total_wafers': total_wafers,
            'avg_sensors_per_batch': round(avg_sensors_per_batch, 1),
            'active_locations': len(active_locations),
            'sensors_this_week': sensors_this_week,
            'batches_this_week': batches_this_week
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error fetching core stats: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def dashboard_recent_activity(request):
    """
    Recent activity metrics for the dashboard - MongoDB/Djongo compatible
    """
    try:
        # Find latest batch by iterating through sensors
        latest_batch = None
        latest_timestamp = None
        
        for sensor in Sensor.objects.only('batch_location', 'batch_id', 'batch_label', 'last_process_timestamp'):
            if sensor.last_process_timestamp:
                if not latest_timestamp or sensor.last_process_timestamp > latest_timestamp:
                    latest_timestamp = sensor.last_process_timestamp
                    latest_batch = {
                        'batch_location': sensor.batch_location,
                        'batch_id': sensor.batch_id,
                        'batch_label': sensor.batch_label,
                        'latest_process': sensor.last_process_timestamp
                    }
        
        # Find last process applied globally
        last_process_sensor = None
        last_process_time = None
        
        for sensor in Sensor.objects.exclude(last_process_timestamp__isnull=True).only('unique_identifier', 'processes', 'last_process_timestamp'):
            if sensor.last_process_timestamp:
                if not last_process_time or sensor.last_process_timestamp > last_process_time:
                    last_process_time = sensor.last_process_timestamp # To do: ensure timestamp is in ISO 1806 format
                    last_process_sensor = sensor
        
        last_process_info = None
        if last_process_sensor and last_process_sensor.processes:
            # Get the most recent process from embedded processes
            most_recent_process = max(
                last_process_sensor.processes, 
                key=lambda p: p['timestamp']
            )
            last_process_info = {
                'process_id': most_recent_process['process_id'],
                'timestamp': last_process_sensor.last_process_timestamp,
                'sensor_id': last_process_sensor.unique_identifier
            }
        
        # Today's activity
        today = timezone.now().date()
        today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        
        today_batches_set = set()
        for sensor in Sensor.objects.filter(last_process_timestamp__gte=today_start).only('batch_location', 'batch_id'):
            today_batches_set.add((sensor.batch_location, sensor.batch_id))
        today_batches = len(today_batches_set)
        
        # Active Celery tasks
        try:
            inspect = current_app.control.inspect()
            active_tasks = inspect.active()
            total_active = sum(len(tasks) for tasks in active_tasks.values()) if active_tasks else 0
        except:
            total_active = 0
        
        return Response({
            'last_batch': {
                'identifier': f"{latest_batch['batch_location']}{latest_batch['batch_id']:03d}" if latest_batch else None,
                'label': latest_batch['batch_label'] if latest_batch else None,
                'timestamp': latest_batch['latest_process'] if latest_batch else None
            } if latest_batch else None,
            'last_process': last_process_info,
            'today_batches': today_batches,
            'active_celery_tasks': total_active
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error fetching recent activity: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    
@api_view(['GET'])
def dahsboard_latest_batches(request):
    """
    Return the latest 5 distinct batches from MongoDB.
    Uses last_process_timestamp to order batches.
    """

    # Query only the needed fields, sorted by timestamp
    queryset = (
        Sensor.objects.only(
            'batch_location',
            'batch_id',
            'batch_label',
            'batch_description',
            'total_wafers',
            'total_sensors',
            'last_process_timestamp'
        )
        .order_by('-last_process_timestamp')
    )

    seen_batches = set()
    batches = []

    # Deduplicate in Python
    for sensor in queryset:
        batch_key = (sensor.batch_location, sensor.batch_id)
        if batch_key not in seen_batches:
            seen_batches.add(batch_key)
            total_sensors = sensor.total_wafers * sensor.total_sensors

            batches.append({
                'batch_location': sensor.batch_location,
                'batch_id': sensor.batch_id,
                'batch_label': sensor.batch_label or '',
                'batch_description': sensor.batch_description or '',
                'total_wafers': sensor.total_wafers,
                'sensors_per_wafer': sensor.total_sensors,
                'total_sensors': total_sensors,
                'last_process_timestamp': sensor.last_process_timestamp,
            })

        if len(batches) == 5:
            break  # stop once we have 5

    return Response(batches, status=status.HTTP_200_OK)

@api_view(['GET'])
def dashboard_processes(self):
    """Get process statistics - MongoDB/Djongo compatible"""
    try:
        
        # Get total processes from ProcessFile model (same as in get_core_stats)
        total_processes = ProcessFile.objects.count()
        
        # Initialize counters
        process_counter = Counter()
        sensors_with_processes = 0
        total_process_applications = 0
        batch_process_stats = defaultdict(lambda: {'sensors': 0, 'processes': Counter()})
        
        # Iterate through all sensors to analyze embedded processes
        for sensor in Sensor.objects.only('batch_location', 'batch_id', 'processes'):
            batch_key = f"{sensor.batch_location}{sensor.batch_id:03d}"
            
            if sensor.processes:
                sensors_with_processes += 1
                sensor_process_count = len(sensor.processes)
                total_process_applications += sensor_process_count
                
                # Update batch stats
                batch_process_stats[batch_key]['sensors'] += 1
                
                # Count each process application
                for process in sensor.processes:
                    process_id = process.get('process_id')
                    if process_id:
                        process_counter[process_id] += 1
                        batch_process_stats[batch_key]['processes'][process_id] += 1
        
        # Calculate average processes per sensor
        avg_processes_per_sensor = 0
        if sensors_with_processes > 0:
            avg_processes_per_sensor = round(total_process_applications / sensors_with_processes, 2)
        
        # Get most applied processes (top 5)
        most_applied_processes = [
            {
                'process_id': process_id,
                'applications': count,
                'percentage': round((count / total_process_applications) * 100, 1) if total_process_applications > 0 else 0
            }
            for process_id, count in process_counter.most_common(5)
        ]
        
        # Get batch process diversity (batches with most diverse processes)
        batch_diversity = []
        for batch_key, stats in batch_process_stats.items():
            unique_processes = len(stats['processes'])
            if unique_processes > 0:
                batch_diversity.append({
                    'batch_identifier': batch_key,
                    'unique_processes': unique_processes,
                    'total_applications': sum(stats['processes'].values()),
                    'sensors_processed': stats['sensors']
                })
        
        # Sort by unique processes descending, take top 3
        batch_diversity.sort(key=lambda x: x['unique_processes'], reverse=True)
        top_diverse_batches = batch_diversity[:3]
        
        return Response({
            'total_processes': total_processes,
            'total_process_applications': total_process_applications,
            'sensors_with_processes': sensors_with_processes,
            'avg_processes_per_sensor': avg_processes_per_sensor,
            'most_applied_processes': most_applied_processes,
            'top_diverse_batches': top_diverse_batches,
            'unique_processes_applied': len(process_counter)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error fetching process stats: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ====== Unified Verification =========
@api_view(['POST'])
def verify_sensors(request):
    """
    Unified verification endpoint for sensors.
    Supports:
      - Batch verification (batch_location + batch_id [+ wafer_ids/sensor_ids])
      - Sensor-level verification (list of unique_identifiers)
    Returns minimal metadata and aggregated processes for frontend pre-population.
    """
    data = request.data
    batch_location = data.get("batch_location")
    batch_id = data.get("batch_id")
    u_ids = data.get("u_ids", [])
    
    # Ensure u_ids is always a list
    if isinstance(u_ids, str):
        u_ids = [u_ids]

    response = {
        "sensors": [],
        "batch_metadata": None,
        "invalid_u_ids": []
    }

    try:
        # --- Batch Mode ---
        if batch_location and batch_id:
            sensors_qs = Sensor.objects.filter(batch_location=batch_location, batch_id=batch_id).only(
                'batch_location', 'batch_id', 'total_wafers', 'total_sensors',
                'batch_label', 'batch_description', 'processes'
            )
           
            if not sensors_qs.exists():
                return Response({"error": "No sensors found for the specified batch"}, status=status.HTTP_404_NOT_FOUND)

            # Use first sensor for batch-level metadata
            first_sensor = sensors_qs.first()
            response["batch_metadata"] = {
                "batch_location": first_sensor.batch_location,
                "batch_id": first_sensor.batch_id,
                "total_wafers": first_sensor.total_wafers,
                "total_sensors": first_sensor.total_sensors,
                "batch_label": first_sensor.batch_label,
                "batch_description": first_sensor.batch_description,
            }

            # Aggregate all processes across the batch
            processes_set = set()
            for s in sensors_qs:
                for p in s.processes:
                    processes_set.add((p.get('process_id'), p.get('description'), p.get('timestamp')))

            response["batch_metadata"]["processes"] = [
                {"process_id": pid, "description": desc, "timestamp": ts}
                for pid, desc, ts in processes_set
            ]

        # --- Sensor Mode ---
        elif u_ids:
            sensors_qs = Sensor.objects.filter(unique_identifier__in=u_ids).only(
                'unique_identifier', 'sensor_label', 'sensor_description', 'processes'
            )

            sensors_list = list(sensors_qs)
            found_u_ids = {s.unique_identifier for s in sensors_list}
            invalid_u_ids = set(u_ids) - found_u_ids
            response["invalid_u_ids"] = list(invalid_u_ids)

            if not sensors_list:
                return Response({"error": "No valid sensors found."}, status=status.HTTP_404_NOT_FOUND)

            # Return minimal fields + processes for each sensor
            response["sensors"] = [
                {
                    "unique_identifier": s.unique_identifier,
                    "sensor_label": s.sensor_label,
                    "sensor_description": s.sensor_description,
                    "processes": s.processes
                }
                for s in sensors_list
            ]

        else:
            return Response(
                {"error": "Either (batch_location + batch_id) or u_ids[] must be provided."},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(response, status=status.HTTP_200_OK)

    except Exception as e:
        traceback.print_exc()
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['PUT'])
def update_sensors(request):
    """
    Unified update function for Sensors.
    Supports:
    - Batch updates (batch_location + batch_id [+ wafer_ids/sensor_ids])
    - Sensor-level updates (unique_identifier list)
    - Bulk metadata updates
    - Add/remove process associations
    """
    data = request.data
    batch_location = data.get("batch_location")
    batch_id = data.get("batch_id")
    u_ids = data.get("u_ids", [])
    wafer_ids = parse_range(str(data.get("wafer_ids", "")))
    sensor_ids = parse_range(str(data.get("sensor_ids", "")))
    new_process_data = data.get("new_process_data", [])
    delete_list = data.get("delete_list", [])
    update_data = data.get("updates", {})

    response_details = {
        "updated_items": 0,
        "created_processes": 0,
        "deleted_processes": 0,
        "invalid_u_ids": [],
        "performance_metrics": {}
    }

    try:
        start_time = time.time()

        with transaction.atomic():
            # --- Mode selection ---
            sensors_qs = None
            if batch_location and batch_id:
                # Batch mode
                sensors_qs = Sensor.objects.filter(
                    batch_location=batch_location,
                    batch_id=batch_id
                )
                if wafer_ids:
                    sensors_qs = sensors_qs.filter(wafer_id__in=wafer_ids)
                if sensor_ids:
                    sensors_qs = sensors_qs.filter(sensor_id__in=sensor_ids)

                allowed_fields = {
                    'batch_label', 'batch_description', 'wafer_label',
                    'wafer_description', 'wafer_design_id',
                    'sensor_label', 'sensor_description',
                    'total_wafers', 'total_sensors'
                }

            elif u_ids:
                # Sensor mode
                sensors_qs = Sensor.objects.filter(unique_identifier__in=u_ids)
                found_u_ids = {s.unique_identifier for s in sensors_qs}
                invalid = set(u_ids) - found_u_ids
                response_details["invalid_u_ids"] = list(invalid)

                allowed_fields = {'sensor_label', 'sensor_description'}
            else:
                return Response(
                    {"error": "Either (batch_location + batch_id) or u_ids[] required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            sensors = list(sensors_qs)
            if not sensors:
                return Response({"error": "No matching sensors found"}, status=status.HTTP_404_NOT_FOUND)

            # --- Step 1: Metadata updates ---
            if update_data:
                update_fields = {f: v for f, v in update_data.items() if f in allowed_fields}
                if update_fields and (batch_location and batch_id):
                    # Bulk update for batch mode
                    sensors_qs.update(**update_fields)
                    response_details["updated_items"] = len(sensors)
                elif update_fields and u_ids:
                    # Individual save for sensor mode
                    for sensor in sensors:
                        for f, v in update_fields.items():
                            setattr(sensor, f, v)
                        sensor.save(update_fields=list(update_fields.keys()))
                    response_details["updated_items"] = len(sensors)

            # --- Step 2: Add processes ---
            if new_process_data:
                created_count = 0
                for sensor in sensors:
                    for entry in new_process_data:
                        pid, desc, ts = entry.get("process_id"), entry.get("description"), entry.get("timestamp")
                        if not pid or not desc or not ts:
                            continue
                        ts = ensure_datetime(ts)
                        before = len(sensor.processes)
                        sensor.add_processes(pid, desc, ts)
                        if len(sensor.processes) > before:
                            created_count += 1
                response_details["created_processes"] = created_count

            # --- Step 3: Remove processes ---
            if delete_list:
                deleted_count = 0
                for sensor in sensors:
                    for entry in delete_list:
                        pid = entry.get("process_id")
                        if pid:
                            before = len(sensor.processes)
                            sensor.remove_process(pid)
                            if len(sensor.processes) < before:
                                deleted_count += 1
                response_details["deleted_processes"] = deleted_count

        response_details["performance_metrics"]["total_time"] = f"{time.time() - start_time:.3f}s"
        return Response(response_details, status=status.HTTP_200_OK)

    except Exception as e:
        traceback.print_exc()
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
# =============================================================================
# OPTIMIZED SL_WITH_PROCESSES FUNCTION (for CharField sensor_label)
# =============================================================================

@api_view(['PUT'])
def sl_with_processes_optimized(request):
    """
    Optimized sensor-level update for specific sensors by unique_identifier.
    Handles:
    - Updating sensor metadata (label, description)
    - Adding embedded processes
    - Deleting embedded processes
    """
    data = request.data
    u_ids = data.get('u_ids', [])
    new_process_data = data.get('new_process_data', [])
    delete_list = data.get('delete_list', [])
    update_data = data.get('updates', {})

    if not u_ids:
        return Response({'error': 'u_ids parameter required'}, status=status.HTTP_400_BAD_REQUEST)

    response_details = {
        "updated_items": 0,
        "created_items": 0,
        "deleted_items": 0,
        "invalid_u_ids": [],
        "performance_metrics": {}
    }

    try:
        start_time = time.time()

        with transaction.atomic():
            # Step 1: Fetch matching sensors
            sensors = list(Sensor.objects.filter(unique_identifier__in=u_ids))
            found_u_ids = {s.unique_identifier for s in sensors}
            invalid_u_ids = set(u_ids) - found_u_ids
            response_details['invalid_u_ids'] = list(invalid_u_ids)

            if not sensors:
                return Response({'error': 'No valid sensors found.'}, status=status.HTTP_404_NOT_FOUND)

            # Step 2: Update allowed sensor fields
            if update_data:
                allowed_fields = ['sensor_label', 'sensor_description']
                for sensor in sensors:
                    for field in allowed_fields:
                        if field in update_data:
                            setattr(sensor, field, update_data[field])

                    # ✅ Simplified label handling (no longer foreign key)
                    if 'label' in update_data:
                        # For backward compatibility, accept both 'label' and 'sensor_label'
                        sensor.sensor_label = update_data['label']

                    sensor.save()
                response_details["updated_items"] = len(sensors)

            # Step 3: Add new processes
            if new_process_data:
                created_count = 0
                for sensor in sensors:
                    for process_entry in new_process_data:
                        pid = process_entry.get("process_id")
                        desc = process_entry.get("description")
                        ts = process_entry.get("timestamp")
                        if not pid or not ts:
                            continue

                        ts = ensure_datetime(ts)
                        before_count = len(sensor.processes)
                        sensor.add_processes(pid, desc, ts)
                        after_count = len(sensor.processes)
                        if after_count > before_count:
                            created_count += 1

                response_details["created_items"] = created_count

            # Step 4: Delete processes
            if delete_list:
                deleted_count = 0
                for sensor in sensors:
                    for process_entry in delete_list:
                        pid = process_entry.get("process_id")
                        if pid:
                            before_count = len(sensor.processes)
                            sensor.remove_process(pid)
                            after_count = len(sensor.processes)
                            if after_count < before_count:
                                deleted_count += 1

                response_details["deleted_items"] = deleted_count

        total_time = time.time() - start_time
        response_details["performance_metrics"]["total_time"] = f"{total_time:.3f}s"

        return Response(response_details, status=status.HTTP_200_OK)

    except Exception as e:
        traceback.print_exc()
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




@api_view(['GET'])
def search_sensors(request):
    """
    Optimized search function leveraging denormalized data model
    Key optimizations:
    1. Direct unique_identifier lookup (indexed field)
    2. Single query with selective prefetching using ImageGroup
    3. Caching for frequently accessed sensors
    4. Query optimization hints for MongoDB
    """
    try:
        identifier = request.query_params.get('identifier', None)
        
        if not identifier:
            return Response({'error': 'No identifier provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check cache first (Redis recommended for production)
        cache_key = f"sensor_search:{identifier}"
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info(f"Cache hit for sensor search: {identifier}")
            return Response(cached_result, status=status.HTTP_200_OK)
        
        # Optimized query using the denormalized model
        # Single query leveraging indexed unique_identifier
        sensor = Sensor.objects.select_related().filter(
            unique_identifier=identifier
        ).only(
            # Only fetch required fields to reduce memory usage
            'batch_location', 'batch_id', 'total_wafers', 'batch_label', 'batch_description',
            'wafer_id', 'wafer_label', 'total_sensors', 'wafer_description', 'wafer_design_id',
            'sensor_id', 'sensor_label', 'sensor_description',
            'processes', 'process_ids', 'last_process_timestamp', 'process_count',
            'unique_identifier'
        ).first()
        
        if not sensor:
            return Response({'error': 'Sensor not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Use ImageGroup for optimized image data retrieval instead of individual Image queries
        # This is much faster than prefetch_related('images')
        image_groups = ImageGroup.objects.filter(
            sensor_unique_id=identifier
        ).only('process_id', 'images_data', 'image_count', 'last_updated')
        
        # Build response using denormalized data
        response_data = {
            'sensor_info': {
                'unique_identifier': sensor.unique_identifier,
                'batch_location': sensor.batch_location,
                'batch_id': sensor.batch_id,
                'total_wafers': sensor.total_wafers,
                'batch_label': sensor.batch_label,
                'batch_description': sensor.batch_description,
                'wafer_id': sensor.wafer_id,
                'wafer_label': sensor.wafer_label,
                'total_sensors': sensor.total_sensors,
                'wafer_description': sensor.wafer_description,
                'wafer_design_id': sensor.wafer_design_id,
                'sensor_id': sensor.sensor_id,
                'sensor_label': sensor.sensor_label,
                'sensor_description': sensor.sensor_description,
            },
            'process_summary': {
                'total_processes': sensor.process_count,
                'last_process_timestamp': sensor.last_process_timestamp,
                'process_ids': sensor.process_ids,
                'processes': sensor.processes  # Full embedded process data
            },
            'images_by_process': {}
        }
        
        # Organize images by process using pre-computed ImageGroup data
        for group in image_groups:
            response_data['images_by_process'][group.process_id or 'Unspecified'] = {
                'count': group.image_count,
                'images': group.images_data,
                'last_updated': group.last_updated
            }
        
        # Cache the result for 15 minutes (adjust based on data update frequency)
        cache.set(cache_key, response_data, timeout=900)
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error in search_sensors for identifier {identifier}: {str(e)}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def autocomplete_search(request):
    """
    Optimized autocomplete with aggressive caching and compound index usage
    Key optimizations:
    1. Leverages compound indexes: (batch_location, batch_id) and (batch_location, process_count)
    2. Uses unique_identifier field directly instead of computing it
    3. Implements multi-level caching strategy
    4. Limits result set early in the database
    5. Uses MongoDB's native aggregation for better performance
    """
    try:
        query = request.query_params.get('query', '').strip()
        
        if not query:
            return Response({'error': 'No search query provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Multi-level caching strategy
        cache_key = f"autocomplete:{query}"
        cached_suggestions = cache.get(cache_key)
        if cached_suggestions:
            return Response({'suggestions': cached_suggestions}, status=status.HTTP_200_OK)
        
        # Parse query components
        if len(query) < 1:
            return Response({'suggestions': []}, status=status.HTTP_200_OK)
            
        batch_location = query[0].upper()  # Normalize case
        
        # Build filter progressively based on query length
        filters = Q(batch_location__iexact=batch_location)
        
        # Batch ID filtering (positions 1-3)
        if len(query) >= 4:
            try:
                batch_id = int(query[1:4])
                filters &= Q(batch_id=batch_id)
            except (ValueError, IndexError):
                # If batch_id parsing fails, still try to match batch_location
                pass
        
        # Wafer ID filtering (positions 5-6 after dash)
        if len(query) >= 7 and query[4] == '-':
            try:
                wafer_id = int(query[5:7])
                filters &= Q(wafer_id=wafer_id)
            except (ValueError, IndexError):
                pass
        
        # Sensor ID filtering (positions 8-10 after second dash)
        if len(query) >= 11 and query[7] == '-':
            try:
                sensor_id = int(query[8:11])
                filters &= Q(sensor_id=sensor_id)
            except (ValueError, IndexError):
                pass
        
        # Optimized query using compound indexes and limiting results at database level
        # Order by process_count DESC to prioritize sensors with more activity
        sensors = Sensor.objects.filter(filters).only(
            'unique_identifier'
        ).order_by(
            '-process_count',  # Sensors with more processes first (uses index)
            'batch_id', 
            'wafer_id', 
            'sensor_id'
        )[:15]  # Limit in database, not Python
        
        # Extract unique identifiers directly (no computation needed)
        suggestions = [sensor.unique_identifier for sensor in sensors if sensor.unique_identifier]
        
        # Cache results with different TTLs based on query specificity
        if len(query) <= 4:
            # Short queries change more frequently, shorter cache
            cache_timeout = 300  # 5 minutes
        else:
            # Specific queries are more stable, longer cache
            cache_timeout = 1800  # 30 minutes
            
        cache.set(cache_key, suggestions, timeout=cache_timeout)
        
        return Response({'suggestions': suggestions[:10]}, status=status.HTTP_200_OK)  # Limit response
        
    except Exception as e:
        logger.error(f"Error in autocomplete_search for query '{query}': {str(e)}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def batch_sensors_summary(request):
    """
    Additional optimized endpoint for batch-level queries
    Leverages denormalized process metadata for fast aggregations
    """
    try:
        batch_location = request.query_params.get('batch_location')
        batch_id = request.query_params.get('batch_id')
        
        if not batch_location or not batch_id:
            return Response({'error': 'batch_location and batch_id required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            batch_id = int(batch_id)
        except ValueError:
            return Response({'error': 'Invalid batch_id'}, status=status.HTTP_400_BAD_REQUEST)
        
        cache_key = f"batch_summary:{batch_location}:{batch_id}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return Response(cached_result, status=status.HTTP_200_OK)
        
        # Use MongoDB aggregation through Django ORM
        # This leverages the compound index (batch_location, batch_id)
        sensors = Sensor.objects.filter(
            batch_location__iexact=batch_location,
            batch_id=batch_id
        ).only(
            'unique_identifier', 'wafer_id', 'sensor_id', 
            'process_count', 'last_process_timestamp'
        ).order_by('wafer_id', 'sensor_id')
        
        # Build summary using denormalized data
        summary = {
            'batch_info': {
                'location': batch_location,
                'batch_id': batch_id,
                'total_sensors': sensors.count()
            },
            'sensors': []
        }
        
        for sensor in sensors:
            summary['sensors'].append({
                'unique_identifier': sensor.unique_identifier,
                'wafer_id': sensor.wafer_id,
                'sensor_id': sensor.sensor_id,
                'process_count': sensor.process_count,
                'last_process_timestamp': sensor.last_process_timestamp
            })
        
        # Cache batch summaries for longer periods (they change less frequently)
        cache.set(cache_key, summary, timeout=3600)  # 1 hour
        
        return Response(summary, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error in batch_sensors_summary: {str(e)}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Additional helper function for cache warming
def warm_autocomplete_cache():
    """
    Background task function to pre-populate autocomplete cache
    Run this periodically to improve response times
    """
    from django.db.models import Count
    
    # Get most common batch prefixes
    common_prefixes = Sensor.objects.values('batch_location').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    for prefix_data in common_prefixes:
        batch_location = prefix_data['batch_location']
        # Pre-cache common prefixes
        cache_key = f"autocomplete:{batch_location}"
        if not cache.get(cache_key):
            # Simulate autocomplete request for this prefix
            sensors = Sensor.objects.filter(
                batch_location__iexact=batch_location
            ).only('unique_identifier').order_by('-process_count')[:15]
            
            suggestions = [s.unique_identifier for s in sensors if s.unique_identifier]
            cache.set(cache_key, suggestions, timeout=1800)
            
            
'''
This function enables dynamic query of the database using query parameters from the request. The function is designed to retrieve a paginated
list of Sensor objects filtered by various query parameters. it allows users to filter based on attributes like b_l, b_id, w_id, s_id, and p_id.
The expected behavior includes validating the query parameters, applying filtersm ordering results, and serializing the data for the response. 
'''
@api_view(['GET'])
def sensors(request):
    filter_serializer = SensorFilterSerializer(data=request.query_params)
    if not filter_serializer.is_valid():
        return Response({'error': 'Invalid query parameters', 'details': filter_serializer.errors})
    
    filter_params = {key: value for key, value in filter_serializer.validated_data.items()}
    process_id = filter_params.pop('process_id', None)       
    
'''
This function enables dynamic query of the database using query parameters from the request. The function is designed to retrieve a paginated
list of Sensor objects filtered by various query parameters. it allows users to filter based on attributes like b_l, b_id, w_id, s_id, and p_id.
The expected behavior includes validating the query parameters, applying filtersm ordering results, and serializing the data for the response. 
'''
@api_view(['GET'])
def sensors(request):
    filter_serializer = SensorFilterSerializer(data=request.query_params)
    if not filter_serializer.is_valid():
        return Response({'error': 'Invalid query parameters', 'details': filter_serializer.errors})
    
    filter_params = {key: value for key, value in filter_serializer.validated_data.items()}
    process_id = filter_params.pop('process_id', None)       
    
    # --- Handle sensor_id alias for unique_identifier ---
    if 'sensor_id' in filter_params and 'unique_identifier' not in filter_params:
        sensor_id_value = filter_params.pop('sensor_id')
        
        # --- Support comma-separated sensor IDs ---
        if isinstance(sensor_id_value, str) and ',' in sensor_id_value:
            sensor_id_list = [sid.strip() for sid in sensor_id_value.split(',') if sid.strip()]
            filter_params['unique_identifier__in'] = sensor_id_list
        else:
            filter_params['unique_identifier'] = sensor_id_value
    
    try:
        sensors = Sensor.objects.all()
        
        if filter_params and process_id:
            sensors = sensors.filter(**filter_params, process_ids__contains=[process_id])
        elif filter_params:
            sensors = sensors.filter(**filter_params)
        elif process_id:
            sensors = sensors.filter(process_ids__contains=[process_id])
            
        sensors = sensors.order_by('id')
        
        paginator = BatchPaginator()
        paginated_data = paginator.paginate_queryset(sensors, request)
        serializer = SensorSerializer(paginated_data, many=True)
        
        return paginator.get_paginated_response(serializer.data)
    except Exception as e:
        return Response({'error': 'Internal server error', 'details': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    
@api_view(['GET'])
def sensors_2(request):
    filter_serializer = SensorFilterSerializer(data=request.query_params)
    if not filter_serializer.is_valid():
        return Response({'error': 'Invalid query parameters', 'details': filter_serializer.errors})
    
    filter_params = {}
    validated_data = filter_serializer.validated_data
    
    # Handle batch_id - can be a list
    batch_id_value = validated_data.pop('batch_id', None)
    if batch_id_value:
        if isinstance(batch_id_value, list):
            filter_params['batch_id__in'] = batch_id_value
        else:
            filter_params['batch_id'] = batch_id_value
    
    # Handle wafer_id - can be a list
    wafer_id_value = validated_data.pop('wafer_id', None)
    if wafer_id_value:
        if isinstance(wafer_id_value, list):
            filter_params['wafer_id__in'] = wafer_id_value
        else:
            filter_params['wafer_id'] = wafer_id_value
    
    # Handle process_id separately
    process_id = validated_data.pop('process_id', None)
    
    # Handle u_id alias for unique_identifier
    if 'u_id' in validated_data:
        u_id_value = validated_data.pop('unique_identifier')
        
        # Support comma-separated sensor IDs
        if isinstance(u_id_value, str) and ',' in u_id_value:
            u_id_list = [uid.strip() for uid in u_id_value.split(',') if uid.strip()]
            filter_params['unique_identifier__in'] = u_id_list
        else:
            filter_params['unique_identifier'] = u_id_value
    
    # Add remaining filter params
    filter_params.update(validated_data)
    
    try:
        sensors = Sensor.objects.all()
        
        if filter_params and process_id:
            sensors = sensors.filter(**filter_params, process_ids__contains=[process_id])
        elif filter_params:
            sensors = sensors.filter(**filter_params)
        elif process_id:
            sensors = sensors.filter(process_ids__contains=[process_id])
            
        sensors = sensors.order_by('id')
        
        paginator = BatchPaginator()
        paginated_data = paginator.paginate_queryset(sensors, request)
        serializer = SensorSerializer(paginated_data, many=True)
        
        return paginator.get_paginated_response(serializer.data)
    except Exception as e:
        logger.error(f"Error retrieving sensors: {str(e)}")
        return Response({'error': 'Internal server error', 'details': str(e)}, 
                       status=status.HTTP_500_INTERNAL_SERVER_ERROR)

