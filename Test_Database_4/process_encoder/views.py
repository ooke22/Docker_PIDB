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
from .serializers import FileProcessSerializer
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

    
        
        
    

