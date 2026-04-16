# batch_encoder/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/progress/(?P<task_id>[\w-]+)/$", consumers.ProgressConsumer.as_asgi()),
    re_path(r"ws/global-tasks/$", consumers.GlobalTaskConsumer.as_asgi()),
    re_path(r"ws/dashboard/$", consumers.DashboardConsumer.as_asgi()),
]
