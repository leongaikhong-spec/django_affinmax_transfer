"""
Celery Worker 后台线程启动模块
自动在 Django/uvicorn 启动时后台运行 Celery Worker
"""
import threading
import subprocess
import sys
import os


class CeleryWorkerThread:
    """Celery Worker 后台线程管理"""
    
    def __init__(self):
        self.worker_process = None
        self.worker_thread = None
        self.is_running = False
    
    def start(self):
        """启动 Celery Worker (后台线程)"""
        if self.is_running:
            print("⚠️ Celery Worker already running")
            return
        
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._run_worker, daemon=True)
        self.worker_thread.start()
    
    def _run_worker(self):
        """在后台线程中运行 Celery Worker"""
        try:
            # 获取项目根目录
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # 构建 celery 命令
            celery_cmd = [
                sys.executable,  # 当前 Python 解释器
                '-m', 'celery',
                '-A', 'middleware',
                'worker',
                '--loglevel=info',
                '--pool=solo',  # 使用 solo pool（单线程，适合开发和简单场景）
            ]
            
            print(f"📋 Starting Celery Worker: {' '.join(celery_cmd)}")
            
            # 启动 Celery Worker 进程
            self.worker_process = subprocess.Popen(
                celery_cmd,
                cwd=base_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            # 实时输出日志
            for line in self.worker_process.stdout:
                if line.strip():
                    print(f"[Celery] {line.strip()}")
            
        except Exception as e:
            print(f"❌ Celery Worker error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.is_running = False
    
    def stop(self):
        """停止 Celery Worker"""
        if self.worker_process:
            self.worker_process.terminate()
            self.worker_process.wait(timeout=5)
            print("✅ Celery Worker stopped")
        self.is_running = False


# 全局单例
_celery_worker = CeleryWorkerThread()


def start_celery_worker_thread():
    """启动 Celery Worker 后台线程（供 apps.py 调用）"""
    _celery_worker.start()


def stop_celery_worker_thread():
    """停止 Celery Worker"""
    _celery_worker.stop()
