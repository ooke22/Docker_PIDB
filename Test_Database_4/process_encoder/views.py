from django.shortcuts import render
import csv
import pandas as pd
import json
import re
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import ProcessFile
from .serializers import FileProcessSerializer, ProcessSerializer
from sensor_4_app.models import Sensor, SensorProcessRelation


@api_view(['POST'])
def process_upload(request):
    serializer = FileProcessSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'error': f'Invalid data: {serializer.errors}'}, status=status.HTTP_400_BAD_REQUEST)

    uploaded_file = serializer.validated_data['source']

    if not uploaded_file:
        return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
    
    file_extension = uploaded_file.name.split('.')[-1].lower()
    
    if file_extension == 'csv':
        try:
            decoded_file = uploaded_file.read().decode('utf-8-sig').splitlines()
            csv_data = csv.reader(decoded_file)
            header = next(csv_data) # Extract the header row
            header = [h.lower() for h in header] 
            
            # Normalize all headers to lower case
            required_columns = {"parameter", "unit", "value", "description"}
            
            # Check if all required columns are present after normalization
            if not required_columns.issubset(set(header)):
                return Response({'error': 'Column names must include "parameter", "unit", "value", and "description".'}, status=status.HTTP_400_BAD_REQUEST)

            # Collect parsed data from each row
            parsed_data = []
            for row in csv_data:
                if len(row) != len(header):
                    return Response({'error': 'CSV row does not match header length'}, status=status.HTTP_400_BAD_REQUEST)
                
                row_data = {header[i]: row[i] for i in range(len(header))} # Converts each row into a dictionary with header fields as keys and row values as values
                parsed_data.append(row_data)
        except UnicodeDecodeError as e:
            return Response({'error': f'Error decoding CSV file: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        
    elif file_extension == 'xlsx':
        try:
            df = pd.read_excel(uploaded_file, engine='openpyxl')
            required_columns = {"parameter", "unit", "value", "description"}
            df.columns = [col.lower() for col in df.columns] # Normalize all headers to lowercase
            
            # Check if all required columns are present after normalization
            if not required_columns.issubset(set(df.columns)):
                return Response({'error': 'Column names must include "parameter", "unit", "value", and "description".'}, status=status.HTTP_400_BAD_REQUEST)
            
            df = df.astype(str).replace({'nan': None, 'NaN': None, 'NaT': None, 'None': None}) # Convert all data to strings and replace NaN with None
            parsed_data = df.to_dict(orient='records')
        except Exception as e:
            return Response({'error': f'Error reading excel file {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        
    else:
        return Response({'error': 'Unsupported file format'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Add the parsed CSV data to the validated data before saving
    validated_data = serializer.validated_data
    validated_data['parsed_data'] = parsed_data
    
    # Update serializer data with parsed data before saving 
    process_serializer = FileProcessSerializer(data=validated_data)
    if process_serializer.is_valid():
        print('process_serializer valid')
        # Save the process to the database
        process = process_serializer.save()
        print(f'Process Created: {process.process_id}')  # additional code for debugging
        return Response({'message': 'Upload Successful!'}, status=status.HTTP_201_CREATED)
    else:
        return Response({'error': f'Invalid file data: {process_serializer.errors}'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET']) # Dropdown GET: retrieves the list processes for the dropdown button
def get_processes(request):
    processes = ProcessFile.objects.values('process_id', 'description').order_by('process_id')
    process_list = [{'process_id': process['process_id'], 'description': process['description']} for process in processes]
    return Response(process_list)


@api_view(['GET']) # Retrieves the list of processes to be viewed in the frontend
def view_processes(request):
    processes = ProcessFile.objects.all().order_by('process_id')
    serializer = FileProcessSerializer(processes, many=True)
    return Response(serializer.data)

@api_view(['DELETE'])
def delete_processes(request, process_id):
    try:      
        process = ProcessFile.objects.get(process_id=process_id)
        process.delete()
        return Response({'message': f'Process {process} deleted successfully!'}, status=status.HTTP_200_OK)
    
    except ProcessFile.DoesNotExist:
        # Handle case where process does not exist
        return Response({'error': 'Process ID does not exists'}, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['PUT'])
def update_process_1(request, process_id):
    try:
        process = ProcessFile.objects.get(process_id=process_id)
    except ProcessFile.DoesNotExist:
        return Response({'error': 'Process ID does not exist.'}, status=status.HTTP_404_NOT_FOUND)
        
    data = request.data
    
    #Update only the allowed fields 
    allowed_fields = ['process_id', 'scope', 'description']
    
    if 'process_id' in data and data['process_id'] != process.process_id:
        if ProcessFile.objects.filter(process_id=data['process_id']).exists():
            return Response({'error': 'New Process ID already exists.'}, status=status.HTTP_400_BAD_REQUEST)
        
    for field in allowed_fields:
        if field in data:
            setattr(process, field, data[field])
    
    try:           
        process.save()
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response({'message': 'Process updated successfully.', 'updated_data': {
        'process_id': process.process_id,
        'scope': process.scope,
        'description': process.description
    }}, status=status.HTTP_200_OK)
    
@api_view(['PUT'])
def update_process(request, process_id):
    try:
        process = ProcessFile.objects.get(process_id=process_id)
    except ProcessFile.DoesNotExist:
        return Response({'error': 'Process ID does not exist.'}, status=status.HTTP_404_NOT_FOUND)
        
    data = request.data

    # Allowed fields for updates
    allowed_fields = ['scope', 'description']

    # Check if process_id is being changed
    new_process_id = data.get('process_id', None)
    if new_process_id and new_process_id != process.process_id:
        if ProcessFile.objects.filter(process_id=new_process_id).exists():
            return Response({'error': 'New Process ID already exists.'}, status=status.HTTP_400_BAD_REQUEST)

        # Create a new ProcessFile instance with the new process_id
        new_process = ProcessFile.objects.create(
            process_id=new_process_id,
            scope=process.scope,
            description=process.description,
            source=process.source,
            parsed_data=process.parsed_data
        )

        # Transfer Foreign Key Relationships
        SensorProcessRelation.objects.filter(process_file=process).update(process_file=new_process)
        #Image.objects.filter(process_id=process.process_id).update(process_id=new_process_id)

        # Delete the old ProcessFile
        process.delete()

        return Response({'message': 'Process ID updated successfully.', 'updated_data': {
            'process_id': new_process.process_id,
            'scope': new_process.scope,
            'description': new_process.description
        }}, status=status.HTTP_200_OK)

    # If no process_id change, update other fields
    for field in allowed_fields:
        if field in data:
            setattr(process, field, data[field])

    try:
        process.save()
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({'message': 'Process updated successfully.', 'updated_data': {
        'process_id': process.process_id,
        'scope': process.scope,
        'description': process.description
    }}, status=status.HTTP_200_OK)
    
       
# ======== Process API Endpoint ==========
@api_view(['GET'])
def process_api(request):
    """ 
    This API endpoint allows users to view the entire list of process files uploaded and the contents of each file.
    Users can utilize query parameters to narrow search for specific fields within the files.
    Utilize the 'parameter', 'unit', 'value', and 'description' headers within each file to perform the query.
    Example: ?parameter=temp&unit=celsius&value=78&p-id=PROC001,PROC002
    """
    try:
        # Get all process files
        processes = ProcessFile.objects.all().order_by('process_id')
        
        # Extract query parameters (all normalized to lowercase for consistent matching)
        query_p_id = request.query_params.get('p-id', '').strip()
        query_parameter = request.query_params.get('parameter', '').lower().strip()
        query_unit = request.query_params.get('unit', '').lower().strip()
        query_value = request.query_params.get('value', '').lower().strip()
        query_description = request.query_params.get('description', '').lower().strip()
        
        # Parse process IDs (support comma-separated list)
        process_id_list = []
        if query_p_id:
            # Split by comma and strip whitespace from each ID
            process_id_list = [pid.strip() for pid in query_p_id.split(',') if pid.strip()]
        
        # Filter processes by process_id if provided
        if process_id_list:
            processes = processes.filter(process_id__in=process_id_list)
        
        # If no query parameters, return all processes with their full data
        if not any([query_parameter, query_unit, query_value, query_description]):
            serializer = FileProcessSerializer(processes, many=True)
            return Response({
                'count': processes.count(),
                'filtered_by_process_id': bool(process_id_list),
                'process_ids': process_id_list if process_id_list else None,
                'processes': serializer.data
            }, status=status.HTTP_200_OK)
        
        # Filter processes based on query parameters within parsed_data
        filtered_results = []
        
        for process in processes:
            if not process.parsed_data:
                continue
            
            # Filter rows within parsed_data that match ALL provided query parameters
            matching_rows = []
            
            for row in process.parsed_data:
                # Normalize row values to lowercase for case-insensitive matching
                row_parameter = str(row.get('parameter', '')).lower().strip()
                row_unit = str(row.get('unit', '')).lower().strip()
                row_value = str(row.get('value', '')).lower().strip()
                row_description = str(row.get('description', '')).lower().strip()
                
                # Check if row matches all provided query parameters (partial match using 'in')
                matches = True
                
                if query_parameter and query_parameter not in row_parameter:
                    matches = False
                if query_unit and query_unit not in row_unit:
                    matches = False
                if query_value and query_value not in row_value:
                    matches = False
                if query_description and query_description not in row_description:
                    matches = False
                
                if matches:
                    matching_rows.append(row)
            
            # If this process has matching rows, add it to results
            if matching_rows:
                filtered_results.append({
                    'process_id': process.process_id,
                    'scope': process.scope,
                    'description': process.description,
                    'source': process.source.url if process.source else None,
                    'matching_rows': matching_rows,
                    'total_matches': len(matching_rows)
                })
        
        return Response({
            'count': len(filtered_results),
            'filtered_by_process_id': bool(process_id_list),
            'query_parameters': {
                'process_ids': process_id_list if process_id_list else None,
                'parameter': query_parameter or None,
                'unit': query_unit or None,
                'value': query_value or None,
                'description': query_description or None
            },
            'results': filtered_results
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'An error occurred while processing the request: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)   
        
    

# ======== Process API Endpoint ==========
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def process_api(request):
    """ 
    This API endpoint allows users to view the entire list of process files uploaded and the contents of each file.
    Users can utilize query parameters to narrow search for specific fields within the files.
    Utilize the 'parameter', 'unit', 'value', and 'description' headers within each file to perform the query.
    Example: ?parameter=temp&unit=celsius&value=78
    """
    try:
        # Get all process files
        processes = ProcessFile.objects.all().order_by('process_id')
        
        # Extract query parameters (all normalized to lowercase for consistent matching)
        query_p_id = request.query_params.get('p-id', '').lower().strip()
        query_parameter = request.query_params.get('parameter', '').lower().strip()
        query_unit = request.query_params.get('unit', '').lower().strip()
        query_value = request.query_params.get('value', '').lower().strip()
        query_description = request.query_params.get('description', '').lower().strip()
        
        # If no query parameters, return all processes with their full data
        if not any([query_p_id, query_parameter, query_unit, query_value, query_description]):
            serializer = ProcessSerializer(processes, many=True)
            return Response({
                'count': processes.count(),
                'processes': serializer.data
            }, status=status.HTTP_200_OK)
        
        # Filter processes based on query parameters
        filtered_results = []
        
        for process in processes:
            if not process.parsed_data:
                continue
            
            # Filter rows within parsed_data that match ALL provided query parameters
            matching_rows = []
            
            for row in process.parsed_data:
                # Normalize row values to lowercase for case-insensitive matching
                row_parameter = str(row.get('parameter', '')).lower().strip()
                row_unit = str(row.get('unit', '')).lower().strip()
                row_value = str(row.get('value', '')).lower().strip()
                row_description = str(row.get('description', '')).lower().strip()
                
                # Check if row matches all provided query parameters (partial match using 'in')
                matches = True
                
                if query_parameter and query_parameter not in row_parameter:
                    matches = False
                if query_unit and query_unit not in row_unit:
                    matches = False
                if query_value and query_value not in row_value:
                    matches = False
                if query_description and query_description not in row_description:
                    matches = False
                
                if matches:
                    matching_rows.append(row)
            
            # If this process has matching rows, add it to results
            if matching_rows:
                filtered_results.append({
                    'process_id': process.process_id,
                    'scope': process.scope,
                    'description': process.description,
                    'source': process.source.url if process.source else None,
                    'matching_rows': matching_rows,
                    'total_matches': len(matching_rows)
                })
        
        return Response({
            'count': len(filtered_results),
            'query_parameters': {
                'parameter': query_parameter or None,
                'unit': query_unit or None,
                'value': query_value or None,
                'description': query_description or None
            },
            'results': filtered_results
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'An error occurred while processing the request: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)   
