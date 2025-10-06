from django.urls import path
from . import views

urlpatterns = [
    path('create_mobile/', views.create_mobile, name="create_mobile"),
    path("make_transfers/<str:pn>/", views.trigger, name="make_transfers"),
]
