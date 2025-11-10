from django.apps import AppConfig


class TransferConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'transfer'
    
    def ready(self):
        """Django 应用启动时自动执行"""
        import os
        import threading
        
        # 避免在 reload 时重复启动（仅用于 Django 开发服务器）
        # uvicorn 不需要这个检查
        run_main = os.environ.get('RUN_MAIN')
        if run_main is not None and run_main != 'true':
            return
        
        # 使用线程锁确保只启动一次
        if not hasattr(self.__class__, '_telegram_bot_started'):
            self.__class__._telegram_bot_started = True
        else:
            return
        
        # 自动启动 Telegram Bot 轮询
        try:
            from .telegram_bot import telegram_notifier
            
            telegram_notifier.start_polling()
            
            print("🚀 Telegram Bot polling started automatically")
            
        except Exception as e:
            print(f"⚠️ Failed to start Telegram Bot polling: {e}")
            import traceback
            traceback.print_exc()
