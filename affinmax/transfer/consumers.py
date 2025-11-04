from channels.generic.websocket import AsyncWebsocketConsumer
import json
from .models import MobileList

# 保存在线设备 {pn: consumer}
connections = {}

class ScriptConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.pn = self.scope['url_route']['kwargs']['pn']
        connections[self.pn] = self
        await self.accept()
        print(f"📱 Device {self.pn} connected")
        # WebSocket连接成功，设为 is_online=1
        from asgiref.sync import sync_to_async
        from .models import MobileList
        try:
            mobile = await sync_to_async(MobileList.objects.get)(device=self.pn)
            mobile.is_online = True
            await sync_to_async(mobile.save)()
            print(f"✅ Device {self.pn} set to online, is_activated={mobile.is_activated}, is_busy={mobile.is_busy}")
            
            # 等待一下确保 connections 已经更新
            import asyncio
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
        print(f"❌ Device {self.pn} disconnected")
        # WebSocket断开，设为 is_online=0
        from asgiref.sync import sync_to_async
        from .models import MobileList
        try:
            mobile = await sync_to_async(MobileList.objects.get)(device=self.pn)
            mobile.is_online = False
            await sync_to_async(mobile.save)()
        except MobileList.DoesNotExist:
            pass

    async def receive(self, text_data):
        print(f"📩 Message from {self.pn}: {text_data}")
        # 你可以在这里接收手机发来的心跳或状态
