"""
Telegram Bot 通知模块
用于发送错误通知和交易状态到 Telegram
"""
import requests
import json
from django.conf import settings


class TelegramNotifier:
    """Telegram 通知器"""
    
    def __init__(self):
        self.bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        self.chat_id = getattr(settings, 'TELEGRAM_CHAT_ID', None)
        # 确保 topic_id 为空字符串或 None 时不使用 Topic 模式
        topic_id_raw = getattr(settings, 'TELEGRAM_TOPIC_ID', None)
        self.topic_id = topic_id_raw if topic_id_raw and str(topic_id_raw).strip() else None
        self.enabled = bool(self.bot_token and self.chat_id)
        
        if not self.enabled:
            print("⚠️ Telegram 通知未启用：请在 settings.py 中配置 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID")
        
        print(f"[Telegram] 初始化完成 - Chat ID: {self.chat_id}, Topic: {'启用' if self.topic_id else '禁用'}")
    
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
            print("⚠️ Telegram 通知未启用，跳过发送")
            return False
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': parse_mode
        }
        
        # 如果设置了 Topic ID，添加到 payload
        # 注意：Topic 模式下可能不支持 reply_markup，根据需要调整
        if self.topic_id:
            payload['message_thread_id'] = int(self.topic_id)
            print(f"⚠️ Topic 模式：message_thread_id = {self.topic_id}")
        
        # 添加按钮（仅在非 Topic 模式或 Topic 支持按钮时）
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
        message_text = error_data.get('message', 'Unknown error')
        error_message = error_data.get('errorMessage', 'No details')
        
        # 构建通知消息
        notification = f"""
🚨 <b>Transactions Process Error</b>

⏰ <b>Error occurred:</b> {self._get_current_time()}
🆔 <b>Transaction ID:</b> {tran_id}
📱 <b>Phone number  :</b> {device}
⚠️ <b>Status        :</b> {status}
🔍 <b>Error detail  :</b> {error_message}

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
    
    def send_insufficient_balance_notification(self, tran_id, device, current_balance, required_amount):
        """
        发送余额不足通知
        
        Args:
            device: 设备号码
            current_balance: 当前余额
            required_amount: 需要金额
        """
        notification = f"""
💰 <b>Balance Insufficient</b>

⏰ <b>Error occurred:</b> {self._get_current_time()}
🆔 <b>Transaction ID:</b> {tran_id}
📱 <b>Phone number  :</b> {device}
💵 <b>Current balance:</b> {current_balance}
💸 <b>Total Process Amount:</b> {required_amount}

"""
        
        return self.send_message(notification)
    
    @staticmethod
    def _get_current_time():
        """获取当前时间字符串"""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# 创建全局实例
telegram_notifier = TelegramNotifier()
