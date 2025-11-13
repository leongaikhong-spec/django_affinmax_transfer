from channels.generic.websocket import AsyncWebsocketConsumer
import json
import asyncio
from datetime import datetime
from .models import MobileList

# 保存在线设备 {pn: consumer}
connections = {}

# 保存每个设备的最后心跳时间 {pn: datetime}
last_heartbeat = {}

# 心跳超时时间（秒）- 如果超过这个时间没收到心跳，设为离线
HEARTBEAT_TIMEOUT = 15  # 30秒（客户端每5秒发一次，允许丢失更多次，更宽松）

class ScriptConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.pn = self.scope['url_route']['kwargs']['pn']
        connections[self.pn] = self
        last_heartbeat[self.pn] = datetime.now()  # 记录连接时间
        await self.accept()
        print(f"📱 Device {self.pn} connected")
        
        # 启动心跳检测任务
        asyncio.create_task(self.check_heartbeat_timeout())
        
        # WebSocket连接成功，设为 is_online=1
        from asgiref.sync import sync_to_async
        from .models import MobileList
        from .telegram_bot import telegram_notifier
        
        try:
            mobile = await sync_to_async(MobileList.objects.get)(device=self.pn)
            mobile.is_online = True
            await sync_to_async(mobile.save)()
            print(f"✅ Device {self.pn} set to online, is_activated={mobile.is_activated}, is_busy={mobile.is_busy}")
            
            # 发送 Telegram 通知
            connect_msg = f"""
<b>Device</b> {self.pn} <b>Connected</b>
"""
            await sync_to_async(telegram_notifier.send_message)(connect_msg)
            
            # 等待一下确保 connections 已经更新
            await asyncio.sleep(0.5)
            
            # 设备连接成功后，自动检查是否有待处理的订单
            from .views import assign_pending_orders
            from django.test import RequestFactory
            factory = RequestFactory()
            assign_request = factory.post('/backend/assign_pending_orders/')
            # 在异步环境中调用同步视图函数
            assign_response = await sync_to_async(assign_pending_orders)(assign_request)
            try:
                response_data = assign_response.data
            except Exception as e:
                print(f"⚠️ Could not parse response: {e}")
        except MobileList.DoesNotExist:
            print(f"⚠️ Device {self.pn} not found in MobileList")
            pass

    async def disconnect(self, close_code):
        if self.pn in connections:
            del connections[self.pn]
        if self.pn in last_heartbeat:
            del last_heartbeat[self.pn]
        print(f"❌ Device {self.pn} disconnected")
        
        # WebSocket断开，设为 is_online=0
        from asgiref.sync import sync_to_async
        from .models import MobileList
        from .telegram_bot import telegram_notifier
        
        try:
            mobile = await sync_to_async(MobileList.objects.get)(device=self.pn)
            mobile.is_online = False
            await sync_to_async(mobile.save)()
            print(f"✅ Device {self.pn} set to offline")
            
            # 发送 Telegram 通知
            disconnect_msg = f"""
<b>Device</b> {self.pn} <b>Disconnected</b>
"""
            await sync_to_async(telegram_notifier.send_message)(disconnect_msg)
            
        except MobileList.DoesNotExist:
            pass

    async def receive(self, text_data):
        # 收到任何消息都更新心跳时间
        last_heartbeat[self.pn] = datetime.now()
        
        # 处理心跳消息
        try:
            data = json.loads(text_data)
            if data.get("type") == "ping":
                # 回复 pong
                await self.send(text_data="pong")
                return
        except json.JSONDecodeError:
            pass
        
        # 打印非心跳消息
        print(f"📩 Message from {self.pn}: {text_data}")
        
        # 其他消息处理逻辑...
    
    async def check_heartbeat_timeout(self):
        """定期检查心跳超时，如果超时则设置为离线"""
        from asgiref.sync import sync_to_async
        
        while self.pn in connections:
            try:
                await asyncio.sleep(5)  # 每5秒检查一次
                
                if self.pn not in last_heartbeat:
                    continue
                
                # 计算距离上次心跳的时间
                time_since_heartbeat = (datetime.now() - last_heartbeat[self.pn]).total_seconds()
                
                if time_since_heartbeat > HEARTBEAT_TIMEOUT:
                    print(f"⚠️ Device {self.pn} heartbeat timeout ({time_since_heartbeat:.1f}s), setting offline")
                    
                    # 设置为离线
                    try:
                        mobile = await sync_to_async(MobileList.objects.get)(device=self.pn)
                        if mobile.is_online:  # 只有在线时才更新，避免重复日志
                            mobile.is_online = False
                            await sync_to_async(mobile.save)()
                            print(f"✅ Device {self.pn} automatically set to offline due to heartbeat timeout")
                    except MobileList.DoesNotExist:
                        pass
                    
                    # 关闭 WebSocket 连接
                    await self.close()
                    break
                    
            except Exception as e:
                print(f"❌ Heartbeat check error for {self.pn}: {e}")
                break
