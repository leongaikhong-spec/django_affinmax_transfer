import json
import time
from django.utils.deprecation import MiddlewareMixin
from .models import APICallLog


class APILoggingMiddleware(MiddlewareMixin):
    """
    中间件用于记录所有API调用信息
    记录包括：HTTP方法、路径、请求体、响应体、客户端IP、状态码、时间戳
    """
    
    def process_request(self, request):
        # 记录请求开始时间
        request.start_time = time.time()
        
        # 获取客户端IP地址
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            request.client_ip = x_forwarded_for.split(',')[0].strip()
        else:
            request.client_ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        
        # 获取请求体
        try:
            if request.body:
                request.request_body = request.body.decode('utf-8')
            else:
                request.request_body = ''
        except Exception:
            request.request_body = ''
        
        return None
    
    def process_response(self, request, response):
        # 只记录 make_transactions API
        path = request.path
        if path != '/script/make_transactions/':
            return response
        
        # 计算响应时间
        response_time = None
        if hasattr(request, 'start_time'):
            response_time = (time.time() - request.start_time) * 1000  # 转换为毫秒
        
        # 获取响应体
        response_body = ''
        try:
            if hasattr(response, 'content'):
                # 限制响应体大小，避免存储过大的数据
                content = response.content.decode('utf-8')
                if len(content) <= 10000:  # 只存储小于10KB的响应
                    response_body = content
                else:
                    response_body = content[:10000] + '... [truncated]'
        except Exception:
            response_body = '[Binary or non-UTF8 content]'
        
        # 获取User-Agent
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # 异步保存日志（避免阻塞响应）
        try:
            APICallLog.objects.create(
                method=request.method,
                path=path,
                request_body=getattr(request, 'request_body', ''),
                response_body=response_body,
                client_ip=getattr(request, 'client_ip', '0.0.0.0'),
                status_code=response.status_code,
                user_agent=user_agent[:1000] if user_agent else '',  # 限制长度
                response_time=response_time
            )
        except Exception as e:
            # 记录日志失败不应该影响正常响应
            print(f"Failed to log API call: {e}")
        
        return response
