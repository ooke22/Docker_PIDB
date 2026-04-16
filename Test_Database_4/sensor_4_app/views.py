from django.shortcuts import render
from rest_framework.decorators import api_view
from .models import Sensor, Image, SensorProcessRelation, SensorLabel, ImageGroup
from process_encoder.models import ProcessFile
from .serializer import ImageSerializer, TestSensorSerializer, BatchSerializer, SensorSerializer, SearchFuncSerializer, DetailSerializer, SensorFilterSerializer, SensorProcessRelationSerializer, SensorLabelSerializer, SLSerializer, UIDSerializer
from datetime import datetime, timezone
from django.db import transaction
from django.db.utils import IntegrityError
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.db.models import Prefetch, Q, Count
import logging
import os, io
from django.core.cache import cache
import traceback
import time
from django.core.files.base import ContentFile
from PIL import Image as PilImage
logger = logging.getLogger(__name__)


@api_view(['POST'])
def batch_encoder(request):
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
                        sensor_description=sensor_description,
                    )
                    sensor.unique_identifier = sensor.get_unique_identifier()
                    
                    sensors.append(sensor)
                    process_file_map[sensor.unique_identifier] = sensor_processes

            # Bulk insert all Sensor objects at once
            Sensor.objects.bulk_create(sensors, batch_size=1000)

            # Efficiently retrieve saved sensors using u_ids
            unique_ids = list(process_file_map.keys())
            saved_sensors = Sensor.objects.filter(unique_identifier__in=unique_ids)
            sensor_lookup = {sensor.unique_identifier: sensor for sensor in saved_sensors}

            # Prepare SensorProcessRelation entries
            sensor_process_relations = []

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
 
 
#TODO: Used in testing and production
# Speed test 5 optimized for multi-reponses. THIS WORKS TOO
@api_view(['PUT'])
def update_batch(request, batch_location, batch_id):
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
                    print("✅ Sensor-process relations successfully created")
                    response_details["created_items"] = len(sensor_process_relations)
                except Exception as e:
                    print(f"Error during bulk_create: {e}")
                    traceback.print_exc()
                    raise e
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
        traceback.print_exc()
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)




@api_view(['GET'])
def bulk_electrode_view(request):
    sensors = Sensor.objects.all().prefetch_related('sensor_process_relations', 'images')
    serializer = BatchSerializer(sensors, many=True)
    return Response(serializer.data)
    
    
class BatchPaginator(PageNumberPagination):
    page_size = 5 # Default page size
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
        #batch_location, batch_id, wafer_id, sensor_id = parse_sensor_identifier(identifier)
        
        # Corresponding electrodes in the database
        sensor = Sensor.objects.filter(
            unique_identifier=identifier
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


# In use on test and prod server
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
    sensors = Sensor.objects.values_list('unique_identifier', flat=True)
    #serializer = UIDSerializer(sensors, many=True)
    #data = [{"unique_identifier": uid} for uid in sensors]
    return Response(list(sensors))


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
@api_view(['POST'])
def upload_image_2(request):
    '''
    Refactored image upload function which uses the new unique_identifier field in the data model for faster lookup of sensor objects.
    '''
    u_ids = request.data.getlist('u_ids')
    process_ids = request.data.getlist('process_ids')
    image_files = request.FILES.getlist('image_files')
    print(f"UIDS: {u_ids}, PROCESSES: {process_ids}, FILES: {image_files}")
    
    if not len(image_files) == len(process_ids) == len(u_ids):
        return Response({'error': 'Mismatch between the number of images, processes, and sensor u_ids.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        for i in range(len(image_files)):
            u_id = u_ids[i]
            process_id = process_ids[i]
            image_file = image_files[i]
            
            sensor = Sensor.objects.filter(unique_identifier=u_id).first()
            
            if not sensor:
                return Response({'error': 'Sensor not found.'}, status=status.HTTP_404_NOT_FOUND)
            
            Image.objects.create(sensor=sensor, process_id=process_id, image=image_file)
            
        return Response({'message': 'Image uploaded successfully'}, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
@api_view(['POST'])
def upload_image_3(request):
    """ 
    Refactored image upload function supporting grouped uploads with multiple images for the same sensor and process ID.
    """
    u_ids = request.data.getlist('u_ids')
    process_ids = request.data.getlist('process_ids')
    image_files = request.FILES.getlist('image_files')
    
    print(f"{u_ids}\n{process_ids}\n{image_files}")
    
    if not len(image_files) == len(process_ids) == len(u_ids):
        print(f"Number of image files: {len(image_files)}\nNumber of process_ids: {len(process_ids)}\nNumber of u_ids: {len(u_ids)}")
        return Response({'error': 'Mismatch between image_files, process_ids, and u_ids count.'}, status=status.HTTP_400_BAD_REQUEST)
    
    success_count = 0
    failure_details = []
    
    for i in range(len(image_files)):
        u_id = u_ids[i]
        process_id = process_ids[i]
        image_file = image_files[i]
        
        try:
            sensor = Sensor.objects.filter(unique_identifier=u_id).first()
            if not sensor:
                failure_details.append({
                    'index': i,
                    'u_id': u_id,
                    'reason': 'Sensor not found.'
                }) 
                continue
            
            Image.objects.create(sensor=sensor, process_id=process_id, image=image_file)
            success_count += 1
            
        except Exception as e:
            failure_details.append({
                'index': i,
                'u_id': u_id,
                'reason': str(e)
            })
    
    if not success_count:
        return Response({'error': 'No images were uploaded.', 'details': failure_details}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response({
        'message': f'{success_count} image(s) uploaded successfully!',
        'failures': failure_details
    }, status=status.HTTP_201_CREATED)
    
    

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

@api_view(['GET'])
def get_images_2(request):
    sensor_query = request.GET.get('sensor', '').lower()
    process_query = request.GET.get('process', '').lower()

    images = Image.objects.all()

    if sensor_query:
        images = images.filter(sensor__unique_identifier__icontains=sensor_query)
    if process_query:
        images = images.filter(process_id__icontains=process_query)
        
    image_data = []

    for image in images:
        unique_identifier = image.sensor.get_unique_identifier()

        # Extract filename without extension
        filename = os.path.basename(image.image.name)
        base, ext = os.path.splitext(filename)

        image_data.append({
            'sensor': unique_identifier,
            'process_id': image.process_id,
            'image': image.image.url,
            'file_name': filename,          # full filename (e.g., M007-01-001_t.png)
            'suffix': base.split('_')[-1] if '_' in base else '',  # extract 't' or 'w'
        })

    paginator = BatchPaginator()
    paginated_data = paginator.paginate_queryset(image_data, request)
    return paginator.get_paginated_response(paginated_data)


# POST sensorlabels
# Refactored to allow creation of multiple SensorLabel entries in one POST request using Postman
@api_view(['POST'])
def sensor_label(request):
    data = request.data 
    # check if data is a list (bulk creation) or a single object
    if isinstance(data, list):
        serializer = SensorLabelSerializer(data=data, many=True)
    else: 
        serializer = SensorLabelSerializer(data=data)
        
    if serializer.is_valid():
        labels = serializer.save()
        # Print all created label names
        if isinstance(labels, list):
            for label in labels:
                print(f"Label created: {label.name}")
        else:
            print(f"Label created: {labels.name}")
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

@api_view(['DELETE'])
def sensor_delete(request, u_id): 
    try:
        sensor = Sensor.objects.filter(unique_identifier=u_id) 
        
        if not sensor.exists():
            return Response({'error': 'Item not found.'}, status=status.HTTP_404_NOT_FOUND)
        sensor.delete()

        return Response({'error': 'Item deleted successfully!'}, status=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)










import re
import tempfile
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from PyPDF2 import PdfReader
#from PIL import Image
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

    
    
class ImagePaginator(PageNumberPagination):
    page_size = 150  # Default page size
    page_size_query_param = 'page_size'
    max_page_size = 300
    
    def get_paginated_response(self, data):
        return Response({
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'page_size': self.page_size,
            'results': data
        })

@api_view(['GET'])
def get_images_enhanced(request):
    """
    Enhanced image API with search, filtering, and optimized pagination
    """
    # Get query parameters
    search_query = request.GET.get('search', '').strip()
    sensor_filter = request.GET.get('sensor', '').strip()
    process_filter = request.GET.get('process_id', '').strip()
    image_type_filter = request.GET.get('type', '').strip()  # t, h, p, v, w
    sort_by = request.GET.get('sort', 'sensor')  # sensor, process_id, file_name, created_at
    sort_order = request.GET.get('order', 'asc')  # asc, desc
    
    # Create cache key for this specific query
    cache_key = f"images_{hash(str(request.GET))}"
    cached_result = cache.get(cache_key)
    
    if cached_result and not search_query:  # Don't cache search results
        return cached_result
    
    # Start with all images
    images = Image.objects.select_related('sensor').all()
    
    # Apply filters
    if search_query:
        images = images.filter(
            Q(sensor__unique_identifier__icontains=search_query) |
            Q(process_id__icontains=search_query) |
            Q(image__icontains=search_query)
        )
    
    if sensor_filter:
        images = images.filter(sensor__unique_identifier=sensor_filter)
    
    if process_filter:
        images = images.filter(process_id__icontains=process_filter)
    
    if image_type_filter and image_type_filter != 'all':
        # Filter by suffix (t, h, p, v, w)
        images = images.filter(image__icontains=f'_{image_type_filter}.')
    
    # Apply sorting
    sort_field = sort_by
    if sort_order == 'desc':
        sort_field = f'-{sort_field}'
    
    images = images.order_by(sort_field, 'id')  # Add id for consistent pagination
    
    # Process image data
    image_data = []
    for image in images:
        unique_identifier = image.sensor.get_unique_identifier()
        filename = os.path.basename(image.image.name)
        base, ext = os.path.splitext(filename)
        
        # Extract suffix more reliably
        suffix = ''
        if '_' in base:
            parts = base.split('_')
            suffix = parts[-1] if len(parts) > 1 else ''
        
        image_data.append({
            'id': image.id,
            'sensor': unique_identifier,
            'process_id': image.process_id or 'Unspecified',
            'image': image.image.url,
            'file_name': filename,
            'suffix': suffix,
            'created_at': image.created_at.isoformat() if hasattr(image, 'created_at') else None,
            'file_size': image.image.size if image.image else 0,
        })
    
    # Paginate the processed data
    paginator = ImagePaginator()
    paginated_data = paginator.paginate_queryset(image_data, request)
    response = paginator.get_paginated_response(paginated_data)
    
    # Add metadata
    response.data['metadata'] = {
        'total_sensors': images.values('sensor__unique_identifier').distinct().count(),
        'total_processes': images.values('process_id').distinct().count(),
        'search_applied': bool(search_query),
        'filters_applied': {
            'sensor': sensor_filter,
            'process': process_filter,
            'type': image_type_filter,
        }
    }
    
    # Cache non-search results for 5 minutes
    if not search_query:
        cache.set(cache_key, response, 300)
    
    return response

@api_view(['GET'])
def get_sensor_summary(request):
    """
    Get summary statistics for sensors
    """
    cache_key = "sensor_summary"
    cached_result = cache.get(cache_key)
    
    if cached_result:
        return Response(cached_result)
    
    # Get sensor statistics
    sensor_stats = (
        Image.objects
        .values('sensor__unique_identifier')
        .annotate(
            image_count=Count('id'),
            process_count=Count('process_id', distinct=True)
        )
        .order_by('sensor__unique_identifier')
    )
    
    summary = []
    for stat in sensor_stats:
        summary.append({
            'sensor_id': stat['sensor__unique_identifier'],
            'image_count': stat['image_count'],
            'process_count': stat['process_count'],
            'processes': list(
                Image.objects
                .filter(sensor__unique_identifier=stat['sensor__unique_identifier'])
                .values_list('process_id', flat=True)
                .distinct()
            )
        })
    
    result = {
        'sensors': summary,
        'total_sensors': len(summary),
        'total_images': sum(s['image_count'] for s in summary),
        'total_processes': len(set().union(*[s['processes'] for s in summary]))
    }
    
    # Cache for 10 minutes
    cache.set(cache_key, result, 600)
    
    return Response(result)

@api_view(['GET'])
def get_process_summary(request):
    """
    Get summary statistics for processes
    """
    cache_key = "process_summary"
    cached_result = cache.get(cache_key)
    
    if cached_result:
        return Response(cached_result)
    
    # Get process statistics
    process_stats = (
        Image.objects
        .values('process_id')
        .annotate(
            image_count=Count('id'),
            sensor_count=Count('sensor__unique_identifier', distinct=True)
        )
        .order_by('process_id')
    )
    
    summary = []
    for stat in process_stats:
        process_id = stat['process_id'] or 'Unspecified'
        summary.append({
            'process_id': process_id,
            'image_count': stat['image_count'],
            'sensor_count': stat['sensor_count'],
        })
    
    result = {
        'processes': summary,
        'total_processes': len(summary),
    }
    
    # Cache for 10 minutes
    cache.set(cache_key, result, 600)
    
    return Response(result)

@api_view(['GET'])
def search_suggestions(request):
    """
    Get search suggestions for autocomplete
    """
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return Response({'suggestions': []})
    
    cache_key = f"search_suggestions_{query.lower()}"
    cached_result = cache.get(cache_key)
    
    if cached_result:
        return Response(cached_result)
    
    suggestions = []
    
    # Get sensor suggestions
    sensors = (
        Image.objects
        .filter(sensor__unique_identifier__icontains=query)
        .values_list('sensor__unique_identifier', flat=True)
        .distinct()[:5]
    )
    
    for sensor in sensors:
        suggestions.append({
            'value': sensor,
            'type': 'sensor',
            'label': f'Sensor: {sensor}'
        })
    
    # Get process suggestions
    processes = (
        Image.objects
        .filter(process_id__icontains=query)
        .values_list('process_id', flat=True)
        .distinct()[:5]
    )
    
    for process in processes:
        if process:  # Skip None values
            suggestions.append({
                'value': process,
                'type': 'process',
                'label': f'Process: {process}'
            })
    
    # Get filename suggestions
    filenames = (
        Image.objects
        .filter(image__icontains=query)
        .values_list('image', flat=True)[:5]
    )
    
    for filename in filenames:
        base_name = os.path.basename(filename)
        suggestions.append({
            'value': base_name,
            'type': 'filename',
            'label': f'File: {base_name}'
        })
    
    result = {'suggestions': suggestions[:10]}  # Limit to 10 suggestions
    
    # Cache for 5 minutes
    cache.set(cache_key, result, 300)
    
    return Response(result)

# =============================================================================
# 6. ASYNC BATCH ENCODER API VIEW
# =============================================================================

from .tasks import create_batch_async

@api_view(['POST'])
def batch_encoder_async(request):
    """
    Async batch encoder - returns immediately while processing in background
    """
    try:
        batch_data = request.data
        
        # Basic validation
        required_fields = ['batch_location', 'batch_id', 'total_wafers', 'total_sensors']
        for field in required_fields:
            if field not in batch_data:
                return Response({'error': f'Missing required field: {field}'}, status=400)
        
        # Start async task
        task = create_batch_async.delay(batch_data)
        print(f"Task id: {task.id}")
        
        return Response({
            'message': 'Batch creation started!',
            'task_id': task.id,
            'status': 'PROCESSING',
            'batch_info': {
                'batch_location': batch_data.get('batch_location'),
                'batch_id': batch_data.get('batch_id'),
                'total_sensors': int(batch_data['total_wafers']) * int(batch_data['total_sensors'])
            },
            'check_status_url': f'/api/batch-status/{task.id}/'
        }, status=status.HTTP_202_ACCEPTED)  # 202 = Accepted for processing
        
    except Exception as e:
        logger.error(f"Failed to start batch creation: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# =============================================================================
# 7. TASK STATUS CHECKING API
# =============================================================================

@api_view(['GET'])
def check_batch_status(request, task_id):
    """
    Check the status of an async batch creation task
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
    
# =====USE of Optimized Data Model (ImageGroups) ======
@api_view(['POST'])
def batch_encoder(request):
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
                        sensor_description=sensor_description,
                    )
                    sensor.unique_identifier = sensor.get_unique_identifier()
                    
                    sensors.append(sensor)
                    process_file_map[sensor.unique_identifier] = sensor_processes

            # Bulk insert all Sensor objects at once
            Sensor.objects.bulk_create(sensors, batch_size=1000)

            # Efficiently retrieve saved sensors using u_ids
            unique_ids = list(process_file_map.keys())
            saved_sensors = Sensor.objects.filter(unique_identifier__in=unique_ids)
            sensor_lookup = {sensor.unique_identifier: sensor for sensor in saved_sensors}

            # Prepare SensorProcessRelation entries
            sensor_process_relations = []

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

# =============================================================================
# BATCH ENCODER - Creates ImageGroups during sensor creation
# =============================================================================
from .tasks import create_imagegroups_task

@api_view(['POST'])
def batch_encoder_with_imagegroups(request):
    """
    Batch encoder that creates sensors AND pre-initializes ImageGroups using Celery 
    """
    try:
        batch_data = request.data
        
        # Extract data (same as before)
        batch_location = batch_data.get('batch_location')
        batch_id = batch_data.get('batch_id')
        batch_label = batch_data.get('batch_label', '')
        batch_description = batch_data.get('batch_description', '')
        total_wafers = int(batch_data['total_wafers'])
        total_sensors = int(batch_data['total_sensors'])
        sensor_processes = batch_data.get('sensor_processes', [])
        
        with transaction.atomic():
            # Step 1: Create sensors (same as optimized version)
            sensors_to_create = []
            unique_identifiers = []
            
            for wafer_id in range(1, total_wafers + 1):
                for sensor_id in range(1, total_sensors + 1):
                    # Pre-compute unique identifier
                    batch_id_padded = str(batch_id).zfill(3)
                    wafer_id_padded = str(wafer_id).zfill(2)
                    sensor_id_padded = str(sensor_id).zfill(3)
                    unique_identifier = f"{batch_location}{batch_id_padded}-{wafer_id_padded}-{sensor_id_padded}"
                    
                    sensor = Sensor(
                        batch_location=batch_location,
                        batch_id=batch_id,
                        batch_label=batch_label,
                        batch_description=batch_description,
                        total_wafers=total_wafers,
                        wafer_id=wafer_id,
                        wafer_label=batch_data.get('wafer_label', ''),
                        wafer_description=batch_data.get('wafer_description', ''),
                        wafer_design_id=batch_data.get('wafer_design_id', ''),
                        total_sensors=total_sensors,
                        sensor_id=sensor_id,
                        sensor_description=batch_data.get('sensor_description', ''),
                        unique_identifier=unique_identifier
                    )
                    
                    sensors_to_create.append(sensor)
                    unique_identifiers.append(unique_identifier)
            
            # Bulk create sensors
            Sensor.objects.bulk_create(sensors_to_create, batch_size=1000)
            
            # Step 2: PRE-CREATE ImageGroups for future image uploads
            if sensor_processes:
                create_imagegroups_task(unique_identifiers, sensor_processes)
        return Response({
            'message': 'Batch created with ImageGroup initialization',
            'details': {
                'sensors_created': len(sensors_to_create),
                'image_groups_creation_task': True
            }
        }, status=201)
            
    except Exception as e:
        return Response({'error': str(e)}, status=500)
    

# =============================================================================
# OPTIMIZED BATCH ENCODER - With required process relations
# =============================================================================
@api_view(['POST'])
def batch_encoder_with_relations(request):
    """
    Fast batch encoder that creates sensors AND required process relations
    No ImageGroup pre-creation for better performance
    """
    try:
        batch_data = request.data
        
        # Extract data
        batch_location = batch_data.get('batch_location')
        batch_id = batch_data.get('batch_id')
        batch_label = batch_data.get('batch_label', '')
        batch_description = batch_data.get('batch_description', '')
        total_wafers = int(batch_data['total_wafers'])
        total_sensors = int(batch_data['total_sensors'])
        sensor_processes = batch_data.get('sensor_processes', [])
        
        # CRITICAL: Pre-validate and cache ProcessFiles
        process_files_cache = {}
        valid_process_data = []
        
        if sensor_processes:
            process_ids = [p.get('process_id') for p in sensor_processes if p.get('process_id')]
            if process_ids:
                # Single query to fetch all process files
                process_files = ProcessFile.objects.filter(process_id__in=process_ids)
                process_files_cache = {pf.process_id: pf for pf in process_files}
                
                # Only keep processes that exist in database
                valid_process_data = [
                    p for p in sensor_processes 
                    if p.get('process_id') in process_files_cache
                ]
        
        with transaction.atomic():
            # Pre-calculate batch identifiers once
            batch_id_padded = str(batch_id).zfill(3)
            
            # Step 1: Create sensors efficiently
            sensors_to_create = []
            
            for wafer_id in range(1, total_wafers + 1):
                wafer_id_padded = str(wafer_id).zfill(2)
                
                for sensor_id in range(1, total_sensors + 1):
                    sensor_id_padded = str(sensor_id).zfill(3)
                    unique_identifier = f"{batch_location}{batch_id_padded}-{wafer_id_padded}-{sensor_id_padded}"
                    
                    sensor = Sensor(
                        batch_location=batch_location,
                        batch_id=batch_id,
                        batch_label=batch_label,
                        batch_description=batch_description,
                        total_wafers=total_wafers,
                        wafer_id=wafer_id,
                        wafer_label=batch_data.get('wafer_label', ''),
                        wafer_description=batch_data.get('wafer_description', ''),
                        wafer_design_id=batch_data.get('wafer_design_id', ''),
                        total_sensors=total_sensors,
                        sensor_id=sensor_id,
                        sensor_description=batch_data.get('sensor_description', ''),
                        unique_identifier=unique_identifier  # ✅ FIXED: Direct assignment
                    )
                    
                    sensors_to_create.append(sensor)
            
            # Bulk create sensors
            Sensor.objects.bulk_create(sensors_to_create, batch_size=1000)
            
            # Step 2: Create process relations efficiently (REQUIRED for batch_summary)
            relations_created = 0
            if valid_process_data:
                relations_created = _create_process_relations_fast(
                    sensors_to_create, valid_process_data, process_files_cache
                )
                
            return Response({
                'message': 'Batch created successfully!',
                'details': {
                    'sensors_created': len(sensors_to_create),
                    'process_relations_created': relations_created,
                    'processes_attached': list(process_files_cache.keys()),
                    'ready_for_batch_summary': True
                }
            }, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        logger.error(f"Batch creation failed: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _create_process_relations_fast(sensors_to_create, valid_process_data, process_files_cache):
    """
    Highly optimized process relation creation
    """
    # Pre-fetch saved sensors in one query using unique_identifiers
    unique_identifiers = [s.unique_identifier for s in sensors_to_create]
    saved_sensors = Sensor.objects.filter(unique_identifier__in=unique_identifiers)
    sensor_lookup = {s.unique_identifier: s for s in saved_sensors}
    
    # Prepare all relations for bulk creation
    relations_to_create = []
    
    for process_data in valid_process_data:
        process_id = process_data.get('process_id')
        timestamp = process_data.get('timestamp')
        
        # Parse timestamp once per process
        if timestamp:
            timestamp = timestamp.rstrip('Z')
            timestamp = datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc)
        else:
            timestamp = timezone.now()  # Default timestamp
        
        process_file = process_files_cache[process_id]  # No database hit!
        
        # Create relations for ALL sensors in batch
        for unique_identifier in unique_identifiers:
            sensor = sensor_lookup.get(unique_identifier)
            if sensor:  # Safety check
                relations_to_create.append(
                    SensorProcessRelation(
                        process_file=process_file,
                        timestamp=timestamp,
                        sensor=sensor,
                        unique_identifier=unique_identifier
                    )
                )
    
    # Single bulk create for all relations
    if relations_to_create:
        SensorProcessRelation.objects.bulk_create(relations_to_create, batch_size=1000)
    
    return len(relations_to_create)

# =============================================================================
# SIMPLIFIED BATCH ENCODER - No ImageGroup pre-creation
# =============================================================================
@api_view(['POST'])
def batch_encoder_optimized(request):
    """
    Simplified batch encoder - creates only sensors and relations
    ImageGroups created lazily during image upload
    """
    try:
        batch_data = request.data
        
        # Extract data
        batch_location = batch_data.get('batch_location')
        batch_id = batch_data.get('batch_id')
        batch_label = batch_data.get('batch_label', '')
        batch_description = batch_data.get('batch_description', '')
        total_wafers = int(batch_data['total_wafers'])
        total_sensors = int(batch_data['total_sensors'])
        sensor_processes = batch_data.get('sensor_processes', [])
        
        # Pre-validate processes (if any)
        valid_process_ids = []
        if sensor_processes:
            process_ids = [p.get('process_id') for p in sensor_processes if p.get('process_id')]
            if process_ids:
                valid_processes = ProcessFile.objects.filter(process_id__in=process_ids).values_list('process_id', flat=True)
                valid_process_ids = list(valid_processes)
        
        with transaction.atomic():
            # Create sensors
            sensors_to_create = []
            
            for wafer_id in range(1, total_wafers + 1):
                for sensor_id in range(1, total_sensors + 1):
                    # Pre-compute unique identifier
                    batch_id_padded = str(batch_id).zfill(3)
                    wafer_id_padded = str(wafer_id).zfill(2)
                    sensor_id_padded = str(sensor_id).zfill(3)
                    unique_identifier = f"{batch_location}{batch_id_padded}-{wafer_id_padded}-{sensor_id_padded}"
                    
                    sensor = Sensor(
                        batch_location=batch_location,
                        batch_id=batch_id,
                        batch_label=batch_label,
                        batch_description=batch_description,
                        total_wafers=total_wafers,
                        wafer_id=wafer_id,
                        wafer_label=batch_data.get('wafer_label', ''),
                        wafer_description=batch_data.get('wafer_description', ''),
                        wafer_design_id=batch_data.get('wafer_design_id', ''),
                        total_sensors=total_sensors,
                        sensor_id=sensor_id,
                        sensor_description=batch_data.get('sensor_description', ''),
                        unique_identifier=unique_identifier
                    )
                    
                    sensors_to_create.append(sensor)
            
            # Bulk create sensors
            Sensor.objects.bulk_create(sensors_to_create, batch_size=1000)
            
            # Create process relations (if any)
            relations_created = 0
            if sensor_processes and valid_process_ids:
                relations_created = _create_process_relations_optimized(
                    sensors_to_create, sensor_processes, valid_process_ids
                )
                
            return Response({
                'message': 'Batch created successfully!',
                'details': {
                    'sensors_created': len(sensors_to_create),
                    'process_relations_created': relations_created,
                    'note': 'ImageGroups will be created automatically when images are uploaded'
                }
            }, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        logger.error(f"Batch creation failed: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# OPTIMIZED UPDATE_BATCH FUNCTION
# =============================================================================

@api_view(['PUT'])
def update_batch_optimized(request, batch_location, batch_id):
    """
    Optimized batch update that focuses solely on sensor-process relationships
    """
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
        "deleted_items": 0,
        "performance_metrics": {}
    }

    try:
        start_time = time.time()
        
        with transaction.atomic():
            # Step 1: Retrieve and filter sensors (optimized query)
            sensors_qs = Sensor.objects.filter(batch_location=batch_location, batch_id=batch_id)
            if wafer_ids:
                sensors_qs = sensors_qs.filter(wafer_id__in=wafer_ids)
            if sensor_ids:
                sensors_qs = sensors_qs.filter(sensor_id__in=sensor_ids)

            # Only select fields we actually need
            sensors_data = list(sensors_qs.values('id', 'unique_identifier'))
            sensor_db_ids = [s['id'] for s in sensors_data]
            
            print(f"Number of sensors to process: {len(sensors_data)}")
            
            if not sensors_data:
                return Response({'error': 'No sensors found matching criteria'}, 
                              status=status.HTTP_404_NOT_FOUND)
            
            query_time = time.time() - start_time
            response_details["performance_metrics"]["query_time"] = f"{query_time:.3f}s"

            # Step 2: Bulk Update Sensor Instances
            if update_data:
                print(f"Applying updates to sensors: {update_data}")
                # Filter to only allowed sensor fields for security
                allowed_fields = {
                    'batch_label', 'batch_description', 'wafer_label', 'wafer_description', 
                    'wafer_design_id', 'sensor_label', 'sensor_description', 'total_wafers', 'total_sensors'
                }
                update_fields = {
                    field: value for field, value in update_data.items() 
                    if field in allowed_fields and hasattr(Sensor, field)
                }
                
                if update_fields:
                    sensors_qs.update(**update_fields)
                    response_details["updated_items"] = len(sensor_db_ids)

            # Step 3: Handle NEW Process Associations
            if new_process_data:
                creation_start = time.time()
                
                # Pre-validate all processes in one query
                process_ids = [p.get('process_id') for p in new_process_data if p.get('process_id')]
                if not process_ids:
                    raise ValueError("No valid process IDs provided")
                    
                valid_process_files = {
                    pf.process_id: pf 
                    for pf in ProcessFile.objects.filter(process_id__in=process_ids)
                }
                
                if not valid_process_files:
                    raise ValueError("No valid process IDs found in database")
                
                sensor_process_relations = []
                
                # Process each entry and validate
                for process_entry in new_process_data:
                    process_id = process_entry.get('process_id')
                    timestamp = process_entry.get('timestamp')

                    if process_id not in valid_process_files:
                        continue
                    
                    if not timestamp:
                        raise ValueError(f"Timestamp required for process {process_id}")
                    
                    # Parse timestamp once and validate
                    try:
                        if isinstance(timestamp, str):
                            timestamp = datetime.fromisoformat(timestamp.rstrip('Z')).replace(tzinfo=timezone.utc)
                    except ValueError as e:
                        raise ValueError(f"Invalid timestamp format for process {process_id}: {timestamp}")

                    # Create relations for all matching sensors
                    for sensor_data in sensors_data:
                        sensor_process_relations.append(
                            SensorProcessRelation(
                                process_file=valid_process_files[process_id],  # Fixed: use object, not ID
                                sensor_id=sensor_data['id'],
                                timestamp=timestamp,
                                unique_identifier=sensor_data['unique_identifier']
                            )
                        )
                        
                # Bulk create with optimized batch size
                if sensor_process_relations:
                    # Use smaller batches for better memory usage
                    batch_size = 1000
                    created_count = 0
                    
                    for i in range(0, len(sensor_process_relations), batch_size):
                        batch = sensor_process_relations[i:i + batch_size]
                        created_relations = SensorProcessRelation.objects.bulk_create(
                            batch, ignore_conflicts=True
                        )
                        created_count += len(created_relations)
                    
                    response_details["created_items"] = created_count
                
                creation_time = time.time() - creation_start
                response_details["performance_metrics"]["creation_time"] = f"{creation_time:.3f}s"

            # Step 4: Handle DELETIONS
            if delete_list:
                deletion_start = time.time()
                
                # Build efficient deletion conditions
                process_conditions = []
                for process in delete_list:
                    process_id = process.get('process_id', '').strip()
                    timestamp = process.get('timestamp', '').strip()
                    if process_id and timestamp:
                        try:
                            parsed_timestamp = datetime.fromisoformat(timestamp.rstrip('Z')).replace(tzinfo=timezone.utc)
                            process_conditions.append((process_id, parsed_timestamp))
                        except ValueError:
                            print(f"Invalid timestamp in delete_list: {timestamp}")
                            continue
                        
                if process_conditions:
                    # Build efficient Q object for deletion
                    deletion_filter = Q(sensor_id__in=sensor_db_ids)
                    process_q = Q()
                    for process_id, timestamp in process_conditions:
                        process_q |= Q(process_file__process_id=process_id, timestamp=timestamp)
                    
                    deletion_filter &= process_q
                    
                    deleted_count, _ = SensorProcessRelation.objects.filter(deletion_filter).delete()
                    response_details["deleted_items"] = deleted_count
                
                deletion_time = time.time() - deletion_start
                response_details["performance_metrics"]["deletion_time"] = f"{deletion_time:.3f}s"

        total_time = time.time() - start_time
        response_details["performance_metrics"]["total_time"] = f"{total_time:.3f}s"
        
        return Response(response_details, status=status.HTTP_200_OK)

    except ValueError as ve:
        print(f"Validation error: {ve}")
        return Response({'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        print(f"Error in processing request: {e}")
        traceback.print_exc()
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# =============================================================================
# OPTIMIZED SL_WITH_PROCESSES FUNCTION  
# =============================================================================

@api_view(['PUT'])
def sl_with_processes_optimized(request):
    """
    Optimized sensor-level update for specific sensors by unique_identifier
    """
    data = request.data
    print("Received data:", data)
    
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
            # Step 1: Validate and retrieve sensors by unique_identifier
            sensors_data = list(Sensor.objects.filter(
                unique_identifier__in=u_ids
            ).values('id', 'unique_identifier'))
            
            found_u_ids = {s['unique_identifier'] for s in sensors_data}
            invalid_u_ids = set(u_ids) - found_u_ids
            
            if invalid_u_ids:
                response_details['invalid_u_ids'] = list(invalid_u_ids)
                print(f"Warning: Invalid u_ids found: {invalid_u_ids}")
                
            if not sensors_data:
                return Response({'error': 'No valid sensors found.'}, status=status.HTTP_404_NOT_FOUND)
            
            sensor_db_ids = [s['id'] for s in sensors_data]
            # FIXED: corrected field name
            unique_identifiers = [s['unique_identifier'] for s in sensors_data]
            
            print(f"Number of sensors to process: {len(sensors_data)}")

            # Step 2: Update allowed sensor fields
            if update_data:
                update_fields = {}
                allowed_fields = ['sensor_label', 'sensor_description']
                
                for field in allowed_fields:
                    if field in update_data:
                        update_fields[field] = update_data[field]
                        
                # Handle label relationship update
                if 'label' in update_data:
                    try:
                        label_obj = SensorLabel.objects.get(name=update_data['label'])
                        update_fields['label'] = label_obj
                    except SensorLabel.DoesNotExist:
                        return Response({'error': f"Label '{update_data['label']}' does not exist."}, 
                                    status=status.HTTP_400_BAD_REQUEST)
                
                if update_fields:
                    Sensor.objects.filter(id__in=sensor_db_ids).update(**update_fields)
                    response_details["updated_items"] = len(sensor_db_ids)

            # Step 3: Handle NEW Process Associations
            if new_process_data:
                creation_start = time.time()
                
                # Pre-validate processes
                process_ids = [p.get('process_id') for p in new_process_data if p.get('process_id')]
                if not process_ids:
                    raise ValueError("No valid process IDs provided")
                    
                valid_process_files = {
                    pf.process_id: pf 
                    for pf in ProcessFile.objects.filter(process_id__in=process_ids)
                }
                
                if not valid_process_files:
                    raise ValueError("No valid process IDs found in database")
                
                sensor_process_relations = []
                
                for process_entry in new_process_data:
                    process_id = process_entry.get('process_id')
                    timestamp = process_entry.get('timestamp')
                    
                    if process_id not in valid_process_files or not timestamp:
                        continue
                    
                    try:
                        if isinstance(timestamp, str):
                            timestamp = datetime.fromisoformat(timestamp.rstrip('Z')).replace(tzinfo=timezone.utc)
                    except ValueError:
                        print(f"Invalid timestamp for process {process_id}: {timestamp}")
                        continue
                    
                    # Create relations for specified sensors only
                    for sensor_data in sensors_data:
                        sensor_process_relations.append(
                            SensorProcessRelation(
                                process_file=valid_process_files[process_id],  # Fixed: use object, not field
                                sensor_id=sensor_data['id'],
                                timestamp=timestamp,
                                unique_identifier=sensor_data['unique_identifier']
                            )
                        )
                        
                # Bulk operations with batching
                if sensor_process_relations:
                    batch_size = 1000
                    created_count = 0
                    
                    for i in range(0, len(sensor_process_relations), batch_size):
                        batch = sensor_process_relations[i:i + batch_size]
                        created_relations = SensorProcessRelation.objects.bulk_create(
                            batch, ignore_conflicts=True
                        )
                        created_count += len(created_relations)
                    
                    response_details["created_items"] = created_count
                
                creation_time = time.time() - creation_start
                response_details["performance_metrics"]["creation_time"] = f"{creation_time:.3f}s"
                        
            # Step 4: Handle deletions
            if delete_list:
                deletion_start = time.time()
                
                # Build efficient deletion filter
                process_conditions = []
                for process in delete_list:
                    process_id = process.get('process_id', '').strip()
                    timestamp = process.get('timestamp', '').strip()
                    if process_id and timestamp:
                        try:
                            parsed_timestamp = datetime.fromisoformat(timestamp.rstrip('Z')).replace(tzinfo=timezone.utc)
                            process_conditions.append((process_id, parsed_timestamp))
                        except ValueError:
                            print(f"Invalid timestamp in delete_list: {timestamp}")
                            continue
                        
                if process_conditions:
                    # Build Q object for deletion
                    deletion_filter = Q(sensor_id__in=sensor_db_ids)
                    process_q = Q()
                    for process_id, timestamp in process_conditions:
                        process_q |= Q(process_file__process_id=process_id, timestamp=timestamp)
                    
                    deletion_filter &= process_q
                    
                    deleted_count, _ = SensorProcessRelation.objects.filter(deletion_filter).delete()
                    response_details["deleted_items"] = deleted_count
                
                deletion_time = time.time() - deletion_start
                response_details["performance_metrics"]["deletion_time"] = f"{deletion_time:.3f}s"

        total_time = time.time() - start_time
        response_details["performance_metrics"]["total_time"] = f"{total_time:.3f}s"
        
        return Response(response_details, status=status.HTTP_200_OK)

    except ValueError as ve:
        print(f"Validation error: {ve}")
        return Response({'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        print(f"Error in processing request: {e}")
        traceback.print_exc()
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# IMAGE UPLOAD - Updates ImageGroups when images are added
# =============================================================================

@api_view(['POST'])
def upload_image_with_imagegroups_1(request):
    import os
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
            image_file = image_files[i]

            try:
                sensor = sensors_lookup.get(u_id)
                if not sensor:
                    failure_details.append({'index': i, 'u_id': u_id, 'reason': 'Sensor not found'})
                    continue

                # Create the Image
                image_obj = Image.objects.create(
                    sensor=sensor,
                    process_id=process_id,
                    image=image_file,
                    sensor_unique_id=u_id
                )

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
                base, ext = os.path.splitext(filename)

                image_data = {
                    'id': str(image_obj.id),
                    'image_url': image_obj.image.url,
                    'file_name': filename,
                    'suffix': base.split('_')[-1] if '_' in base else ''
                }

                # Add image only if it doesn't already exist in the group
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