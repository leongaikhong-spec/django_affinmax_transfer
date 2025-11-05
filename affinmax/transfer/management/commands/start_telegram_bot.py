"""
Django Management Command: 启动 Telegram Bot 轮询模式
用于处理按钮点击等交互事件

运行方式：
    python3 manage.py start_telegram_bot
"""
from django.core.management.base import BaseCommand
from transfer.telegram_bot import telegram_notifier


class Command(BaseCommand):
    help = '启动 Telegram Bot 轮询模式，处理按钮点击事件'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🤖 Starting Telegram Bot (Polling Mode)...'))
        
        try:
            # 启动轮询
            telegram_notifier.start_polling()
            
            # 保持主线程运行
            self.stdout.write(self.style.SUCCESS('✅ Telegram Bot is now running'))
            self.stdout.write(self.style.WARNING('Press Ctrl+C to stop'))
            
            # 无限循环，等待中断
            import time
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\n⚠️  Stopping Telegram Bot...'))
            telegram_notifier.stop_polling()
            self.stdout.write(self.style.SUCCESS('✅ Telegram Bot stopped'))
