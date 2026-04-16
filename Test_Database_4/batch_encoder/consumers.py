# batch_encoder/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from celery import current_app
import logging

logger = logging.getLogger(__name__)

class ProgressConsumer(AsyncWebsocketConsumer):
    """ 
    Task-specific consumer
    Subscribed clients only see updates for the given task_id.
    """
    async def connect(self):
        self.task_id = self.scope['url_route']['kwargs']['task_id']
        self.group_name = f"task_{self.task_id}"

        # Join task-specific group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        # Leave group
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # Receive message from group
    async def progress_update(self, event):
        await self.send(text_data=json.dumps(event["data"]))

    
# batch_encoder/consumers.py
class GlobalTaskConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("global_tasks", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("global_tasks", self.channel_name)

    async def task_update(self, event):
        await self.send(text_data=json.dumps(event["data"]))
        
class UserTaskConsumer(AsyncWebsocketConsumer):
    """ 
    User-specific global consumer.
    Subscribed clients only see upfates for their own tasks, even when they navigate across pages.
    """
    async def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close()
            return
        
        self.user_group_name = f"user_{user.id}_tasks"
        
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.accept()
        
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.user_group_name, self.channel_name)
        
    async def task_update(self, event):
        """ 
        Receive updates about any of this user's tasks.
        """
        await self.send(text_data=json.dumps(event["data"]))
        
        
# ======= DASHBOARD CONSUMERS (WEBSOCKET) ==================
class DashboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Join dashboard group for potential future updates
        await self.channel_layer.group_add("dashboard", self.channel_name)
        await self.accept()
        
        # Send initial dashboard data immediately upon connection
        await self.send_dashboard_data()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("dashboard", self.channel_name)

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'refresh_dashboard':
                await self.send_dashboard_data()
            elif message_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))

    async def send_dashboard_data(self):
        """Fetch and send all dashboard data at once"""
        try:
            # Fetch all data concurrently using database_sync_to_async
            core_stats = await self.get_core_stats()
            recent_activity = await self.get_recent_activity()
            latest_batches = await self.get_latest_batches()
            processes_stats = await self.get_processes()
            
            # Send combined data
            dashboard_data = {
                'type': 'dashboard_data',
                'data': {
                    'core_stats': core_stats,
                    'recent_activity': recent_activity,
                    'latest_batches': latest_batches,
                    'processes_stats': processes_stats
                },
                'timestamp': timezone.now().isoformat()
            }
            
            await self.send(text_data=json.dumps(dashboard_data, default=str))
            
        except Exception as e:
            logger.error(f"Error fetching dashboard data: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Failed to fetch dashboard data: {str(e)}'
            }))

    @database_sync_to_async
    def get_core_stats(self):
        """Get core production statistics - MongoDB/Djongo compatible"""
        try:
            from .models import Sensor
            from process_encoder.models import ProcessFile
            # Core metrics using basic queries
            total_sensors = Sensor.objects.count()
            total_processes = ProcessFile.objects.count()
            
            # Get unique batches by iterating (MongoDB compatible)
            unique_batches = set()
            unique_wafers = set()
            active_locations = set()
            
            for sensor in Sensor.objects.only('batch_location', 'batch_id', 'wafer_id'):
                batch_key = (sensor.batch_location, sensor.batch_id)
                unique_batches.add(batch_key)
                unique_wafers.add((sensor.batch_location, sensor.batch_id, sensor.wafer_id))
                active_locations.add(sensor.batch_location)
            
            total_batches = len(unique_batches)
            total_wafers = len(unique_wafers)
            
            # Calculate average sensors per batch
            if unique_batches:
                batch_counts = defaultdict(int)
                for sensor in Sensor.objects.only('batch_location', 'batch_id'):
                    batch_key = (sensor.batch_location, sensor.batch_id)
                    batch_counts[batch_key] += 1
                avg_sensors_per_batch = sum(batch_counts.values()) / len(batch_counts)
            else:
                avg_sensors_per_batch = 0
            
            # Weekly growth calculation
            week_ago = timezone.now() - timedelta(days=7)
            sensors_this_week = Sensor.objects.filter(
                last_process_timestamp__gte=week_ago
            ).count()
            
            # Count unique batches this week
            batches_this_week_set = set()
            for sensor in Sensor.objects.filter(last_process_timestamp__gte=week_ago).only('batch_location', 'batch_id'):
                batches_this_week_set.add((sensor.batch_location, sensor.batch_id))
            batches_this_week = len(batches_this_week_set)
            
            return {
                'total_sensors': total_sensors,
                'total_batches': total_batches,
                'total_wafers': total_wafers,
                'total_processes': total_processes,
                'avg_sensors_per_batch': round(avg_sensors_per_batch, 1),
                'active_locations': len(active_locations),
                'sensors_this_week': sensors_this_week,
                'batches_this_week': batches_this_week
            }
            
        except Exception as e:
            logger.error(f"Error fetching core stats: {str(e)}")
            raise

    @database_sync_to_async
    def get_recent_activity(self):
        """Get recent activity metrics - MongoDB/Djongo compatible"""
        try:
            from .models import Sensor
            # Find latest batch by iterating through sensors
            latest_batch = None
            latest_timestamp = None
            
            for sensor in Sensor.objects.only('batch_location', 'batch_id', 'batch_label', 'last_process_timestamp'):
                if sensor.last_process_timestamp:
                    if not latest_timestamp or sensor.last_process_timestamp > latest_timestamp:
                        latest_timestamp = sensor.last_process_timestamp
                        latest_batch = {
                            'batch_location': sensor.batch_location,
                            'batch_id': sensor.batch_id,
                            'batch_label': sensor.batch_label,
                            'latest_process': sensor.last_process_timestamp
                        }
            
            # Find last process applied globally
            last_process_sensor = None
            last_process_time = None
            
            for sensor in Sensor.objects.exclude(last_process_timestamp__isnull=True).only('unique_identifier', 'processes', 'last_process_timestamp'):
                if sensor.last_process_timestamp:
                    if not last_process_time or sensor.last_process_timestamp > last_process_time:
                        last_process_time = sensor.last_process_timestamp
                        last_process_sensor = sensor
            
            last_process_info = None
            if last_process_sensor and last_process_sensor.processes:
                # Get the most recent process from embedded processes
                most_recent_process = max(
                    last_process_sensor.processes, 
                    key=lambda p: p['timestamp']
                )
                last_process_info = {
                    'process_id': most_recent_process['process_id'],
                    'timestamp': last_process_sensor.last_process_timestamp,
                    'sensor_id': last_process_sensor.unique_identifier
                }
            
            # Today's activity
            today = timezone.now().date()
            today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
            
            today_batches_set = set()
            for sensor in Sensor.objects.filter(last_process_timestamp__gte=today_start).only('batch_location', 'batch_id'):
                today_batches_set.add((sensor.batch_location, sensor.batch_id))
            today_batches = len(today_batches_set)
            
            # Active Celery tasks
            try:
                inspect = current_app.control.inspect()
                active_tasks = inspect.active()
                total_active = sum(len(tasks) for tasks in active_tasks.values()) if active_tasks else 0
            except:
                total_active = 0
            
            return {
                'last_batch': {
                    'identifier': f"{latest_batch['batch_location']}{latest_batch['batch_id']:03d}" if latest_batch else None,
                    'label': latest_batch['batch_label'] if latest_batch else None,
                    'timestamp': latest_batch['latest_process'] if latest_batch else None
                } if latest_batch else None,
                'last_process': last_process_info,
                'today_batches': today_batches,
                'active_celery_tasks': total_active
            }
            
        except Exception as e:
            logger.error(f"Error fetching recent activity: {str(e)}")
            raise

    @database_sync_to_async
    def get_latest_batches(self):
        """Get the latest 5 distinct batches"""
        try:
            from .models import Sensor
            # Query only the needed fields, sorted by timestamp
            queryset = (
                Sensor.objects.only(
                    'batch_location',
                    'batch_id',
                    'batch_label',
                    'batch_description',
                    'total_wafers',
                    'total_sensors',
                    'last_process_timestamp'
                )
                .order_by('-last_process_timestamp')
            )

            seen_batches = set()
            batches = []

            # Deduplicate in Python
            for sensor in queryset:
                batch_key = (sensor.batch_location, sensor.batch_id)
                if batch_key not in seen_batches:
                    seen_batches.add(batch_key)
                    total_sensors = sensor.total_wafers * sensor.total_sensors

                    batches.append({
                        'batch_location': sensor.batch_location,
                        'batch_id': sensor.batch_id,
                        'batch_label': sensor.batch_label or '',
                        'batch_description': sensor.batch_description or '',
                        'total_wafers': sensor.total_wafers,
                        'sensors_per_wafer': sensor.total_sensors,
                        'total_sensors': total_sensors,
                        'last_process_timestamp': sensor.last_process_timestamp,
                    })

                if len(batches) == 5:
                    break  # stop once we have 5

            return batches
            
        except Exception as e:
            logger.error(f"Error fetching latest batches: {str(e)}")
            raise
        
    @database_sync_to_async
    def get_processes(self):
        """Get process statistics - MongoDB/Djongo compatible"""
        try:
            from .models import Sensor
            from process_encoder.models import ProcessFile
            
            # Get total processes from ProcessFile model (same as in get_core_stats)
            total_processes = ProcessFile.objects.count()
            
            # Initialize counters
            process_counter = Counter()
            sensors_with_processes = 0
            total_process_applications = 0
            batch_process_stats = defaultdict(lambda: {'sensors': 0, 'processes': Counter()})
            
            # Iterate through all sensors to analyze embedded processes
            for sensor in Sensor.objects.only('batch_location', 'batch_id', 'processes'):
                batch_key = f"{sensor.batch_location}{sensor.batch_id:03d}"
                
                if sensor.processes:
                    sensors_with_processes += 1
                    sensor_process_count = len(sensor.processes)
                    total_process_applications += sensor_process_count
                    
                    # Update batch stats
                    batch_process_stats[batch_key]['sensors'] += 1
                    
                    # Count each process application
                    for process in sensor.processes:
                        process_id = process.get('process_id')
                        if process_id:
                            process_counter[process_id] += 1
                            batch_process_stats[batch_key]['processes'][process_id] += 1
            
            # Calculate average processes per sensor
            avg_processes_per_sensor = 0
            if sensors_with_processes > 0:
                avg_processes_per_sensor = round(total_process_applications / sensors_with_processes, 2)
            
            # Get most applied processes (top 5)
            most_applied_processes = [
                {
                    'process_id': process_id,
                    'applications': count,
                    'percentage': round((count / total_process_applications) * 100, 1) if total_process_applications > 0 else 0
                }
                for process_id, count in process_counter.most_common(5)
            ]
            
            # Get batch process diversity (batches with most diverse processes)
            batch_diversity = []
            for batch_key, stats in batch_process_stats.items():
                unique_processes = len(stats['processes'])
                if unique_processes > 0:
                    batch_diversity.append({
                        'batch_identifier': batch_key,
                        'unique_processes': unique_processes,
                        'total_applications': sum(stats['processes'].values()),
                        'sensors_processed': stats['sensors']
                    })
            
            # Sort by unique processes descending, take top 3
            batch_diversity.sort(key=lambda x: x['unique_processes'], reverse=True)
            top_diverse_batches = batch_diversity[:3]
            
            return {
                'total_processes': total_processes,
                'total_process_applications': total_process_applications,
                'sensors_with_processes': sensors_with_processes,
                'avg_processes_per_sensor': avg_processes_per_sensor,
                'most_applied_processes': most_applied_processes,
                'top_diverse_batches': top_diverse_batches,
                'unique_processes_applied': len(process_counter)
            }
            
        except Exception as e:
            logger.error(f"Error fetching process stats: {str(e)}")
            raise

    # Method to handle dashboard updates from external sources
    async def dashboard_update(self, event):
        """Handle dashboard update messages from the group"""
        await self.send(text_data=json.dumps(event["data"]))

