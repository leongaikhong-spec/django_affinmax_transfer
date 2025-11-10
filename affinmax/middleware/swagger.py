# swagger.py
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

def schema_view_with_dynamic_host(request=None):
    host = request.get_host() if request else "47.130.115.16:9001"
    schema_view = get_schema_view(
        openapi.Info(
            title="My API",
            default_version='v1',
        ),
        public=True,
        permission_classes=(permissions.AllowAny,),
        url=f"http://{host}",
    )
    return schema_view
