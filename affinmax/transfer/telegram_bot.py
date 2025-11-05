"""
Telegram Bot 通知模块（Polling 轮询模式）
包含：
1. 发送通知消息（错误、余额不足）
2. 轮询模式处理按钮点击（不需要 HTTPS webhook）

使用方法：
- 发送消息: from transfer.telegram_bot import telegram_notifier
- 启动轮询: python3 manage.py start_telegram_bot
"""
import requests
import json
import time
import threading
from django.conf import settings
from datetime import datetime


class TelegramNotifier:
    """Telegram 通知器（轮询模式，支持按钮点击处理）"""
    
    def __init__(self):
        self.bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        self.chat_id = getattr(settings, 'TELEGRAM_CHAT_ID', None)
        self.enabled = bool(self.bot_token and self.chat_id)
        self.last_update_id = 0
        self.polling_thread = None
        self.polling_active = False
        
        if not self.enabled:
            print("⚠️ Telegram notifications disabled: Please configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        else:
            print(f"[Telegram] Initialized (Polling Mode) - Chat ID: {self.chat_id}")
            print(f"[Telegram] Ready to handle button clicks via polling")
    
    def send_message(self, message, parse_mode='HTML', reply_markup=None):
        """
        发送消息到 Telegram
        
        Args:
            message: 消息内容
            parse_mode: 解析模式 ('HTML' 或 'Markdown')
            reply_markup: 按钮布局（InlineKeyboardMarkup）
        
        Returns:
            bool: 是否发送成功
        """
        if not self.enabled:
            print("⚠️ Telegram notifications disabled, skipping send")
            return False
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': parse_mode
        }
        
        # 添加按钮
        if reply_markup:
            payload['reply_markup'] = reply_markup
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            print("✅ Telegram message sent successfully")
            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ Telegram message sending failed: {e}")
            return False
    
    def send_error_notification(self, device, error_data):
        """
        发送错误通知（带 Activate/Deactivate 按钮）
        
        Args:
            device: 设备号码
            error_data: 错误数据字典
        """
        status = error_data.get('status', 'unknown')
        tran_id = error_data.get('tran_id', 'N/A')
        group_id = error_data.get('group_id', 'N/A')
        message_text = error_data.get('message', 'Unknown error')
        error_message = error_data.get('errorMessage', 'No details')
        current_balance = error_data.get('current_balance', 'N/A')
        required_amount = error_data.get('required_amount', 'N/A')
        
        # 检查错误类型
        error_lower = error_message.lower()
        
        # 1. 余额不足错误
        is_insufficient_balance = 'balance less than transfer amount' in error_lower

        # 2. 无效的银行或账号
        is_invalid_bank_account = 'invalid bank or account number' in error_lower
        
        # 3. 名字不匹配（包含 Expected 和 Actual）
        is_name_mismatch = ('expected' in error_lower and 'actual' in error_lower)
        
        # 根据错误类型选择格式
        if is_insufficient_balance:
            # 💰 余额不足格式
            notification = f"""
💰 <b>Balance Insufficient</b>

<b>Error occurred:</b> {self._get_current_time()}
<b>Transaction ID:</b> {tran_id}
<b>Group ID:</b> {group_id}
<b>Phone number:</b> {device}
<b>Current balance:</b> {current_balance}
<b>Total Process Amount:</b> {required_amount}
<b>Error detail:</b> {error_message}

⚠️ <b>Device auto-deactivated</b>
"""
        elif is_invalid_bank_account:
            # 🏦 无效银行/账号格式
            notification = f"""
🏦 <b>Invalid Bank or Account Number</b>

<b>Error occurred:</b> {self._get_current_time()}
<b>Transaction ID:</b> {tran_id}
<b>Group ID:</b> {group_id}
<b>Phone number:</b> {device}
<b>Status:</b> {status}
<b>Error detail:</b> {error_message}

ℹ️ <b>Device remains active</b>
"""
        elif is_name_mismatch:
            # 👤 名字不匹配格式
            notification = f"""
👤 <b>Name Mismatch Error</b>

<b>Error occurred:</b> {self._get_current_time()}
<b>Transaction ID:</b> {tran_id}
<b>Group ID:</b> {group_id}
<b>Phone number:</b> {device}
<b>Status:</b> {status}
<b>Error detail:</b> {error_message}

ℹ️ <b>Device remains active</b>
"""
        else:
            # 🚨 通用错误格式
            notification = f"""
🚨 <b>Transaction Process Error</b>

<b>Error occurred:</b> {self._get_current_time()}
<b>Transaction ID:</b> {tran_id}
<b>Group ID:</b> {group_id}
<b>Phone number:</b> {device}
<b>Status:</b> {status}
<b>Error detail:</b> {error_message}

⚠️ <b>Device auto-deactivated</b>
"""
        
        # 创建 Inline Keyboard 按钮
        inline_keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Activate",
                        "callback_data": f"activate_{device}"
                    },
                    {
                        "text": "❌ Deactivate",
                        "callback_data": f"deactivate_{device}"
                    }
                ]
            ]
        }
        
        return self.send_message(notification, reply_markup=inline_keyboard)
    
    def get_updates(self, offset=None, timeout=30):
        """获取 Telegram 更新（轮询）"""
        if not self.enabled:
            return None
            
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        params = {
            'timeout': timeout,
            'allowed_updates': ['callback_query']
        }
        if offset:
            params['offset'] = offset
        
        try:
            response = requests.get(url, params=params, timeout=timeout + 5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ Failed to get updates: {e}")
            return None
    
    def answer_callback_query(self, callback_query_id, text):
        """回复 callback query（显示提示消息）"""
        if not self.enabled:
            return False
            
        url = f"https://api.telegram.org/bot{self.bot_token}/answerCallbackQuery"
        payload = {
            'callback_query_id': callback_query_id,
            'text': text,
            'show_alert': False
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"❌ answer_callback_query failed: {e}")
            return False
    
    def edit_message_text(self, chat_id, message_id, new_text):
        """编辑消息内容"""
        if not self.enabled:
            return False
            
        url = f"https://api.telegram.org/bot{self.bot_token}/editMessageText"
        payload = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': new_text,
            'parse_mode': 'HTML'
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"❌ edit_message_text failed: {e}")
            return False
    
    def process_callback_query(self, callback_query):
        """处理按钮点击"""
        from .models import MobileList
        
        callback_data = callback_query.get('data', '')
        callback_id = callback_query.get('id', '')
        message = callback_query.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        message_id = message.get('message_id')
        
        # 获取点击者信息
        user = callback_query.get('from', {})
        user_id = user.get('id', 'Unknown')
        username = user.get('username', '')
        first_name = user.get('first_name', '')
        last_name = user.get('last_name', '')
        
        # 构建点击者显示名称
        if username:
            user_display = f"@{username}"
        elif first_name or last_name:
            user_display = f"{first_name} {last_name}".strip()
        else:
            user_display = f"User ID: {user_id}"
        
        print(f"[{datetime.now()}] Processing callback: {callback_data} from {user_display}")
        
        # 解析 callback_data: "activate_0123456789" 或 "deactivate_0123456789"
        parts = callback_data.split('_', 1)
        if len(parts) != 2:
            print(f"❌ Invalid callback data: {callback_data}")
            self.answer_callback_query(callback_id, "❌ 无效的操作")
            return
        
        action = parts[0]  # "activate" 或 "deactivate"
        device = parts[1]   # 设备号码
        
        # 查找设备
        try:
            mobile = MobileList.objects.get(device=device)
        except MobileList.DoesNotExist:
            print(f"❌ Device not found: {device}")
            self.answer_callback_query(callback_id, f"❌ 设备 {device} 未找到")
            return
        
        # 执行操作
        if action == "activate":
            mobile.is_activated = True
            mobile.save()
            new_message = f"✅ <b>Device {device} activated</b>\n👤 <b>Activated by:</b> {user_display}\n⏰ <b>Time:</b> {self._get_current_time()}"
            answer_text = f"✅ Device {device} activated"
            print(f"✅ Device {device} activated by {user_display}")
        elif action == "deactivate":
            mobile.is_activated = False
            mobile.save()
            new_message = f"❌ <b>Device {device} deactivated</b>\n👤 <b>Deactivated by:</b> {user_display}\n⏰ <b>Time:</b> {self._get_current_time()}"
            answer_text = f"❌ Device {device} deactivated"
            print(f"❌ Device {device} deactivated by {user_display}")
        else:
            print(f"❌ Invalid action: {action}")
            self.answer_callback_query(callback_id, "❌ Invalid operation")
            return
        
        # 回复 callback query（弹出提示）
        self.answer_callback_query(callback_id, answer_text)
        
        # 发送一条新消息（不编辑原消息）
        self.send_message(new_message)
    
    def start_polling(self):
        """启动轮询（在后台线程运行）"""
        if not self.enabled:
            print("⚠️ Telegram polling disabled")
            return
        
        if self.polling_active:
            print("⚠️ Telegram polling already running")
            return
        
        self.polling_active = True
        self.polling_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.polling_thread.start()
        print("✅ Telegram polling started in background thread")
    
    def stop_polling(self):
        """停止轮询"""
        self.polling_active = False
        if self.polling_thread:
            self.polling_thread.join(timeout=5)
        print("✅ Telegram polling stopped")
    
    def _polling_loop(self):
        """轮询主循环（内部方法）"""
        print("=" * 60)
        print("🤖 Telegram Bot Polling Mode Started")
        print("=" * 60)
        print(f"Bot Token: {self.bot_token[:10]}...{self.bot_token[-10:]}")
        print(f"Chat ID: {self.chat_id}")
        print("=" * 60)
        print("\n✅ Listening for button clicks...\n")
        
        while self.polling_active:
            try:
                # 获取更新
                offset = self.last_update_id + 1 if self.last_update_id > 0 else None
                result = self.get_updates(offset, timeout=30)
                
                if result and result.get('ok'):
                    updates = result.get('result', [])
                    
                    for update in updates:
                        update_id = update.get('update_id')
                        callback_query = update.get('callback_query')
                        
                        # 更新 last_update_id
                        if update_id > self.last_update_id:
                            self.last_update_id = update_id
                        
                        # 处理 callback_query
                        if callback_query:
                            try:
                                self.process_callback_query(callback_query)
                            except Exception as e:
                                print(f"❌ Error processing callback: {e}")
                                import traceback
                                traceback.print_exc()
                
                # 短暂休眠
                time.sleep(1)
                
            except KeyboardInterrupt:
                print("\n⚠️  Received interrupt signal, stopping...")
                break
            except Exception as e:
                print(f"❌ Error in polling loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(5)  # 出错后等待5秒再继续
        
        print("🛑 Telegram polling loop ended")
    
    @staticmethod
    def _get_current_time():
        """获取当前时间字符串"""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# 创建全局实例
telegram_notifier = TelegramNotifier()
