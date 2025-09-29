from django.urls import path
from . import views

urlpatterns = [
    path("trigger/<str:pn>/", views.trigger, name="trigger"),
    path("run-script/", views.run_script, name="run_script"),
    path("log/", views.receive_log, name="receive_log"),
]
