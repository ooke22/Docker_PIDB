from django.urls import path, include
from . import views

urlpatterns = [
    path('v2/sensors/', views.create_batch_api, name='async-create-batch-websockets'),
    path('batch-status/<str:task_id>/', views.check_batch_status, name='check-batch-status'),
    path('batches/', views.batches, name='batches'),
    path('batches-2/', views.batches_2, name='batches-2'),
    path('batches-3/', views.batches_3, name='batches-3'),
    path('batches-4/', views.batches_4, name='batches-4'),
    path('update-batch/<str:batch_location>/<int:batch_id>/', views.update_batch_optimized, name='update-batch'),
    path('batch-detail/<str:batch_location>/<int:batch_id>/', views.batch_detail, name='batch-detail'),
    path('async/update-batch/<str:batch_location>/<int:batch_id>/', views.update_batch_async, name='async-update-batch'),
    path('unified_sensor_update/', views.unified_sensor_update_endpoint, name='unified-sensor-update-endpoint'),
    path('batch-update-status/', views.batch_update_status, name='batch-update-status'),
    path('sensor-label/', views.sensor_labels, name='create-sensor-label'),
    path('s-labels/', views.labels, name='sensor-labels'),
    path('s-l/', views.labels_lst, name='labels-lst-dropdown'),
    path('verify-sensors/', views.verify_sensors, name='verify-sensors'),
    path('image-upload/', views.upload_image_with_imagegroups, name='image-upload'),
    path('images/', views.get_images_optimized_final, name='view-images'),
    path('u_id-dropdown/', views.sensors_dropdown, name='u_ids-list'),
    path('dashboard-core-stats/', views.dashboard_core_stats, name='dashboard-core-stats'),
    path('dashboard-recent-activity/', views.dashboard_recent_activity, name='dashboard-recent-activity'),
    path('dashboard-latest-batches/', views.dahsboard_latest_batches, name='dashnoard-latest-batches'),
    path('dashboard-process-stats/', views.dashboard_processes, name='dashboard-processes'),
    # ==== Search and autocomplete ======
    path('search/', views.search_sensors, name='search-sensors'),
    path('autocomplete/', views.autocomplete_search, name='autcomplete-search'),
    path('sensors/', views.sensors, name='sensors'),
    path('sensors-2/', views.sensors_2, name='sensors-2-batch-wafer-and uid ranges'),
    path('sl-update/', views.sl_with_processes_optimized, name='sensor-update')
    
   
]
