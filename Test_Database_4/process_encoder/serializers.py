from rest_framework import serializers
from .models import ProcessFile

class FileProcessSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessFile
        fields = '__all__'
        
    
    def to_representation(self, instance):
        process = super().to_representation(instance)
        process['parsed_data'] = instance.parsed_data if ProcessFile else None
        return process

class ProcessSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessFile
        fields = ['process_id', 'scope', 'description', 'parsed_data']
        
    
    def to_representation(self, instance):
        process = super().to_representation(instance)
        process['parsed_data'] = instance.parsed_data if ProcessFile else None
        return process



