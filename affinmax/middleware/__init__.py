"""
确保 Celery app 在 Django 启动时加载
"""
from __future__ import absolute_import, unicode_literals

# 导入 Celery app，确保 Django 启动时自动加载
from .celery import app as celery_app

__all__ = ('celery_app',)
