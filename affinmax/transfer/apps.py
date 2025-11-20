from django.apps import AppConfig


class TransferConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'transfer'
    
    def ready(self):
        """Django 应用启动时自动执行"""
        import os
        import sys
        import threading
        
        # 避免在 reload 时重复启动（仅用于 Django 开发服务器）
        # uvicorn 不需要这个检查
        run_main = os.environ.get('RUN_MAIN')
        if run_main is not None and run_main != 'true':
            return
        
        # 🚫 如果在 Celery Worker 进程中，跳过所有服务启动
        if 'celery' in sys.argv[0] or any('celery' in arg for arg in sys.argv):
            print("ℹ️  Running in Celery Worker, skipping service startup")
            return
        
        # 使用线程锁确保只启动一次
        if not hasattr(self.__class__, '_services_started'):
            self.__class__._services_started = True
        else:
            return
        
        # 主进程：启动 Telegram Bot 和 Celery Worker
        try:
            from .telegram_bot import telegram_notifier
            telegram_notifier.start_polling()
            print("🚀 Telegram Bot polling started")
        except Exception as e:
            print(f"⚠️ Failed to start Telegram Bot: {e}")
        
        try:
            from .celery_worker import start_celery_worker_thread
            start_celery_worker_thread()
            print("🚀 Celery Worker started")
        except Exception as e:
            print(f"⚠️ Failed to start Celery Worker: {e}")
            import traceback
            traceback.print_exc()
