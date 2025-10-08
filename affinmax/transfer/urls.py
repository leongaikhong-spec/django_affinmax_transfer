from django.urls import path
from . import views

urlpatterns = [
    path('create_mobile/', views.create_mobile, name="create_mobile"),
    path("make_transfers/", views.trigger, name="make_transfers"),
    path("log/", views.log, name="log"),
    path("add/", views.add_transaction_status, name="add_transaction_status"),
]
