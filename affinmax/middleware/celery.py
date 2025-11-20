"""
Celery 配置文件
用于异步任务处理
"""
from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# 设置 Django 的默认配置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'middleware.settings')

# 创建 Celery 应用实例
app = Celery('affinmax')

# 从 Django 设置中加载配置，命名空间为 'CELERY'
app.config_from_object('django.conf:settings', namespace='CELERY')

# 自动从所有已注册的 Django 应用中发现任务
app.autodiscover_tasks()

# 时区设置（与 Django 保持一致）
app.conf.timezone = 'Asia/Kuala_Lumpur'
