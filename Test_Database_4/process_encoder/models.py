from django.db import models

from django.db import models
from djongo import models
from djongo.models import JSONField


class ProcessFile(models.Model):
    process_id = models.CharField(primary_key=True, max_length=10)
    scope = models.CharField(max_length=50, blank=True, null=True)
    description = models.CharField(max_length=200, blank=True, null=True)
    source = models.FileField(upload_to='uploads/')
    parsed_data = models.JSONField(blank=True, null=True)  # Store parsed CSV data as a list of dictionaries

    def __str__(self):
        return f'{str(self.process_id)} - {str(self.csv)}'
    
class ProcessFiles(models.Model):
    id = models.AutoField(primary_key=True)
    process_id = models.CharField(unique=True, max_length=10)
    scope = models.CharField(max_length=50, blank=True, null=True)
    description = models.CharField(max_length=200, blank=True, null=True)
    source = models.FileField(upload_to='uploads/')
    parsed_data = models.JSONField(blank=True, null=True)  # Store parsed CSV data as a list of dictionaries

    def __str__(self):
        return f'{str(self.process_id)} - {str(self.source)}'


