from django.urls import path
from . import views

urlpatterns = [
    path('create_mobile/', views.create_mobile, name="Create Mobile"),
    path("make_transfers/", views.trigger, name="Make Transfers"),
    path("log/", views.log, name="Log"),
    path("add/", views.add_transaction_status, name="Add Transaction Status"),
    path('update_group_success_amount/', views.update_group_success_amount, name="Update Group Success Amount"),
    path('update_current_balance/', views.update_current_balance, name="Update Current Balance"),
]
