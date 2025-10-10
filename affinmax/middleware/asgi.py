import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "middleware.settings")
import django
django.setup()
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import transfer.routing


application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            transfer.routing.websocket_urlpatterns
        )
    ),
})
