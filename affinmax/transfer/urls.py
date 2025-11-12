from django.urls import path
from . import views


urlpatterns = [
    path('script/create_mobile/', views.create_mobile, name="Create Mobile"),
    path("script/add_transaction_status/", views.add_transaction_status, name="Add Transaction Status"),
    path("script/make_transactions/", views.trigger, name="Make Transactions"),
    
    path("backend/log/", views.log, name="Log"),
    path('backend/update_group_success_amount/', views.update_group_success_amount, name="Update Group Success Amount"),
    path('backend/update_current_balance/', views.update_current_balance, name="Update Current Balance"),
    path('backend/update_is_busy/', views.update_is_busy, name="Update Is Busy"),
    path('backend/assign_pending_orders/', views.assign_pending_orders, name="Assign Pending Orders"),
    path('backend/upload_s3/', views.upload_s3, name="Upload to S3"),
    path('backend/test_telegram/', views.test_telegram, name="Test Telegram"),
    path('backend/send_callback/', views.send_callback_to_client, name="Send Callback"),
]
