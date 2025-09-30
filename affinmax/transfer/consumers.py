from channels.generic.websocket import AsyncWebsocketConsumer
import json

# 保存在线设备 {pn: consumer}
connections = {}

class ScriptConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.pn = self.scope['url_route']['kwargs']['pn']
        connections[self.pn] = self
        await self.accept()
        print(f"📱 Device {self.pn} connected")

    async def disconnect(self, close_code):
        if self.pn in connections:
            del connections[self.pn]
        print(f"❌ Device {self.pn} disconnected")

    async def receive(self, text_data):
        print(f"📩 Message from {self.pn}: {text_data}")
        # 你可以在这里接收手机发来的心跳或状态
