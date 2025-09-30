from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/(?P<pn>\w+)/$", consumers.ScriptConsumer.as_asgi()),
]
