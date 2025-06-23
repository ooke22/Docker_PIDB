from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import ExperimentTest, ExperimentSensorRelation
from sensor_4_app.models import Sensor
from .serializer import ExperimentTestSerializer, ExperimentDetailSerializer, ExSenRelSerializer


@api_view(['POST'])
def create_experiment(request):
    """

    Creates a new experiment and attaches sensors.
    Expected payload:
    {
        "test_id": "EXP001",
        "sensor": [
            {"id": "M021-01-045", "role": "working"},
            {"id": "B210-01-100", "role": "reference"}
        ]
    }
    """
    
    serializer = ExperimentTestSerializer(data=request.data)
    if serializer.is_valid():
        experiment = serializer.save()
        return Response({'message': 'Experiment created successfully', 'experiment': serializer.data}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#@api_view(['POST'])