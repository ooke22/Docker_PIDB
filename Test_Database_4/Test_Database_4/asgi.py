"""
ASGI config for Test_Database_4 project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/asgi/
"""

import os
import django
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
import batch_encoder.routing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Test_Database_4.settings")
django.setup()

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(batch_encoder.routing.websocket_urlpatterns)
    ),
})