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
        except MobileList.DoesNotExist:
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
