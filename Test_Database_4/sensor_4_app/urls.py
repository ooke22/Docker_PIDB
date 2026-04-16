from django.urls import path, include
from . import views

urlpatterns = [
    path('batch/',  views.batch_encoder, name='Create Batch'),
    path('batchview/', views.bulk_electrode_view, name='View entire database'),
    path('batches/', views.get_batches, name='View Batches'),
    path('batches/delete/<str:batch_location>/<int:batch_id>/', views.delete_batch, name='Delete Batches'),
    path('sensor/search/', views.search_electrode, name='Search function'),
    path('v4/detail/<str:batch_location>/<int:batch_id>/', views.batch_detail_4, name='Batch Detail V4'),
    path('electrode-dropdown/', views.electrode_dropdown, name='Electrode Dropdown'),
    path('image-upload/', views.upload_image_3, name='Image Upload'),
    path('v4/update/<str:batch_location>/<int:batch_id>/', views.update_batch, name='Update Sensors'),
    path('delete_process/<str:b_l>/<int:b_id>/', views.delete_process, name='delete_process'),
    path('sensors/', views.sensors, name='Dynamic Query of Sensors'),
    path('v2/sensors/', views.sensors_2, name='Dynamic Query of Sensors 2'),
    path('v3/sensors/', views.sensors_3, name='Dynamic query 3 with process_id'),
    path('v4/sensors/', views.sensors_4, name='Sensor 4'),
    path('sensor_processes/', views.sensor_processes, name='Sensor Processes'),
    path('sp/', views.s_p, name='SP'),
    path('batches_2/', views.get_batches_2, name='Get Batches '),
    path('batches_3/', views.get_batches_3_with_processes, name='Get Batches 3'),
    path('batches_4/', views.get_batches_4, name='Batches 4'),
    path('batches_5/', views.get_batches_5, name='Batches 5'),
    path('batches_5/<str:batch_location>/<int:batch_id>/', views.get_batches_5, name='Batches 5'),
    path('batches_5/<str:batch_location>/', views.get_batches_5, name='Batches 5'),
    path('image/view/', views.get_images_2, name='View Images'),
    path('sensorLabel/', views.sensor_label, name='Create Sensor Labels'),
    path('s_labels/', views.labels, name='View Sensor Labels'),
    path('s_l/', views.labels_lst, name='Drop down list of labels'),
    path('verify_sensors/', views.verify_sensors, name='Verify Sensors'),
    path('assign_labels/', views.assign_labels, name='Assign Sensor Labels'),
    path('verify_sensors_2/', views.verify_sensors_2, name='Verify Sensors'),
    path('assign_labels_2/', views.assign_labels_2, name='Assign Sensor Labels'),
    path('assign_labels_3/', views.assign_labels_3, name='Assign Labels with Description included'),
    path('sensor/bulk-update/', views.update_sensors_labels_2, name='Update sensors in bulk'),
    path('verify_sensors_3/', views.verify_sensors_3, name='Verify Sensors'),
    path('sensor-delete/<str:u_id>/', views.sensor_delete, name='Delete single sensor.'),
    
    path('images/', views.get_images_enhanced, name='get_images_enhanced'),
    
    # Summary APIs
    path('sensors/summary/', views.get_sensor_summary, name='sensor_summary'),
    path('processes/summary/', views.get_process_summary, name='process_summary'),
    
    # Search suggestions
    path('search/suggestions/', views.search_suggestions, name='search_suggestions'),
    
    # ====== Optimized System API endpoints
    path('v2/batch/', views.batch_encoder_with_relations, name='Optimized Batch Encoder'),
    path('v5/batch/<str:batch_location>/<int:batch_id>/', views.update_batch_optimized, name='Optimized Batch Update'),
    path('v2/sensors/', views.sl_with_processes_optimized, name='Optimized sensor update'),
    path('v3/images/', views.upload_image_with_imagegroups, name='Optimized Image Upload'),
    path('v3/view-images/', views.get_images_optimized_final, name='Optimized image view'),
    
    # =====Async urls========
    path('api/batch-encoder-async/', views.batch_encoder_async, name='batch_encoder_async'),
    path('api/batch-status/<str:task_id>/', views.check_batch_status, name='check_batch_status'),
    #path('api/batch-summary/', views.batch_summary_async_aware, name='batch_summary_async'),
    
]