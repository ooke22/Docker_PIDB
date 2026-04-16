"""
experiments/urls.py

URL routing for experiments API with electrode support.
"""

from django.urls import path
from . import views

app_name = 'experiments'

urlpatterns = [
    # Experiment CRUD
    path('', views.list_experiments, name='list_experiments'),
    path('create/', views.create_experiment, name='create_experiment'),
    path('<str:experiment_id>/', views.get_experiment, name='get_experiment'),
    path('<str:experiment_id>/update/', views.update_experiment, name='update_experiment'),
    path('<str:experiment_id>/delete/', views.delete_experiment, name='delete_experiment'),
    
    # Results management
    path('<str:experiment_id>/results/', views.get_experiment_results, name='get_results'),
    path('<str:experiment_id>/results/upload/', views.upload_results, name='upload_results'),
    
    # Utilities
    path('utils/validate-sensors/', views.validate_sensors, name='validate_sensors'),
    path('utils/statistics/', views.experiment_statistics, name='statistics'),
]


"""
In your main urls.py, include:

from django.urls import path, include

urlpatterns = [
    # ... other patterns
    path('api/experiments/', include('experiments.urls')),
]

This creates these endpoints:

LIST & CREATE:
GET     /api/experiments/                            - List all experiments (with filters)
POST    /api/experiments/create/                     - Create experiment (with/without results)

RETRIEVE, UPDATE, DELETE:
GET     /api/experiments/<experiment_id>/            - Get complete experiment details
PATCH   /api/experiments/<experiment_id>/update/     - Update experiment metadata
DELETE  /api/experiments/<experiment_id>/delete/     - Delete experiment

RESULTS:
GET     /api/experiments/<experiment_id>/results/    - Get results
POST    /api/experiments/<experiment_id>/results/upload/ - Upload/update results

UTILITIES:
GET     /api/experiments/utils/validate-sensors/     - Validate sensor IDs
GET     /api/experiments/utils/statistics/           - Get dashboard statistics
"""