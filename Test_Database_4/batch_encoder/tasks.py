from celery import shared_task
from process_encoder.models import ProcessFile
from batch_encoder.models import Sensor, SensorLabel
from django.db import transaction
from datetime import datetime
import logging, time, traceback
from .utils.datetime_utils import ensure_datetime
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils.timezone import now

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def create_sensor_batch_task(self, batch_data, sensor_processes):
    # Channel layer for sending messages
    channel_layer = get_channel_layer()
    task_group_name = f"task_{self.request.id}"  # individual task
    global_group_name = "global_tasks"           # global notifications
    
    # Track sent progress updates to prevent duplicates
    sent_progress_milestones = set()
    
    try:
        total_wafers = int(batch_data['total_wafers'])
        total_sensors_per_wafer = int(batch_data['total_sensors'])
        total_sensors = total_wafers * total_sensors_per_wafer
        created_count = 0
        buffer = []
        batch_size = 1000

        # Sort processes by timestamp
        sensor_processes.sort(key=lambda x: x['timestamp'])
        # Precompute process-related denormalized fields
        process_ids = [proc['process_id'] for proc in sensor_processes]
        process_count = len(process_ids)
        last_process_timestamp = max(proc['timestamp'] for proc in sensor_processes) if sensor_processes else None
        
        sensor_id_counter = 1
        for i_w in range(total_wafers):
            wafer_id = i_w + 1
            for i_s in range(total_sensors_per_wafer):
                sensor_id = i_s + 1
                
                # Build embedded processes dict 
                processes = [
                    {
                        'process_id': proc['process_id'],
                        'description': proc.get('description', ''),
                        'timestamp': ensure_datetime(proc['timestamp'])
                    }
                    for proc in sensor_processes
                ]
                
                sensor = Sensor(
                    batch_location=batch_data['batch_location'],
                    batch_id=int(batch_data['batch_id']),
                    batch_label=batch_data.get('batch_label', ''),
                    batch_description=batch_data.get('batch_description', ''),
                    wafer_id=wafer_id,
                    total_wafers=total_wafers,
                    total_sensors=total_sensors_per_wafer,
                    wafer_label=batch_data.get('wafer_label', ''),
                    wafer_description=batch_data.get('wafer_description', ''),
                    wafer_design_id=batch_data.get('wafer_design_id', ''),
                    sensor_id=sensor_id,
                    sensor_description=batch_data.get('sensor_description', ''),
                    processes=processes,
                    process_ids=process_ids,
                    process_count=process_count,
                    last_process_timestamp=last_process_timestamp,
                )
                sensor.unique_identifier=sensor.get_unique_identifier()
                
                buffer.append(sensor)
                sensor_id_counter += 1
                created_count += 1

                # Flush buffer
                if len(buffer) >= batch_size:
                    Sensor.objects.bulk_create(buffer, batch_size=batch_size)
                    buffer = []

                # Calculate progress
                progress = int((created_count / total_sensors) * 100)
                
                # Only send progress updates for specific milestones and only once
                if progress in (25, 50, 75, 100) and progress not in sent_progress_milestones:
                    sent_progress_milestones.add(progress)
                    
                    data = {
                        "task_id": self.request.id,
                        "progress": progress,
                        "state": "PROGRESS",
                        "message": f"Created {created_count}/{total_sensors} sensors",
                    }
                    
                    # Send to task-specific group
                    async_to_sync(channel_layer.group_send)(
                        task_group_name,
                        {"type": "progress_update", "data": data}
                    )
                    # Send to global group
                    async_to_sync(channel_layer.group_send)(
                        global_group_name,
                        {"type": "task_update", "data": data}
                    )

        # Flush remaining sensors
        if buffer:
            Sensor.objects.bulk_create(buffer, batch_size=batch_size)

        # Success message
        success_data = {
            "task_id": self.request.id,
            "progress": 100,
            "state": "SUCCESS",
            "message": f"Batch {batch_data['batch_location']}{batch_data['batch_id']} created successfully!"
        }
        async_to_sync(channel_layer.group_send)(task_group_name, {"type": "progress_update", "data": success_data})
        async_to_sync(channel_layer.group_send)(global_group_name, {"type": "task_update", "data": success_data})

        return {"task_id": self.request.id, "created_sensors": created_count}

    except Exception as e:
        error_data = {
            "task_id": self.request.id,
            "state": "FAILURE",
            "message": str(e)
        }
        async_to_sync(channel_layer.group_send)(task_group_name, {"type": "progress_update", "data": error_data})
        async_to_sync(channel_layer.group_send)(global_group_name, {"type": "task_update", "data": error_data})
        raise


@shared_task(bind=True)
def update_batch_task_1(self, batch_location, batch_id, wafer_ids, sensor_ids, new_process_data, delete_list, update_data):
    """
    Background task for batch update of sensors.
    """
    response_details = {
        "updated_items": 0,
        "created_processes": 0,
        "deleted_processes": 0,
        "performance_metrics": {}
    }

    try:
        start_time = time.time()

        with transaction.atomic():
            # Step 1: Retrieve sensors in batch with filters
            sensors_qs = Sensor.objects.filter(batch_location=batch_location, batch_id=batch_id)
            if wafer_ids:
                sensors_qs = sensors_qs.filter(wafer_id__in=wafer_ids)
            if sensor_ids:
                sensors_qs = sensors_qs.filter(sensor_id__in=sensor_ids)

            sensors_data = list(sensors_qs.only(
                'id', 'processes', 'process_ids', 'unique_identifier'
            ))

            if not sensors_data:
                return {"error": "No sensors found matching criteria"}

            response_details["performance_metrics"]["query_time"] = f"{time.time() - start_time:.3f}s"

            # Step 2: Bulk update sensor fields
            if update_data:
                allowed_fields = {
                    'batch_label', 'batch_description', 'wafer_label', 'wafer_description',
                    'wafer_design_id', 'sensor_label', 'sensor_description',
                }
                update_fields = {
                    field: value for field, value in update_data.items()
                    if field in allowed_fields and hasattr(Sensor, field)
                }
                if update_fields:
                    sensors_qs.update(**update_fields)
                    response_details["updated_items"] = len(sensors_data)

            # Step 3: Add new process associations
            if new_process_data:
                creation_start = time.time()
                valid_process_ids = [p['process_id'] for p in new_process_data if p.get('process_id')]
                valid_process_files = {
                    pf.process_id: pf
                    for pf in ProcessFile.objects.filter(process_id__in=valid_process_ids)
                }

                created_count = 0
                for sensor in sensors_data:
                    updated = False
                    for process_entry in new_process_data:
                        process_id = process_entry.get('process_id')
                        description = process_entry.get('description')
                        timestamp = process_entry.get('timestamp')
                        if not process_id or process_id not in valid_process_files:
                            continue
                        if not description or not timestamp:
                            continue
                        timestamp = ensure_datetime(timestamp)

                        if process_id not in sensor.process_ids:
                            sensor.processes.append({
                                "process_id": process_id,
                                "description": description,
                                "timestamp": timestamp
                            })
                            sensor.process_ids.append(process_id)
                            updated = True

                    if updated:
                        if sensor.processes:
                            sensor.last_process_timestamp = max(
                                ensure_datetime(rel['timestamp']) for rel in sensor.processes
                            )
                        sensor.process_count = len(sensor.process_ids)
                        sensor.save(update_fields=[
                            'processes', 'process_ids',
                            'process_count', 'last_process_timestamp'
                        ])
                        created_count += 1

                response_details["created_processes"] = created_count
                response_details["performance_metrics"]["creation_time"] = f"{time.time() - creation_start:.3f}s"

            # Step 4: Remove process associations
            if delete_list:
                deletion_start = time.time()
                deleted_count = 0
                for sensor in sensors_data:
                    updated = False
                    for process_entry in delete_list:
                        process_id = process_entry.get('process_id')
                        if not process_id:
                            continue
                        original_count = len(sensor.processes)
                        sensor.processes = [
                            rel for rel in sensor.processes if rel["process_id"] != process_id
                        ]
                        sensor.process_ids = [rel["process_id"] for rel in sensor.processes]
                        if len(sensor.processes) != original_count:
                            updated = True
                    if updated:
                        if sensor.processes:
                            sensor.last_process_timestamp = max(
                                ensure_datetime(rel['timestamp']) for rel in sensor.processes
                            )
                        else:
                            sensor.last_process_timestamp = None
                        sensor.process_count = len(sensor.process_ids)
                        sensor.save(update_fields=[
                            'processes', 'process_ids',
                            'process_count', 'last_process_timestamp'
                        ])
                        deleted_count += 1

                response_details["deleted_processes"] = deleted_count
                response_details["performance_metrics"]["deletion_time"] = f"{time.time() - deletion_start:.3f}s"

        response_details["performance_metrics"]["total_time"] = f"{time.time() - start_time:.3f}s"
        return response_details

    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}
    

from concurrent.futures import ThreadPoolExecutor, as_completed
@shared_task(bind=True)
def update_batch_task(self, batch_location, batch_id, wafer_ids, sensor_ids,
                      new_process_data, delete_list, update_data, batch_size=100):
    """
    Background task for batch update of sensors.
    Optimized: precomputes sets, parallelizes updates with ThreadPoolExecutor,
    and sends WebSocket notifications via Django Channels.
    """
    channel_layer = get_channel_layer()
    task_group_name = f"task_{self.request.id}"   # per-task group
    global_group_name = "global_tasks"            # broadcast group

    response_details = {
        "updated_items": 0,
        "created_processes": 0,
        "deleted_processes": 0,
        "performance_metrics": {}
    }

    try:
        start_time = time.time()

        # ----------------- Step 1: Retrieve sensors -----------------
        sensors_qs = Sensor.objects.filter(batch_location=batch_location, batch_id=batch_id)
        if wafer_ids:
            sensors_qs = sensors_qs.filter(wafer_id__in=wafer_ids)
        if sensor_ids:
            sensors_qs = sensors_qs.filter(sensor_id__in=sensor_ids)

        sensors_data = list(sensors_qs.only(
            'id', 'processes', 'process_ids', 'unique_identifier'
        ))

        if not sensors_data:
            return {"error": "No sensors found matching criteria"}

        response_details["performance_metrics"]["query_time"] = f"{time.time() - start_time:.3f}s"

        # ----------------- Step 2: Bulk update top-level fields -----------------
        if update_data:
            allowed_fields = {
                'batch_label', 'batch_description', 'wafer_label', 'wafer_description',
                'wafer_design_id', 'sensor_label', 'sensor_description',
            }
            update_fields = {
                field: value for field, value in update_data.items()
                if field in allowed_fields and hasattr(Sensor, field)
            }
            if update_fields:
                with transaction.atomic():
                    sensors_qs.update(**update_fields)
                response_details["updated_items"] = len(sensors_data)

        # ----------------- Step 3: Precompute reusable data -----------------
        created_count, deleted_count = 0, 0

        valid_process_ids = [p['process_id'] for p in new_process_data if p.get('process_id')] if new_process_data else []
        valid_process_files = {
            pf.process_id: pf
            for pf in ProcessFile.objects.filter(process_id__in=valid_process_ids)
        }

        delete_ids = {p["process_id"] for p in delete_list if p.get("process_id")} if delete_list else set()

        if new_process_data:
            for p in new_process_data:
                if p.get("timestamp"):
                    p["timestamp"] = ensure_datetime(p["timestamp"])

        # ----------------- Step 4: Threaded per-sensor update -----------------
        def update_sensor_processes(sensor):
            created, deleted = 0, 0
            updated = False

            # Remove processes
            if delete_ids:
                original_count = len(sensor.processes)
                sensor.processes = [p for p in sensor.processes if p["process_id"] not in delete_ids]
                sensor.process_ids = [p["process_id"] for p in sensor.processes]
                if len(sensor.processes) != original_count:
                    updated = True
                    deleted = original_count - len(sensor.processes)

            # Add processes
            if new_process_data:
                existing_ids = set(sensor.process_ids)
                for entry in new_process_data:
                    pid = entry.get('process_id')
                    desc = entry.get('description')
                    ts = entry.get('timestamp')
                    if not pid or pid not in valid_process_files or not desc or not ts:
                        continue
                    if pid not in existing_ids:
                        sensor.processes.append({"process_id": pid, "description": desc, "timestamp": ts})
                        sensor.process_ids.append(pid)
                        updated = True
                        created += 1

            # Update metadata and save once
            if updated:
                sensor.last_process_timestamp = max(
                    (p["timestamp"] for p in sensor.processes), default=None
                )
                sensor.process_count = len(sensor.process_ids)
                sensor.save(update_fields=['processes', 'process_ids', 'process_count', 'last_process_timestamp'])

            return created, deleted

        total_sensors = len(sensors_data)

        for i in range(0, total_sensors, batch_size):
            batch = sensors_data[i:i + batch_size]
            with ThreadPoolExecutor(max_workers=min(20, len(batch))) as executor:
                futures = [executor.submit(update_sensor_processes, sensor) for sensor in batch]
                for f in as_completed(futures):
                    c, d = f.result()
                    created_count += c
                    deleted_count += d

            # 🔔 Send intermediate progress
            progress = int(((i + batch_size) / total_sensors) * 100)
            progress_data = {
                "task_id": self.request.id,
                "progress": min(progress, 100),
                "state": "PROGRESS",
                "message": f"Processed {min(i + batch_size, total_sensors)} / {total_sensors} sensors..."
            }
            async_to_sync(channel_layer.group_send)(global_group_name, {"type": "task_update", "data": progress_data})
            async_to_sync(channel_layer.group_send)(task_group_name, {"type": "task_update", "data": progress_data})

        response_details["created_processes"] = created_count
        response_details["deleted_processes"] = deleted_count
        response_details["performance_metrics"]["creation_deletion_time"] = f"{time.time() - start_time:.3f}s"

        response_details["performance_metrics"]["total_time"] = f"{time.time() - start_time:.3f}s"

        # 🔔 Final success message
        success_data = {
            "task_id": self.request.id,
            "progress": 100,
            "state": "SUCCESS",
            "message": f"Batch {batch_location}{batch_id} updated successfully!"
        }
        async_to_sync(channel_layer.group_send)(global_group_name, {"type": "task_update", "data": success_data})
        async_to_sync(channel_layer.group_send)(task_group_name, {"type": "task_update", "data": success_data})

        return response_details

    except Exception as e:
        error_data = {
            "task_id": self.request.id,
            "state": "FAILURE",
            "message": str(e),
            "traceback": traceback.format_exc(limit=1)
        }
        async_to_sync(channel_layer.group_send)(global_group_name, {"type": "task_update", "data": error_data})
        async_to_sync(channel_layer.group_send)(task_group_name, {"type": "task_update", "data": error_data})
        raise



    
@shared_task(bind=True)
def unified_sensor_update_task(self, 
                               # Selection Strategy Parameters
                               selection_strategy,  # 'batch' or 'individual'
                               
                               # Batch Selection Parameters (for strategy='batch')
                               batch_location=None,
                               batch_id=None,
                               wafer_ids=None,
                               sensor_ids=None,
                               
                               # Individual Selection Parameters (for strategy='individual')
                               unique_identifiers=None,
                               
                               # Update Operations
                               update_data=None,
                               new_process_data=None,
                               delete_list=None):
    """
    Unified Celery task for updating sensors with flexible selection strategies.
    OPTIMIZED FOR CharField sensor_label (no ForeignKey overhead).
    
    Args:
        selection_strategy (str): 'batch' or 'individual'
        
        # Batch strategy parameters
        batch_location (str): Batch location code (e.g., 'MXXX')
        batch_id (int): Batch ID number
        wafer_ids (list): List of wafer IDs or ranges ['1-3', '8', '9-12']
        sensor_ids (list): List of sensor IDs or ranges ['1-3', '8', '9-12']
        
        # Individual strategy parameters  
        unique_identifiers (list): List of unique sensor identifiers ['MXXX-XX-XXX']
        
        # Update operations (common to both strategies)
        update_data (dict): Fields to update on sensors (sensor_label now as string)
        new_process_data (list): List of processes to add
        delete_list (list): List of processes to remove
    """
    
    # Validate input parameters
    if selection_strategy not in ['batch', 'individual']:
        return {"error": "selection_strategy must be 'batch' or 'individual'"}
    
    if selection_strategy == 'batch' and (not batch_location or batch_id is None):
        return {"error": "batch_location and batch_id are required for batch strategy"}
        
    if selection_strategy == 'individual' and not unique_identifiers:
        return {"error": "unique_identifiers are required for individual strategy"}
    
    # Initialize response structure
    response_details = {
        "selection_strategy": selection_strategy,
        "updated_items": 0,
        "created_processes": 0,
        "deleted_processes": 0,
        "invalid_identifiers": [],
        "errors": [],
        "performance_metrics": {}
    }
    
    try:
        start_time = time.time()
        
        # Step 1: Build sensor queryset based on selection strategy (OPTIMIZED)
        sensors_qs = _build_sensor_queryset_optimized(
            selection_strategy=selection_strategy,
            batch_location=batch_location,
            batch_id=batch_id,
            wafer_ids=wafer_ids,
            sensor_ids=sensor_ids,
            unique_identifiers=unique_identifiers
        )
        
        # Step 2: Determine if we need individual processing (for processes only)
        needs_individual_processing = bool(new_process_data or delete_list)
        
        # Step 3: Handle pure field updates with maximum bulk efficiency
        bulk_update_count = 0
        if update_data and not needs_individual_processing:
            # Pure bulk update path - maximum performance
            bulk_update_count = _perform_optimized_bulk_update(sensors_qs, update_data, selection_strategy)
            response_details["updated_items"] = bulk_update_count
            
            if not needs_individual_processing:
                # We're done! No need to fetch individual sensors
                response_details["performance_metrics"]["total_time"] = f"{time.time() - start_time:.3f}s"
                response_details["sensors_found"] = bulk_update_count
                return response_details
        
        # Step 4: If we need individual processing, fetch sensors
        if needs_individual_processing or not update_data:
            query_start = time.time()
            
            # Only fetch fields we actually need for individual processing
            field_list = ['id', 'unique_identifier', 'processes', 'process_ids']
            if update_data and not bulk_update_count:
                # We still need to do individual field updates
                field_list.extend(['sensor_label', 'sensor_description'])
                
            sensors_data = list(sensors_qs.only(*field_list))
            
            if not sensors_data:
                return {"error": "No sensors found matching criteria"}
                
            response_details["performance_metrics"]["query_time"] = f"{time.time() - query_start:.3f}s"
            response_details["sensors_found"] = len(sensors_data)
            
            # Track invalid identifiers for individual strategy
            if selection_strategy == 'individual':
                found_identifiers = {s.unique_identifier for s in sensors_data}
                invalid_identifiers = set(unique_identifiers) - found_identifiers
                response_details['invalid_identifiers'] = list(invalid_identifiers)
        
        # Step 5: Process individual sensor updates (only if needed)
        if needs_individual_processing:
            with transaction.atomic():
                created_count, deleted_count = _process_individual_sensors(
                    self, sensors_data, update_data if not bulk_update_count else None,
                    new_process_data, delete_list, selection_strategy, response_details
                )
                
                response_details["created_processes"] = created_count
                response_details["deleted_processes"] = deleted_count
                
                # Add bulk update count if we did that first
                if bulk_update_count:
                    response_details["updated_items"] = bulk_update_count
        
        response_details["performance_metrics"]["total_time"] = f"{time.time() - start_time:.3f}s"
        return response_details
        
    except Exception as e:
        self.update_state(state="FAILURE", meta={"exc_message": traceback.format_exc()})
        return {"error": str(e), "traceback": traceback.format_exc()}


def _build_sensor_queryset_optimized(selection_strategy, batch_location=None, batch_id=None, 
                                    wafer_ids=None, sensor_ids=None, unique_identifiers=None):
    """Build optimized queryset with minimal overhead."""
    
    if selection_strategy == 'batch':
        # Batch-based selection with compound index usage
        queryset = Sensor.objects.filter(
            batch_location=batch_location, 
            batch_id=batch_id
        )
        
        # Apply wafer ID filters if provided (use single combined filter)
        if wafer_ids:
            expanded_wafer_ids = _expand_id_ranges(wafer_ids)
            queryset = queryset.filter(wafer_id__in=expanded_wafer_ids)
            
        # Apply sensor ID filters if provided  
        if sensor_ids:
            expanded_sensor_ids = _expand_id_ranges(sensor_ids)
            queryset = queryset.filter(sensor_id__in=expanded_sensor_ids)
            
    else:  # individual strategy
        # Individual unique identifier selection (uses unique index)
        queryset = Sensor.objects.filter(unique_identifier__in=unique_identifiers)
    
    return queryset


def _expand_id_ranges(id_list):
    """
    Expand ID ranges like ['1-3', '8', '9-12'] into [1, 2, 3, 8, 9, 10, 11, 12].
    OPTIMIZED: Early exit and type checking.
    """
    if not id_list:
        return []
        
    expanded = []
    for item in id_list:
        if isinstance(item, str) and '-' in item:
            # Handle range like '1-3'
            try:
                start, end = map(int, item.split('-', 1))  # limit split to 1
                expanded.extend(range(start, end + 1))
            except (ValueError, TypeError):
                # Invalid range format, treat as single item
                try:
                    expanded.append(int(item))
                except (ValueError, TypeError):
                    continue  # Skip invalid items
        else:
            # Handle single ID
            try:
                expanded.append(int(item))
            except (ValueError, TypeError):
                continue  # Skip invalid items
    return expanded


def _perform_optimized_bulk_update(queryset, update_data, selection_strategy):
    """
    Perform highly optimized bulk field updates.
    WITH CharField sensor_label, this can now handle ALL common field updates in bulk!
    """
    
    if selection_strategy == 'batch':
        # For batch updates, we can update virtually all fields in bulk
        allowed_fields = {
            'batch_label', 'batch_description', 'wafer_label', 'wafer_description',
            'wafer_design_id', 'sensor_description', 'sensor_label'  # NOW BULK-UPDATABLE!
        }
    else:
        # For individual updates, focus on sensor-specific fields
        allowed_fields = {'sensor_description', 'sensor_label'}  # BOTH NOW BULK-UPDATABLE!
    
    # Build bulk update dictionary with validation
    bulk_update_fields = {}
    for field, value in update_data.items():
        # Handle legacy 'label' key mapping to 'sensor_label'
        if field == 'label':
            field = 'sensor_label'
            
        if field in allowed_fields and hasattr(Sensor, field):
            bulk_update_fields[field] = value
    
    # Perform single bulk update for maximum efficiency
    if bulk_update_fields:
        return queryset.update(**bulk_update_fields)
    return 0


def _process_individual_sensors(task_instance, sensors_data, update_data, new_process_data, 
                              delete_list, selection_strategy, response_details):
    """
    Process individual sensor updates ONLY when bulk operations aren't sufficient.
    OPTIMIZED: Reduced to only handle process operations + any remaining field updates.
    """
    
    created_count = 0
    deleted_count = 0
    total_sensors = len(sensors_data)
    
    # Pre-validate process data once (not per sensor)
    valid_process_files = {}
    if new_process_data:
        valid_process_ids = [p['process_id'] for p in new_process_data if p.get('process_id')]
        if valid_process_ids:  # Only query if we have IDs
            valid_process_files = {
                pf.process_id: pf
                for pf in ProcessFile.objects.filter(process_id__in=valid_process_ids)
            }
    
    # Batch individual field updates if they weren't handled in bulk
    sensors_to_save = []
    if update_data:
        for sensor in sensors_data:
            sensor_updated = False
            
            # Handle any remaining field updates not covered by bulk
            for field, value in update_data.items():
                if field == 'label':
                    field = 'sensor_label'
                    
                if hasattr(sensor, field):
                    setattr(sensor, field, value)
                    sensor_updated = True
            
            if sensor_updated:
                sensors_to_save.append(sensor)
        
        # Bulk save all field-updated sensors at once
        if sensors_to_save:
            Sensor.objects.bulk_update(sensors_to_save, 
                                     ['sensor_label', 'sensor_description'], 
                                     batch_size=1000)
            response_details["updated_items"] = len(sensors_to_save)
    
    # Process operations (these require individual processing due to embedded arrays)
    for idx, sensor in enumerate(sensors_data, start=1):
        try:
            # Process additions
            if new_process_data:
                for process_entry in new_process_data:
                    process_id = process_entry.get('process_id')
                    description = process_entry.get('description')
                    timestamp = process_entry.get('timestamp')
                    
                    if not process_id or process_id not in valid_process_files:
                        continue
                    if not description or not timestamp:
                        continue
                        
                    timestamp = ensure_datetime(timestamp)
                    
                    if process_id not in sensor.process_ids:
                        sensor.add_processes(process_id, description, timestamp)
                        created_count += 1
            
            # Process deletions
            if delete_list:
                for process_entry in delete_list:
                    process_id = process_entry.get('process_id')
                    if process_id and process_id in sensor.process_ids:
                        sensor.remove_process(process_id)
                        deleted_count += 1
        
        except Exception as e:
            response_details["errors"].append({
                "sensor": sensor.unique_identifier,
                "error": str(e)
            })
        
        # Update progress every 100 sensors (less frequent for better performance)
        if idx % 100 == 0 or idx == total_sensors:
            task_instance.update_state(
                state="PROGRESS",
                meta={
                    "current": idx,
                    "total": total_sensors,
                    "percent": round((idx / total_sensors) * 100, 2),
                    "strategy": selection_strategy,
                    "updated_items": response_details.get("updated_items", 0),
                    "created_processes": created_count,
                    "deleted_processes": deleted_count,
                    "errors": response_details["errors"][-3:],  # Show last 3 errors
                }
            )
    
    return created_count, deleted_count


