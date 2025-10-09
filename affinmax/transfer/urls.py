from django.urls import path
from . import views

urlpatterns = [
    path('create_mobile/', views.create_mobile, name="Create Mobile"),
    path("make_transactions/", views.trigger, name="Make Transactions"),
    path("log/", views.log, name="Log"),
    path("add_transaction_status/", views.add_transaction_status, name="Add Transaction Status"),
    path('update_group_success_amount/', views.update_group_success_amount, name="Update Group Success Amount"),
    path('update_current_balance/', views.update_current_balance, name="Update Current Balance"),
    path('update_is_busy/', views.update_is_busy, name="Update Is Busy"),
    path('assign_pending_orders/', views.assign_pending_orders, name="Assign Pending Orders"),
]
