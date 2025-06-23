from django.shortcuts import render
from rest_framework.decorators import api_view
from .models import Sensor, Image, SensorProcessRelation, SensorLabel
from process_encoder.models import ProcessFile
from .serializer import ImageSerializer, TestSensorSerializer, BatchSerializer, SensorSerializer, SearchFuncSerializer, DetailSerializer, SensorFilterSerializer, SensorProcessRelationSerializer, SensorLabelSerializer, SLSerializer, UIDSerializer
from datetime import datetime, timezone
from django.db import transaction
from django.db.utils import IntegrityError
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.db.models import Prefetch
import logging
logger = logging.getLogger(__name__)



@api_view(['POST'])
def bulk_create_2(request):
    try:
        batch_data = request.data
        print(f"Batch Data: {batch_data}")
        sensors = []
        process_file_map = {}

        batch_location = batch_data.get('batch_location')
        batch_id = batch_data.get('batch_id')
        batch_label = batch_data.get('batch_label', '')
        batch_description = batch_data.get('batch_description', '')

        total_wafers = int(batch_data['total_wafers'])
        total_sensors = int(batch_data['total_sensors'])
        print(f"Wafers and Sensors: {total_wafers}, {total_sensors}")

        with transaction.atomic():
            for i_w in range(total_wafers):
                wafer_id = i_w + 1
                wafer_label = batch_data.get('wafer_label', '')
                wafer_description = batch_data.get('wafer_description', '')
                wafer_design_id = batch_data.get('wafer_design_id', '')
                wafer_build_time = batch_data.get('wafer_build_time', '')

                sensor_processes = batch_data.get('sensor_processes', [])

                for i_s in range(total_sensors):
                    sensor_id = i_s + 1
                    sensor_label = batch_data.get('sensor_label', '')
                    sensor_description = batch_data.get('sensor_description', '')

                    sensor = Sensor(
                        batch_location=batch_location,
                        batch_id=batch_id,
                        batch_label=batch_label,
                        batch_description=batch_description,
                        total_wafers=total_wafers,
                        total_sensors=total_sensors,
                        wafer_id=wafer_id,
                        wafer_label=wafer_label,
                        wafer_description=wafer_description,
                        wafer_design_id=wafer_design_id,
                        #wafer_build_time=wafer_build_time,
                        sensor_id=sensor_id,
                        sensor_label=sensor_label,
                        sensor_description=sensor_description,
                    )
                    sensors.append(sensor)

                    # Store ManyToMany relations with timestamps using the unique identifier
                    unique_identifier = sensor.get_unique_identifier()
                    process_file_map[unique_identifier] = sensor_processes

            # Bulk insert all Electrode objects at once
            Sensor.objects.bulk_create(sensors, batch_size=1000)

            # Retrieve saved electrodes with their primary keys
            saved_sensors = Sensor.objects.filter(
                batch_location=batch_location, batch_id=batch_id
            ).filter(sensor_id__lte=total_sensors)

            # Prepare WaferProcessRelation entries
            sensor_process_relations = []
            for sensor in saved_sensors:
                unique_identifier = sensor.get_unique_identifier()
                sensor_processes = process_file_map.get(unique_identifier, [])
                

                for process_data in sensor_processes:
                    process_id = process_data.get('process_id')
                    timestamp = process_data.get('timestamp')
                    #unique_identifier = electrode.get_unique_identifier()

                    if timestamp:
                        timestamp = timestamp.rstrip('Z')
                        timestamp = datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc)
                        
                    print('unique_identifier:', unique_identifier)

                    process_file = ProcessFile.objects.get(process_id=process_id)

                    sensor_process_relations.append(
                        SensorProcessRelation(
                            sensor=sensor,
                            process_file=process_file,
                            timestamp=timestamp,
                            unique_identifier=unique_identifier  # Include unique identifier
                        )
                    )

            # Bulk insert all WaferProcessRelation entries
            SensorProcessRelation.objects.bulk_create(sensor_process_relations, batch_size=1000)

            return Response({'message': 'Sensor objects created with processes and timestamps'}, status=status.HTTP_201_CREATED)

    except ProcessFile.DoesNotExist:
        return Response({'error': 'One or more process files not found'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
 
 
 

@api_view(['POST'])
def bulk_create_(request):
    try:
        batch_data = request.data
        sensors = []
        process_file_map = {}

        batch_location = batch_data.get('batch_location')
        batch_id = batch_data.get('batch_id')
        batch_label = batch_data.get('batch_label', '')
        batch_description = batch_data.get('batch_description', '')

        total_wafers = int(batch_data['total_wafers'])
        total_sensors = int(batch_data['total_sensors'])

        with transaction.atomic():
            for i_w in range(total_wafers):
                wafer_id = i_w + 1
                wafer_label = batch_data.get('wafer_label', '')
                wafer_description = batch_data.get('wafer_description', '')
                wafer_design_id = batch_data.get('wafer_design_id', '')

                sensor_processes = batch_data.get('sensor_processes', [])

                for i_s in range(total_sensors):
                    sensor_id = i_s + 1
                    sensor_label = batch_data.get('sensor_label', '')
                    sensor_description = batch_data.get('sensor_description', '')

                    sensor = Sensor(
                        batch_location=batch_location,
                        batch_id=batch_id,
                        batch_label=batch_label,
                        batch_description=batch_description,
                        total_wafers=total_wafers,
                        total_sensors=total_sensors,
                        wafer_id=wafer_id,
                        wafer_label=wafer_label,
                        wafer_description=wafer_description,
                        wafer_design_id=wafer_design_id,
                        sensor_id=sensor_id,
                        sensor_label=sensor_label,
                        sensor_description=sensor_description,
                    )
                    sensors.append(sensor)

                    unique_identifier = sensor.get_unique_identifier()
                    process_file_map[unique_identifier] = sensor_processes

            # Bulk insert all Sensor objects at once
            Sensor.objects.bulk_create(sensors, batch_size=1000)

            # Efficiently retrieve saved sensors using batch identifiers
            saved_sensors = list(
                Sensor.objects.filter(
                    batch_location=batch_location, batch_id=batch_id
                )
            )

            # Prepare SensorProcessRelation entries
            sensor_process_relations = []
            sensor_lookup = {sensor.get_unique_identifier(): sensor for sensor in saved_sensors}

            for unique_identifier, sensor_processes in process_file_map.items():
                sensor = sensor_lookup.get(unique_identifier)
                if not sensor:
                    continue

                for process_data in sensor_processes:
                    process_id = process_data.get('process_id')
                    timestamp = process_data.get('timestamp')

                    if timestamp:
                        timestamp = timestamp.rstrip('Z')
                        timestamp = datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc)

                    process_file = ProcessFile.objects.get(process_id=process_id)

                    sensor_process_relations.append(
                        SensorProcessRelation(
                            sensor=sensor,
                            process_file=process_file,
                            timestamp=timestamp,
                            unique_identifier=unique_identifier  # Include unique identifier
                        )
                    )

            # Bulk insert all SensorProcessRelation entries
            SensorProcessRelation.objects.bulk_create(sensor_process_relations, batch_size=1000)

            return Response({'message': 'Sensor objects created with processes and timestamps'}, status=status.HTTP_201_CREATED)

    except ProcessFile.DoesNotExist:
        return Response({'error': 'One or more process files not found'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

 
 
 
 
#TODO: Used in testing and production
# Speed test 5 optimized for multi-reponses. THIS WORKS TOO
@api_view(['PUT'])
def update_sensors_4(request, batch_location, batch_id):
    # Extract data from the request
    data = request.data
    print("Received data:", data)
    
    wafer_ids = parse_range(str(data.get('wafer_ids', '')))
    sensor_ids = parse_range(str(data.get('sensor_ids', '')))
    new_process_data = data.get('new_process_data', [])
    delete_list = data.get('delete_list', [])
    update_data = data.get('updates', {})

    response_details = {
        "updated_items": 0,
        "created_items": 0,
        "deleted_items": 0
    }

    try:
        with transaction.atomic():  # Ensure atomicity
            # Step 1: Retrieve and filter electrodes
            sensors_qs = Sensor.objects.filter(batch_location=batch_location, batch_id=batch_id)
            if wafer_ids:
                sensors_qs = sensors_qs.filter(wafer_id__in=wafer_ids)
            if sensor_ids:
                sensors_qs = sensors_qs.filter(sensor_id__in=sensor_ids)

            sensors = list(sensors_qs)
            sensor_ids = [sensor.id for sensor in sensors]
            print(f"Number of electrodes to process: {len(sensors)}")

            # Step 2: Bulk Update Electrode Instances
            if update_data:
                print(f"Applying updates to electrodes: {update_data}")
                update_fields = {field: value for field, value in update_data.items() if hasattr(Sensor, field)}
                if update_fields:
                    sensors_qs.update(**update_fields)
                    response_details["updated_items"] = len(sensor_ids)

            # Step 3: Bulk Create WaferProcessRelation Entries
            sensor_process_relations = []
            for process_entry in new_process_data:
                process_id = process_entry.get('process_id')
                timestamp = process_entry.get('timestamp')

                # Validate input fields
                if not process_id or not timestamp:
                    raise ValueError("Each process entry must include both process_id and timestamp.")
                if not ProcessFile.objects.filter(process_id=process_id).exists():
                    raise ValueError(f"Invalid process_id: {process_id} does not exist.")

                # Create WaferProcessRelation entries
                for sensor in sensors:
                    sensor_process_relations.append(
                        SensorProcessRelation(
                            process_file_id=process_id,
                            sensor=sensor,
                            timestamp=timestamp,
                            unique_identifier=sensor.get_unique_identifier()
                        )
                    )

            if sensor_process_relations:
                try:
                    SensorProcessRelation.objects.bulk_create(
                        sensor_process_relations, ignore_conflicts=True
                    )
                    response_details["created_items"] = len(sensor_process_relations)
                except Exception as e:
                    print(f"Error during bulk_create: {e}")
                    raise
            elif not sensor_process_relations:
                print("No valid sensor-process relations to insert.")

            # Step 4: Handle Deletions
            if delete_list:
                valid_processes = [
                    (process.get('process_id').strip(), process.get('timestamp').strip())
                    for process in delete_list if process.get('process_id') and process.get('timestamp')
                ]
                if valid_processes:
                    filters = Q(sensor_id__in=sensor_ids)
                    for process_id, timestamp in valid_processes:
                        filters &= Q(process_file_id=process_id, timestamp=timestamp)

                    deleted_count, _ = SensorProcessRelation.objects.filter(filters).delete()
                    response_details["deleted_items"] = deleted_count

        # Step 5: Return a Consolidated Response
        return Response(response_details, status=status.HTTP_200_OK)

    except ValueError as ve:
        print(f"Validation error: {ve}")
        return Response({'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        print(f"Error in processing request: {e}")
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)




@api_view(['GET'])
def bulk_electrode_view(request):
    sensors = Sensor.objects.all().prefetch_related('wafer_process_relations', 'images')
    serializer = BatchSerializer(sensors, many=True)
    return Response(serializer.data)
    
    
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
    return list(Sensor.objects.values_list('wafer_id', flat=True).distinct())

def get_all_sensor_ids():
    return list(Sensor.objects.values_list('sensor_id', flat=True).distinct())

    
class BatchPaginator(PageNumberPagination):
    page_size = 150 # Default page size
    page_size_query_param = 'page_size'
    max_page_size = 300
    
# get_sensors
@api_view(['GET'])
def sensors(request):
    try:
        batch_location = request.query_params.get('batch_location', None)
        batch_id = request.query_params.get('batch_id', None)    
        wafer_id = request.query_params.get('wafer_id', None)
        sensor_id = request.query_params.get('sensor_id', None)
        
        filter_params = {}
        
        if batch_location:
            filter_params['batch_location'] = batch_location
        if batch_id:
            filter_params['batch_id'] = batch_id
        if wafer_id:
            filter_params['wafer_id'] = wafer_id
        if sensor_id:
            filter_params['sensor_id'] = sensor_id
        
        sensors = Sensor.objects.filter(**filter_params).prefetch_related('sensor_process_relations')
        paginator = BatchPaginator()
        paginated_data = paginator.paginate_queryset(sensors, request)
        serializer = SensorSerializer(paginated_data, many=True)
        
        return paginator.get_paginated_response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    
''' Sensors 2: Optimizations to improve functionality and readiblity of the function above'''
@api_view(['GET'])
def sensors_2(request):
    filter_serializer = SensorFilterSerializer(data=request.query_params)
    if not filter_serializer.is_valid():
        return Response({'error': 'Invalid query parameters', 'details': filter_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    
    filter_params = {key: value for key, value in filter_serializer.validated_data.items()}
    
    try:
        # Fetch and paginate sensors
        sensors = (
            Sensor.objects.filter(**filter_params)
            .order_by('batch_location')
            .prefetch_related('sensor_process_relations')
        )
        paginator = BatchPaginator()
        paginated_data = paginator.paginate_queryset(sensors, request)
        serializer = SensorSerializer(paginated_data, many=True)
        
        return paginator.get_paginated_response(serializer.data)
    except Exception as e:
        return Response({'error': 'Internal server error', 'details': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
''' 
Sensor 3: Optimizations to enable inclusion of process_id in the query parameters. 
Currenty in use.
'''
@api_view(['GET']) 
def sensors_3(request):
    filter_serializer = SensorFilterSerializer(data=request.query_params)
    if not filter_serializer.is_valid():
        return Response({'error': 'Invalid query parameters', 'details': filter_serializer.errors})
    
    filter_params = {key: value for key, value in filter_serializer.validated_data.items()}
    process_id = filter_params.pop('process_id', None)        
    
    try:
        sensors = Sensor.objects.all()
        
        if filter_params:
            sensors = sensors.filter(**filter_params)
            
        if process_id:
            sensors = sensors.filter(process_relations__process_file__process_id=process_id)
            
        sensors = sensors.order_by('batch_location', 'batch_id').prefetch_related('sensor_process_relations')
        
        paginator = BatchPaginator()
        paginated_data = paginator.paginate_queryset(sensors, request)
        serializer = SensorSerializer(paginated_data, many=True)
        
        return paginator.get_paginated_response(serializer.data)
    except Exception as e:
        return Response({'error': 'Internal server error', 'details': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
'''
Sensors 4: Optimized function that returns Response in a nested format, where the response is grouped by b_l and b_id, 
and the u_ids are returned for the senors that match query parameters.
'''

@api_view(['GET'])
def sensors_4(request):
    filter_serializer = SensorFilterSerializer(data=request.query_params)
    if not filter_serializer.is_valid():
        return Response({'error': 'Invalid query parameters', 'details': filter_serializer.errors})
    
    filter_params = {key: value for key, value in filter_serializer.validated_data.items()}
    process_id = filter_params.pop('process_id', None)
    
    try:
        sensors = Sensor.objects.all()
        
        if filter_params and process_id:
            sensors = Sensor.objects.filter(**filter_params, process_relations__process_file__process_id=process_id)
        elif filter_params:
            sensors = Sensor.objects.filter(**filter_params)
        elif process_id:
            sensors = Sensor.objects.filter(process_relations__process_file__process_id=process_id)
            
        sensors = sensors.order_by('batch_id').prefetch_related('sensor_process_relations')    
                
        paginator = BatchPaginator()
        paginated_data = paginator.paginate_queryset(sensors, request)
        serializer = SensorSerializer(paginated_data, many=True)
        
        return paginator.get_paginated_response(serializer.data)
    
    except Exception as e:
        return Response({'error': 'Internal server error', 'details': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['GET'])
def sensor_processes(request):
    try:
        processes = SensorProcessRelation.objects.select_related('process_file').all()
        serialzer = SensorProcessRelationSerializer(processes, many=True)
        return Response(serialzer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['GET'])
def s_p(request):
    try:
        sensors = Sensor.objects.all()
        serializer = SensorSerializer(sensors, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': 'Internal server error', 'details': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

    
    
@api_view(['GET'])
def get_batches(request):
    try:
        # Initial queryset
        sensors = Sensor.objects.all()
        
        # Get query params
        batch_location = request.query_params.get('batch_location', None)
        batch_id = request.query_params.get('batch_id', None)
        
        # Filtering parameters
        if batch_location:
            sensors = sensors.filter(batch_location=batch_location)
        
        if batch_id:
            batch_id_list = parse_range(batch_id)
            sensors = sensors.filter(batch_id__in=batch_id_list)
                       
        unique_batches = sensors.values('batch_location', 'batch_id', 'total_wafers', 'total_sensors', 'batch_label', 'batch_description').distinct().order_by('batch_id')
        print("Unique Batches", unique_batches)
        
        batch_data = list(unique_batches)
        
        for batch in batch_data:
            related_sensors = sensors.filter(
                batch_location=batch['batch_location'],
                batch_id=batch['batch_id']
            ).prefetch_related('sensor_process_relations')
            
            sensor_process_list = list(
                related_sensors.values_list('sensor_process_relations__process_id', flat=True).distinct()
            )
            
            batch['sensor_processes'] = sensor_process_list
        
        print('\nBatch Data:', batch_data)
        # Pagination
        paginator = BatchPaginator()
        paginated_data = paginator.paginate_queryset(batch_data, request)
        #serializer = BatchesSerializer(paginated_data, many=True)
        
        return paginator.get_paginated_response(paginated_data)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
from django.db.models import Prefetch
from collections import defaultdict

@api_view(['GET'])
def get_batches_2(request):
    try:
        # Initial queryset
        sensors = Sensor.objects.all()
        
        # Get query params
        batch_location = request.query_params.get('batch_location', None)
        batch_id = request.query_params.get('batch_id', None)
        
        # Filtering parameters
        if batch_location:
            sensors = sensors.filter(batch_location=batch_location)
        
        if batch_id:
            batch_id_list = parse_range(batch_id)
            sensors = sensors.filter(batch_id__in=batch_id_list)
                       
        unique_batches = sensors.values('batch_location', 'batch_id', 'total_wafers', 'total_sensors', 'batch_label', 'batch_description').distinct().order_by('batch_id')
        print("Unique Batches", unique_batches)
        
        batch_data = list(unique_batches)
        
        for batch in batch_data:
            related_sensors = sensors.filter(
                batch_location=batch['batch_location'],
                batch_id=batch['batch_id']
            ).prefetch_related('sensor_process_relations')
            
            sensor_process_list = list(
                related_sensors.values(
                    'sensor_process_relations__process_id',
                    'sensor_process_relations__description',
                ).distinct()
            )
            
            batch['sensor_processes'] = sensor_process_list
        
        print('\nBatch Data:', batch_data)
        # Pagination
        paginator = BatchPaginator()
        paginated_data = paginator.paginate_queryset(batch_data, request)
        #serializer = BatchesSerializer(paginated_data, many=True)
        
        return paginator.get_paginated_response(paginated_data)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    
    
@api_view(['GET'])
def get_batches_3_with_processes(request):
    try:
        # Get query params
        batch_location = request.query_params.get('batch_location', None)
        batch_id = request.query_params.get('batch_id', None)

        filters = {}
        if batch_location:
            filters['batch_location'] = batch_location
        if batch_id:
            filters['batch_id__in'] = parse_range(batch_id)

        # Get unique batch combinations
        unique_batches = Sensor.objects.filter(**filters).values(
            'batch_location', 'batch_id', 'total_wafers', 'total_sensors', 'batch_label', 'batch_description'
        ).distinct().order_by('batch_id')

        batch_data = list(unique_batches)

        # Prefetch related process files efficiently
        sensor_queryset = Sensor.objects.filter(**filters).prefetch_related(
            Prefetch('sensor_process_relations', to_attr='prefetched_processes')
        )

        sensor_dict = {}
        for sensor in sensor_queryset:
            key = (sensor.batch_location, sensor.batch_id)
            if key not in sensor_dict:
                sensor_dict[key] = set()
            sensor_dict[key].update([rel.process_id for rel in sensor.prefetched_processes])

        for batch in batch_data:
            key = (batch['batch_location'], batch['batch_id'])
            batch['sensor_processes'] = list(sensor_dict.get(key, []))

        return Response({'count': len(batch_data), 'results': batch_data}, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
def get_batches_4(request, batch_location=None, batch_id=None):
    try:
        # Base queryset
        sensor_queryset = Sensor.objects.all()
        
        # Apply filters if provided
        if batch_location:
            sensor_queryset = sensor_queryset.filter(batch_location=batch_location)
        
        if batch_id:
            sensor_queryset = sensor_queryset.filter(batch_id=batch_id)

        # Fetch related process data
        sensor_queryset = sensor_queryset.prefetch_related(
            Prefetch(
                'process_relations',  # Reverse relation from SensorProcessRelation to Sensor
                queryset=SensorProcessRelation.objects.select_related('process_file').only(
                    'process_file_id', 'timestamp', 'unique_identifier'
                ),
                to_attr='prefetched_processes'
            )
        ).only(
            'batch_location', 'batch_id', 'batch_label', 'batch_description', 'total_wafers', 'total_sensors'
        )

        # If no data is found, return an appropriate response
        if not sensor_queryset.exists():
            return Response({'error': 'No matching batches found.'}, status=status.HTTP_404_NOT_FOUND)

        # Serialize queryset
        serializer = DetailSerializer(sensor_queryset, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    except Sensor.DoesNotExist:
        return Response({'error': 'Batch not found'}, status=status.HTTP_404_NOT_FOUND)
    
@api_view(['GET'])
def get_batches_5(request, batch_location=None, batch_id=None):
    try:
        # Base queryset with only required fields
        sensors = Sensor.objects.only(
            'batch_location', 'batch_id', 'batch_label', 
            'batch_description', 'total_wafers', 'total_sensors'
        )

        # Apply filters if provided
        if batch_location:
            sensors = sensors.filter(batch_location=batch_location)

        if batch_id:
            sensors = sensors.filter(batch_id=batch_id)

        # Use values() to optimize data retrieval
        batch_data = list(sensors.values(
            'batch_location', 'batch_id', 'batch_label', 'batch_description', 
            'total_wafers', 'total_sensors'
        ).distinct().order_by('batch_id'))

        if not batch_data:
            return Response({'error': 'No matching batches found.'}, status=status.HTTP_404_NOT_FOUND)

        # Get related SensorProcessRelation data efficiently
        process_relations = SensorProcessRelation.objects.filter(
            sensor__batch_location__in=[b['batch_location'] for b in batch_data],
            sensor__batch_id__in=[b['batch_id'] for b in batch_data]
        ).values(
            'sensor__batch_location', 'sensor__batch_id', 
            'process_file_id', 'timestamp', 'process_file__description'
        ).distinct().order_by('process_file_id')

        # Organize process data in a dictionary
        process_dict = {}
        for relation in process_relations:
            key = (relation['sensor__batch_location'], relation['sensor__batch_id'])
            if key not in process_dict:
                process_dict[key] = []
            process_dict[key].append({
                'process_id': relation['process_file_id'],
                'timestamp': relation['timestamp'],
                'description': relation['process_file__description']
            })

        # Attach related process data to batches
        for batch in batch_data:
            key = (batch['batch_location'], batch['batch_id'])
            batch['sensor_processes'] = process_dict.get(key, [])

        return Response({'count': len(batch_data), 'results': batch_data}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    
@api_view(['DELETE'])
def delete_batch(request, batch_location, batch_id):
    try:
        batch = Sensor.objects.filter(batch_location=batch_location, batch_id=batch_id)
        
        if not batch.exists():
            return Response({'error': 'Batch not found.'}, status=status.HTTP_404_NOT_FOUND)
        
        # Delete all filtered batches
        deleted_count, _ = batch.delete()
        
        return Response({'message': f'{deleted_count} items deleted successfully!'}, status=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        print(f"Error in delete_batch {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Comprehensive Search function
def parse_sensor_identifier(identifier):
    try:
        batch_location = identifier[0]
        batch_id = int(identifier[1:4])
        wafer_id = int(identifier[5:7])
        sensor_id = int(identifier[8:11])
        #electrode_id = int(identifier[12])

        return batch_location, batch_id, wafer_id, sensor_id   #, electrode_id
    except (IndexError, ValueError) as e:
        return ValueError(f"Invalid identifier format: {identifier}. Error: {str(e)}")
    
@api_view(['GET'])
def search_electrode(request):
    try:
        # Get the identifier from query parameters
        identifier = request.query_params.get('identifier', None)
        
        if not identifier:
            return Response({'error': 'No identifier provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Parse the identifuer into individual components
        batch_location, batch_id, wafer_id, sensor_id = parse_sensor_identifier(identifier)
        
        # Corresponding electrodes in the database
        sensor = Sensor.objects.filter(
            batch_location = batch_location,
            batch_id=batch_id, 
            wafer_id=wafer_id,
            sensor_id=sensor_id,
            #electrode_id=electrode_id
        ).prefetch_related('images', 'sensor_process_relations').first()
        
        if not sensor:
            return Response({'error': 'Electrode not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = SearchFuncSerializer(sensor)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

     
@api_view(['GET'])
def autocomplete_search(request):
    try:
        query = request.query_params.get('query', None)
        
        if not query:
            return Response({'error': 'No search query provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Extract batch_location and batch_id 
        batch_location = query[0]  
        batch_id_str = query[1:4] 
        
        try:
            batch_id = int(batch_id_str)  # Convert to integer to match the database
        except ValueError:
            return Response({'error': 'Invalid batch ID in query'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Fetch electrodes that match the batch_location and batch_id
        sensors = Sensor.objects.filter(
            Q(batch_location__iexact=batch_location) &  # Case-insensitive match for batch_location
            Q(batch_id=batch_id)  # Exact match for batch_id as it's an integer in the database
        )#[:10]
        
        # Additional filtering for wafer_id, sensor_id, and electrode_id if provided
        if len(query) >= 7:
            wafer_id_str = query[5:7]
            try:
                wafer_id = int(wafer_id_str)
                electrodes = electrodes.filter(wafer_id=wafer_id)
            except ValueError:
                pass
            
        if len(query) >= 11:
            sensor_id_str = query[8:11]
            try: 
                sensor_id = int(sensor_id_str)
                sensors = sensors.filter(sensor_id=sensor_id)
            except ValueError:
                pass
            
        #if len(query) >= 13:
         #   electrode_id_str = query[12]
          #  try:
           #     electrode_id= int(electrode_id_str)
            #    electrodes = electrodes.filter(electrode_id=electrode_id)
            #except ValueError:
             #   pass
        
        # Prepare the suggestions list using the get_unique_identifier method
        suggestions = [sensor.get_unique_identifier() for sensor in sensors[:10]]
        
        return Response({'suggestions': suggestions}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    
    
# Delete processes using identifier
@api_view(['DELETE'])
def delete_process_2(request, b_l, b_id):
    sensors = Sensor.objects.filter(batch_location=b_l, batch_id=b_id)
    delete_list = request.get('delete_list', [])
    
    ids = []
    
    for sensor in sensors:
        u_id = sensor.get_unique_identifier()
        ids.append(u_id)
        
    #to_be_deleted = []
    valid = SensorProcessRelation.objects.filter(
        process_file_id__in=delete_list,
        unique_identifer__in=ids
    )
    
    deleted_count, _ = valid.delete()
    print(f"Successfully deleted {deleted_count} SensorProcessRelation entries.")

    return Response({'message': f'{deleted_count} items deleted successfully!'}, status=status.HTTP_204_NO_CONTENT)    


@api_view(['DELETE'])
def delete_process_3(request, b_l, b_id):
    try:
        # Get the list of processes to delete
        delete_list = request.data.get('delete_list', [])
        print(f"Delete List: {delete_list}")
        if not delete_list:
            return Response({'error': 'delete_list is required and cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)

        # Get all sensors for the specified batch location and batch ID
        sensors = Sensor.objects.filter(batch_location=b_l, batch_id=b_id)
        print(f"Number of sensors to process {len(sensors)}")
        if not sensors.exists():
            return Response({'error': f'No electrodes found for batch_location={b_l} and batch_id={b_id}.'}, status=status.HTTP_404_NOT_FOUND)

        # Generate the list of unique identifiers for the sensors
        ids = [sensor.get_unique_identifier() for sensor in sensors]
        
        
        for process in delete_list:
            process_id = process.get('process_id')
            timestamp = process.get('timestamp')
        

            # Filter WaferProcessRelation objects for deletion
            for sensor in sensors:
                valid_relations = SensorProcessRelation.objects.filter(
                    process_file_id=process_id,  # Match process_file_id
                    timestamp=timestamp,
                    sensor=sensor,
                    unique_identifier__in=ids        # Match unique_identifier
                )

                # Check if there are valid relations to delete
                if not valid_relations.exists():
                    print(f'error: No matching WaferProcessRelation entries found for delete_list= {delete_list}.')
                    return Response({'error': f'No matching WaferProcessRelation entries found for delete_list={delete_list}.'}, status=status.HTTP_404_NOT_FOUND)

                # Perform the deletion
                deleted_count, _ = valid_relations.delete()
                print(f"Successfully deleted {deleted_count} WaferProcessRelation entries.")

                return Response({'message': f'{deleted_count} items deleted successfully!'}, status=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        print(f"Error during deletion: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    
@api_view(['DELETE'])
def delete_process_4(request, b_l, b_id):
    try:
        # Get the list of processes to delete
        delete_list = request.data.get('delete_list', [])
        print(f"Delete List: {delete_list}")
        if not delete_list:
            return Response({'error': 'delete_list is required and cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)

        # Get all sensors for the specified batch location and batch ID
        sensors = Sensor.objects.filter(batch_location=b_l, batch_id=b_id)
        print(f"Number of sensors to process: {sensors.count()}")
        if not sensors.exists():
            return Response({'error': f'No electrodes found for batch_location={b_l} and batch_id={b_id}.'}, status=status.HTTP_404_NOT_FOUND)

        # Generate the list of unique identifiers for the sensors
        ids = [sensor.get_unique_identifier() for sensor in sensors]

        # Track deleted count and unmatched items
        total_deleted = 0
        unmatched_items = []

        for process in delete_list:
            process_id = process.get('process_id')
            timestamp = process.get('timestamp')

            if not process_id or not timestamp:
                unmatched_items.append(process)
                continue  # Skip to next item if data is incomplete

            # Filter WaferProcessRelation objects for deletion
            valid_relations = SensorProcessRelation.objects.filter(
                process_file_id=process_id.strip(),  # Ensure clean string
                timestamp__exact=timestamp.strip(),
                unique_identifier__in=ids  # Match unique_identifier
            )

            # Check if there are valid relations to delete
            if not valid_relations.exists():
                unmatched_items.append({'process_id': process_id, 'timestamp': timestamp})
                continue  # Continue to next process in the list

            # Perform the deletion
            deleted_count, _ = valid_relations.delete()
            total_deleted += deleted_count
            print(f"Deleted {deleted_count} entries for process_id={process_id} and timestamp={timestamp}.")

        if unmatched_items:
            print(f"Unmatched items: {unmatched_items}")
            return Response(
                {
                    'error': f'Some items in delete_list were not found: {unmatched_items}',
                    'deleted_count': total_deleted
                },
                status=status.HTTP_207_MULTI_STATUS  # Partial success
            )

        return Response(
            {'message': f'{total_deleted} items deleted successfully!'},
            status=status.HTTP_204_NO_CONTENT
        )

    except Exception as e:
        print(f"Error during deletion: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

from django.db.models import Q

@api_view(['DELETE'])
def delete_process(request, b_l, b_id):
    try:
        # Get the list of processes to delete
        delete_list = request.data.get('delete_list', [])
        print(f"Delete List: {delete_list}")
        if not delete_list:
            return Response({'error': 'delete_list is required and cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)

        # Get all sensors for the specified batch location and batch ID
        sensors = Sensor.objects.filter(batch_location=b_l, batch_id=b_id)
        if not sensors.exists():
            return Response({'error': f'No electrodes found for batch_location={b_l} and batch_id={b_id}.'}, status=status.HTTP_404_NOT_FOUND)

        print(f"Number of sensors to process: {sensors.count()}")

        # Generate the list of unique identifiers dynamically
        ids = [sensor.get_unique_identifier() for sensor in sensors]

        # Prepare bulk filter query for WaferProcessRelation
        filters = [
            Q(process_file_id=process.get('process_id').strip(), timestamp=process.get('timestamp').strip(), unique_identifier__in=ids)
            for process in delete_list if process.get('process_id') and process.get('timestamp')
        ]

        if not filters:
            return Response({'error': 'No valid process_id and timestamp found in delete_list.'}, status=status.HTTP_400_BAD_REQUEST)

        # Combine all filters with OR to perform a single query
        query = filters.pop()
        for filter_query in filters:
            query |= filter_query

        # Execute the query and delete matching records
        valid_relations = SensorProcessRelation.objects.filter(query)
        total_deleted, _ = valid_relations.delete()

        # Cross-reference delete_list with the remaining WaferProcessRelation entries
        unmatched_items = [
            process for process in delete_list
            if not SensorProcessRelation.objects.filter(
                process_file_id=process.get('process_id').strip(),
                timestamp=process.get('timestamp').strip(),
                unique_identifier__in=ids
            ).exists()
        ]

        # Handle response
        if unmatched_items:
            print(f"Unmatched items: {unmatched_items}")
            return Response(
                {
                    'error': f'Some items in delete_list were not found: {unmatched_items}',
                    'deleted_count': total_deleted
                },
                status=status.HTTP_207_MULTI_STATUS  # Partial success
            )

        return Response(
            {'message': f'{total_deleted} items deleted successfully!'},
            status=status.HTTP_204_NO_CONTENT
        )

    except Exception as e:
        print(f"Error during deletion: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def electrodedetail(request, batch_location, batch_id):
    try:
        sensor = Sensor.objects.filter(batch_location=batch_location, batch_id=batch_id).prefetch_related('sensor_process_relations')
        serializer = DetailSerializer(sensor, many=True)

        serialized_data = serializer.data[0] if serializer.data else {}
        return Response(serialized_data)
    except Sensor.DoesNotExist:
        return Response({'error': 'Electrode not found'}, status=status.HTTP_404_NOT_FOUND)
    
@api_view(['GET'])
def batch_detail_2(request, batch_location, batch_id):
    try:
        sensor_process_queryset = SensorProcessRelation.objects.only('process_file', 'timestamp', 'unique_identifier')
        image_queryset = Image.objects.only('process_id', 'image')
        
        sensor = Sensor.objects.filter(batch_location=batch_location, batch_id=batch_id).prefetch_related(
            Prefetch('process_relations', queryset=sensor_process_queryset),
            Prefetch('images', queryset=image_queryset)
        )
        
        serializer = DetailSerializer(sensor, many=True)
        serialized_data = serializer.data[0] if serializer.data else {}
        return Response(serialized_data)
    except Sensor.DoesNotExist:
        return Response({'error': 'Electrode not found'}, status=status.HTTP_404_NOT_FOUND)
    

@api_view(['GET'])
def batch_detail_3(request, batch_location, batch_id):
    try:
        # Use only required fields in the query to reduce data retrieval load
        sensor_queryset = (Sensor.objects.filter(batch_location=batch_location, batch_id=batch_id)
            .select_related()  # Prefetch related fields efficiently
            .prefetch_related(
                Prefetch(
                    'process_relations', 
                    queryset=SensorProcessRelation.objects.select_related('process_file').only('process_file_id', 'timestamp', 'unique_identifier')
                ),
            )
        )
        
        # Serialize the data
        serializer = DetailSerializer(sensor_queryset, many=True)

        # Return data (return only the first object if required, as per the original logic)
        serialized_data = serializer.data[0] if serializer.data else {}
        return Response(serialized_data)
    except Sensor.DoesNotExist:
        return Response({'error': 'Electrode not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
def batch_detail_4(request, batch_location, batch_id):
    try:
        # Fetch only the first matching document
        sensor = (Sensor.objects.filter(batch_location=batch_location, batch_id=batch_id)
            .select_related()  # Efficiently prefetch related fields
            .prefetch_related(
                Prefetch(
                    'process_relations', 
                    queryset=SensorProcessRelation.objects.select_related('process_file').only('process_file_id', 'timestamp', 'unique_identifier')
                ),
            )
            .only('batch_location', 'batch_id', 'batch_label', 'batch_description', 'total_wafers', 'total_sensors')
            .first()  # Get the first document
        )
        
        if not sensor:
            return Response({'error': 'Sensor not found'}, status=status.HTTP_404_NOT_FOUND)

        # Serialize the single object
        serializer = DetailSerializer(sensor)

        return Response(serializer.data)
    except Sensor.DoesNotExist:
        return Response({'error': 'Sensor not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
def get_batches(request):
    try:
        # Initial queryset
        sensors = Sensor.objects.all()
        
        # Get query params
        batch_location = request.query_params.get('batch_location', None)
        batch_id = request.query_params.get('batch_id', None)
        
        # Filtering parameters
        if batch_location:
            sensors = sensors.filter(batch_location=batch_location)
        
        if batch_id:
            batch_id_list = parse_range(batch_id)
            sensors = sensors.filter(batch_id__in=batch_id_list)
                       
        unique_batches = sensors.values('batch_location', 'batch_id', 'total_wafers', 'total_sensors', 'batch_label', 'batch_description').distinct().order_by('batch_id')
        print("Unique Batches", unique_batches)
        
        batch_data = list(unique_batches)
        
        for batch in batch_data:
            related_sensors = sensors.filter(
                batch_location=batch['batch_location'],
                batch_id=batch['batch_id']
            ).prefetch_related('sensor_process_relations')
            
            wafer_process_list = list(
                related_sensors.values_list('sensor_process_relations__process_id', flat=True).distinct()
            )
            
            batch['sensor_processes'] = wafer_process_list
        
        print('\nBatch Data:', batch_data)
        # Pagination
        paginator = BatchPaginator()
        paginated_data = paginator.paginate_queryset(batch_data, request)
        #serializer = BatchesSerializer(paginated_data, many=True)
        
        return paginator.get_paginated_response(paginated_data)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['GET'])
def electrode_dropdown(request):
    sensors = Sensor.objects.all()
    serializer = UIDSerializer(sensors, many=True)
    return Response(serializer.data)


@api_view(['POST'])
def upload_image(request):
    electrode_identifiers = request.data.getlist('electrode_identifier')
    process_id = request.data.get('process_id')
    image_files = request.FILES.getlist('image_files')
    
    if len(image_files) != len(electrode_identifiers):
        return Response({'error': 'Mismatch between the number of images and electrode identifiers'}, status=status.HTTP_400_BAD_REQUEST)

    try:        
        for i, image_file in enumerate(image_files):
            electrode_identifier = electrode_identifiers[i]
        
            sensor = Sensor.objects.filter(
                batch_location=electrode_identifier[:1],
                batch_id=int(electrode_identifier[1:4]),
                wafer_id=int(electrode_identifier[5:7]),
                sensor_id=int(electrode_identifier[8:11]),
                #electrode_id=int(electrode_identifier[12])
            ).first()
            
            if not sensor:
                return Response({'error': 'Electrode not found.'}, status=status.HTTP_404_NOT_FOUND)
            
            Image.objects.create(sensor=sensor, process_id=process_id, image=image_file)
                
        return Response({'message': 'Image uploaded successfully'}, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
# Refactored sensor image upload
def upload_image_2(request):
    '''
    Refactored image upload function which uses the new unique_identifier field in the data model for faster lookup of sensor objects.
    '''
    u_ids = request.data.getlist('u_ids')
    process_id = request.data.get('process_id')
    image_files = request.FILES.getlist('image_files')
    
    if len(image_files) != len(u_ids):
        return Response({'error': 'Mismatch between the number of images and sensor u_ids.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        for i, image_file in enumerate(image_files):
            u_id = u_ids[i]
            
            sensor = Sensor.objects.filter(unique_identifier=u_id).first()
            
            if not sensor:
                return Response({'error': 'Sensor not found.'}, status=status.HTTP_404_NOT_FOUND)
            
            Image.objects.create(sensor=sensor, process_id=process_id, image=image_file)
            
        return Response({'message': 'Image uploaded successfully'}, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    

# get sensor images (2)
@api_view(['GET'])
def get_images(request):
    images = Image.objects.all()
    image_data = []
    
    for image in images:
        # Get the unique identifier for the associated electrode
        unique_identifier = image.sensor.get_unique_identifier()
        
        # Append the necessary data to the list
        image_data.append({
            'sensor': unique_identifier,
            'process_id': image.process_id,
            'image': image.image.url
        })
    
    paginator = BatchPaginator()
    paginated_data = paginator.paginate_queryset(image_data, request)
    # No need to use serializer since the response is manually created
    #return Response(image_data)
    return paginator.get_paginated_response(paginated_data)


# POST sensorlabels
@api_view(['POST'])
def sensor_label(request):
    serializer = SensorLabelSerializer(data=request.data)
    if serializer.is_valid():
        label = serializer.save()
        print(f"Label Created: {label.name}")
        return Response({'message': 'Labels created successfully!'}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def labels(request):
    sensor_labels = SensorLabel.objects.all()
    serializer = SensorLabelSerializer(sensor_labels, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def labels_lst(request):
    s_labels = SensorLabel.objects.values('name')
    labels_list = [{'name': label['name']} for label in s_labels]
    return Response(labels_list)

@api_view(['POST'])
def verify_sensors(request):
    '''
    Verifies a list of sensor unique identifiers (e.g. 'M100-62-001).
    '''
    identifiers = request.data.get('sensors', [])
    if not identifiers:
        return Response({'error': 'No sensors provided.'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Fetch all sensors and compute their identifiers
    sensors = Sensor.objects.all()
    id_map = {sensor.get_unique_identifier(): sensor.id for sensor in sensors}
    
    existing_ids = [identifier for identifier in identifiers if identifier in id_map]
    
    return Response(existing_ids, status=status.HTTP_200_OK)

@api_view(['POST']) #TODO: In use for testing and production servers
def verify_sensors_2(request):
    identifiers = request.data.get('sensors', [])
    if not identifiers:
        return Response({"error": "No sensors provided."}, status=status.HTTP_400_BAD_REQUEST)

    existing_ids = Sensor.objects.filter(unique_identifier__in=identifiers).values_list('unique_identifier', flat=True)

    return Response(list(existing_ids), status=status.HTTP_200_OK)

@api_view(['POST'])
def verify_sensors_3(request):
    identifiers = request.data.get('sensors', [])
    print(f'Sensors to be verified: {identifiers}')
    if not identifiers:
        return Response({'error': 'No Sensors provided.'}, status=status.HTTP_400_BAD_REQUEST)

    # Prefetch SensorProcessRelation with its related ProcessFile
    sensors = Sensor.objects.filter(unique_identifier__in=identifiers).prefetch_related(
        Prefetch(
            'process_relations',
            queryset=SensorProcessRelation.objects.select_related('process_file').only(
                'process_file_id', 'timestamp', 'unique_identifier'
            ),
            to_attr='prefetched_process_relations'
        )
    ).only('unique_identifier', 'sensor_description', 'label')
    
    if not sensors.exists():
        return Response({'error': 'No matching sensors found'}, status=status.HTTP_404_NOT_FOUND)

    serializer = SLSerializer(sensors, many= True)

    return Response({'validated_sensors': serializer.data}, status=status.HTTP_200_OK)
   


@api_view(['POST'])
def assign_labels(request):
    """_summary_
    Assigns labels (by name) to sensors identified by their unique identifier.
    Payload format:
    {
        "sensor_labels": [
            { "sensor_id": "M100-62-001", "label": "XX-RE" },
        ]
    }
    """

    data = request.data.get('sensor_labels', [])
    if not data:
        return Response({'error': "No label data submitted."}, status=status.HTTP_400_BAD_REQUEST)
    
    updated = []
    errors = []
    
    for item in data:
        sensor_uid = item.get('sensor_id')
        label_name = item.get('label')
        
        if not sensor_uid or not label_name:
            errors.append({'sensor_id': sensor_uid, 'error': 'Missing sensor_id or label'})
            continue
        
        try:
            sensor = next(
                (s for s in Sensor.objects.all() if s.get_unique_identifier() == sensor_uid),
                None 
            )
            if not sensor:
                raise Sensor.DoesNotExist
            
            label = SensorLabel.objects.get(name=label_name)
            sensor.label = label
            sensor.save()
            updated.append(sensor_uid)
            
        except Sensor.DoesNotExist:
            errors.append({'sensor_id': sensor_uid, 'errors': "Sensor not found."})
        except SensorLabel.DoesNotExist:
            errors.append({'sensor_id': sensor_uid, 'error': f"Label '{label_name}' not found."})
            
    return Response({'updated': updated, "errors": errors}, status=status.HTTP_200_OK)



@api_view(['POST']) #TODO: In use for testing and production servers
def assign_labels_2(request):
    """
    Accepts a list of {identifier, label_name} objects.
    Updates each corresponding Sensor with the new label.
    """
    updates = request.data.get('sensor_labels', [])
    if not updates:
        return Response({"error": "No labels provided."}, status=status.HTTP_400_BAD_REQUEST)

    errors = []
    updated = []

    for item in updates:
        sensor_uid = item.get('sensor_id')
        label_name = item.get('label')

        if not sensor_uid or not label_name:
            errors.append({
                "sensor_uid": sensor_uid,
                "error": "Missing identifier or label_name"
            })
            continue

        try:
            sensor = Sensor.objects.get(unique_identifier=sensor_uid)
        except Sensor.DoesNotExist:
            errors.append({
                "sensor_uid": sensor_uid,
                "error": "Sensor not found"
            })
            continue

        try:
            label = SensorLabel.objects.get(name=label_name)
        except SensorLabel.DoesNotExist:
            errors.append({
                "sensor_uid": sensor_uid,
                "error": f"Label '{label_name}' not found"
            })
            continue

        sensor.label = label
        sensor.save()
        updated.append(sensor_uid)

    return Response({
        "updated": updated,
        "errors": errors
    }, status=status.HTTP_200_OK)


@api_view(['POST']) #TODO: testing if sensor_description can be included as well
def assign_labels_3(request):
    """
    Accepts a list of {identifier, label_name, description} objects.
    Updates each corresponding Sensor with the new label and description if needed.
    """
    updates = request.data.get('sensor_labels', [])
    if not updates:
        return Response({"error": "No labels provided."}, status=status.HTTP_400_BAD_REQUEST)

    errors = []
    updated = []

    for item in updates:
        sensor_uid = item.get('sensor_id')
        label_name = item.get('label')
        has_description = 'description' in item
        description = item.get('description', '')

        if not sensor_uid or not label_name:
            errors.append({
                "sensor_uid": sensor_uid,
                "error": "Missing identifier or label_name"
            })
            continue

        try:
            sensor = Sensor.objects.get(unique_identifier=sensor_uid)
        except Sensor.DoesNotExist:
            errors.append({
                "sensor_uid": sensor_uid,
                "error": "Sensor not found"
            })
            continue

        try:
            label = SensorLabel.objects.get(name=label_name)
        except SensorLabel.DoesNotExist:
            errors.append({
                "sensor_uid": sensor_uid,
                "error": f"Label '{label_name}' not found"
            })
            continue
        
        updated_flag = False
        
        if sensor.label != label:
            sensor.label = label
            updated_flag = True
        
        if has_description and sensor.sensor_description != description:
            sensor.sensor_description = description
            updated_flag = True
        
        if updated_flag:
            sensor.save()
            updated.append(sensor_uid)

    return Response({
        "updated": updated,
        "errors": errors
    }, status=status.HTTP_200_OK)






















#TODO: Implement PDF upload and include sensor labeling in update page 

@api_view(['PUT'])
def update_sensors_labels(request):
    # Extract data from the request
    data = request.data
    print("Received data:", data)
    
    u_ids = data.get('u_ids', [])
    new_process_data = data.get('new_process_data', [])
    delete_list = data.get('delete_list', [])
    update_data = data.get('updates', {})

    response_details = {
        "updated_items": 0,
        "created_items": 0,
        "deleted_items": 0
    }

    try:
        with transaction.atomic():  # Ensure atomicity
            # Step 1: Retrieve and filter electrodes
            sensors_qs = Sensor.objects.filter(unique_identifier__in=u_ids)

            sensors = list(sensors_qs)
            sensor_ids = [sensor.id for sensor in sensors]
            print(f"Number of electrodes to process: {len(sensors)}")
            
            if not sensors:
                return Response({'error': 'No valid sensors found.'}, status=status.HTTP_404_NOT_FOUND)

            # Step 2: Bulk Update Electrode Instances
            update_fields = {}
            allowed_fields = ['sensor_label', 'sensor_description']
            
            for field in allowed_fields:
                if field in update_data:
                    update_fields[field] = update_data[field]
                    
            if 'label' in update_data:
                try:
                    label_obj = SensorLabel.objects.get(name=update_data['label'])
                    update_fields['label'] = label_obj
                except SensorLabel.DoesNotExist:
                    return Response({'error': f"Label '{update_data['label']}' does not exist."}, status=status.HTTP_400_BAD_REQUEST)
            
            if update_fields:
                sensors_qs.update(**update_fields)
                response_details['updated_items'] = len(sensor_ids)

            # Step 3: Bulk Create WaferProcessRelation Entries
            sensor_process_relations = []
            for process_entry in new_process_data:
                process_id = process_entry.get('process_id')
                timestamp = process_entry.get('timestamp')

                # Validate input fields
                if not process_id or not timestamp:
                    raise ValueError("Each process entry must include both process_id and timestamp.")
                if not ProcessFile.objects.filter(process_id=process_id).exists():
                    raise ValueError(f"Invalid process_id: {process_id} does not exist.")

                # Create WaferProcessRelation entries
                for sensor in sensors:
                    sensor_process_relations.append(
                        SensorProcessRelation(
                            process_file_id=process_id,
                            sensor=sensor,
                            timestamp=timestamp,
                            unique_identifier=sensor.get_unique_identifier()
                        )
                    )

            if sensor_process_relations:
                try:
                    SensorProcessRelation.objects.bulk_create(
                        sensor_process_relations, ignore_conflicts=True
                    )
                    response_details["created_items"] = len(sensor_process_relations)
                except Exception as e:
                    print(f"Error during bulk_create: {e}")
                    raise
            elif not sensor_process_relations:
                print("No valid sensor-process relations to insert.")

            # Step 4: Handle Deletions
            if delete_list:
                valid_processes = [
                    (process.get('process_id').strip(), process.get('timestamp').strip())
                    for process in delete_list if process.get('process_id') and process.get('timestamp')
                ]
                if valid_processes:
                    filters = Q(sensor_id__in=sensor_ids)
                    for process_id, timestamp in valid_processes:
                        filters &= Q(process_file_id=process_id, timestamp=timestamp)

                    deleted_count, _ = SensorProcessRelation.objects.filter(filters).delete()
                    response_details["deleted_items"] = deleted_count

        # Step 5: Return a Consolidated Response
        return Response(response_details, status=status.HTTP_200_OK)

    except ValueError as ve:
        print(f"Validation error: {ve}")
        return Response({'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        print(f"Error in processing request: {e}")
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# Modified to ensure deletion works when there are multiple processes to delete
@api_view(['PUT'])
def update_sensors_labels_2(request):
    # Extract data from the request
    data = request.data
    print("Received data:", data)
    
    u_ids = data.get('u_ids', [])
    new_process_data = data.get('new_process_data', [])
    delete_list = data.get('delete_list', [])
    update_data = data.get('updates', {})

    response_details = {
        "updated_items": 0,
        "created_items": 0,
        "deleted_items": 0
    }

    try:
        with transaction.atomic():  # Ensure atomicity
            # Step 1: Retrieve and filter electrodes
            sensors_qs = Sensor.objects.filter(unique_identifier__in=u_ids)

            sensors = list(sensors_qs)
            sensor_ids = [sensor.id for sensor in sensors]
            print(f"Number of electrodes to process: {len(sensors)}")
            
            if not sensors:
                return Response({'error': 'No valid sensors found.'}, status=status.HTTP_404_NOT_FOUND)

            # Step 2: Bulk Update Electrode Instances
            update_fields = {}
            allowed_fields = ['sensor_label', 'sensor_description']
            
            for field in allowed_fields:
                if field in update_data:
                    update_fields[field] = update_data[field]
                    
            if 'label' in update_data:
                try:
                    label_obj = SensorLabel.objects.get(name=update_data['label'])
                    update_fields['label'] = label_obj
                except SensorLabel.DoesNotExist:
                    return Response({'error': f"Label '{update_data['label']}' does not exist."}, status=status.HTTP_400_BAD_REQUEST)
            
            if update_fields:
                sensors_qs.update(**update_fields)
                response_details['updated_items'] = len(sensor_ids)

            # Step 3: Bulk Create WaferProcessRelation Entries
            sensor_process_relations = []
            for process_entry in new_process_data:
                process_id = process_entry.get('process_id')
                timestamp = process_entry.get('timestamp')

                # Validate input fields
                if not process_id or not timestamp:
                    raise ValueError("Each process entry must include both process_id and timestamp.")
                if not ProcessFile.objects.filter(process_id=process_id).exists():
                    raise ValueError(f"Invalid process_id: {process_id} does not exist.")

                # Create WaferProcessRelation entries
                for sensor in sensors:
                    sensor_process_relations.append(
                        SensorProcessRelation(
                            process_file_id=process_id,
                            sensor=sensor,
                            timestamp=timestamp,
                            unique_identifier=sensor.get_unique_identifier()
                        )
                    )

            if sensor_process_relations:
                try:
                    SensorProcessRelation.objects.bulk_create(
                        sensor_process_relations, ignore_conflicts=True
                    )
                    response_details["created_items"] = len(sensor_process_relations)
                except Exception as e:
                    print(f"Error during bulk_create: {e}")
                    raise
            elif not sensor_process_relations:
                print("No valid sensor-process relations to insert.")

            # Step 4: Handle Deletions
            if delete_list:
                valid_processes = [
                    (process.get('process_id').strip(), process.get('timestamp').strip())
                    for process in delete_list if process.get('process_id') and process.get('timestamp')
                ]
                if valid_processes:
                    based_filter = Q(sensor_id__in=sensor_ids)
                    process_filters = Q()
                    for process_id, timestamp in valid_processes:
                        process_filters |= Q(process_file_id=process_id, timestamp=timestamp)
                        
                    combined_filter = based_filter & process_filters
                    deleted_count, _ = SensorProcessRelation.objects.filter(combined_filter).delete()
                    response_details["deleted_items"] = deleted_count

        # Step 5: Return a Consolidated Response
        return Response(response_details, status=status.HTTP_200_OK)

    except ValueError as ve:
        print(f"Validation error: {ve}")
        return Response({'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        print(f"Error in processing request: {e}")
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)






import re
import tempfile
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from PyPDF2 import PdfReader
from PIL import Image
import pytesseract

@api_view(['POST'])
@parser_classes([MultiPartParser])
def upload_file_and_get_sensors(request):
    file = request.FILES.get('file')
    if not file:
        return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            for chunk in file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        content = ''
        if file.name.lower().endswith('.pdf'):
            reader = PdfReader(tmp_path)
            for page in reader.pages:
                content += page.extract_text()
        else:  # Assume image
            image = Image.open(tmp_path)
            content = pytesseract.image_to_string(image)

        print("Extracted content:", content)

        # Parse sensor identifiers (format M###-##-###)
        identifiers = set(re.findall(r'[A-Z]\d{3}-\d{2}-\d{3}', content))

        # Parse batch_location, batch_id, wafer_id from identifiers
        sensors_to_return = []
        for identifier in identifiers:
            match = re.match(r'([A-Z])(\d{3})-(\d{2})-(\d{3})', identifier)
            if match:
                loc, batch, wafer, sensor = match.groups()
                sensor_qs = Sensor.objects.filter(
                    batch_location=loc,
                    batch_id=int(batch),
                    wafer_id=int(wafer),
                    sensor_id=int(sensor)
                )
                for sensor_obj in sensor_qs:
                    sensors_to_return.append({
                        "id": sensor_obj.id,
                        "identifier": sensor_obj.get_unique_identifier(),
                        "label": sensor_obj.label.name if sensor_obj.label else None,
                    })

        return Response({"sensors": sensors_to_return}, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"Error processing file: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    
    

