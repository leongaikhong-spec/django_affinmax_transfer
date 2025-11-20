"""
Celery tasks for automatic callback retry mechanism
"""
from celery import shared_task
from django.conf import settings
from .models import TransactionsList, CallbackLog
import requests
import json
import logging

logger = logging.getLogger(__name__)

# 固定重试间隔（秒）- 无限重试直到成功
RETRY_INTERVAL = 30  # 每30秒重试一次


@shared_task(bind=True, max_retries=None)
def retry_failed_callback(self, transaction_id):
    """
    自动重试失败的 callback
    
    Args:
        transaction_id: TransactionsList 的主键 ID
    """
    try:
        transaction = TransactionsList.objects.get(id=transaction_id)
        
        # 检查是否已经成功
        if transaction.callback_status == 1:
            logger.info(f"Transaction {transaction_id} callback already successful, skipping retry")
            return {"status": "already_success", "transaction_id": transaction_id}
        
        # 准备 callback 数据
        callback_url = getattr(settings, 'DEFAULT_CALLBACK_URL', '')
        if not callback_url:
            logger.error(f"No callback URL configured for transaction {transaction_id}")
            return {"status": "no_callback_url", "transaction_id": transaction_id}
        
        callback_data = {
            "tran_id": transaction.tran_id,
            "status": transaction.status,
            "message": "Transaction completed" if transaction.status == 1 else "Transaction failed",
            "errorMessage": transaction.error_message or ""
        }
        
        # 增加尝试次数
        transaction.callback_attempts += 1
        transaction.save(update_fields=['callback_attempts'])
        
        logger.info(f"Attempting callback retry #{transaction.callback_attempts} for transaction {transaction_id}")
        
        # 发送 callback
        try:
            response = requests.post(
                callback_url,
                json=callback_data,
                timeout=30,
                headers={'Content-Type': 'application/json'}
            )
            
            # 记录到 CallbackLog
            CallbackLog.objects.create(
                callback_url=callback_url,
                request_body=json.dumps(callback_data),
                response_body=response.text,
                status_code=response.status_code,
                success=(response.status_code == 200),
                error_message=None if response.status_code == 200 else f"HTTP {response.status_code}"
            )
            
            if response.status_code == 200:
                # 成功！更新 callback_status 为 1
                transaction.callback_status = 1
                transaction.save(update_fields=['callback_status'])
                logger.info(f"Callback retry successful for transaction {transaction_id} after {transaction.callback_attempts} attempts")
                return {
                    "status": "success",
                    "transaction_id": transaction_id,
                    "attempts": transaction.callback_attempts
                }
            else:
                # 失败，安排下一次重试
                logger.warning(f"Callback retry failed with status {response.status_code} for transaction {transaction_id}")
                schedule_next_retry(transaction_id, transaction.callback_attempts)
                return {
                    "status": "retry_scheduled",
                    "transaction_id": transaction_id,
                    "attempts": transaction.callback_attempts,
                    "http_status": response.status_code
                }
                
        except requests.exceptions.RequestException as e:
            # 网络错误，记录并安排重试
            logger.error(f"Network error during callback retry for transaction {transaction_id}: {str(e)}")
            
            CallbackLog.objects.create(
                callback_url=callback_url,
                request_body=json.dumps(callback_data),
                response_body=None,
                status_code=None,
                success=False,
                error_message=str(e)
            )
            
            schedule_next_retry(transaction_id, transaction.callback_attempts)
            return {
                "status": "retry_scheduled",
                "transaction_id": transaction_id,
                "attempts": transaction.callback_attempts,
                "error": str(e)
            }
            
    except TransactionsList.DoesNotExist:
        logger.error(f"Transaction {transaction_id} not found")
        return {"status": "not_found", "transaction_id": transaction_id}
    except Exception as e:
        logger.exception(f"Unexpected error in retry_failed_callback for transaction {transaction_id}: {str(e)}")
        return {"status": "error", "transaction_id": transaction_id, "error": str(e)}


def schedule_next_retry(transaction_id, current_attempts):
    """
    安排下一次重试，使用固定间隔
    
    Args:
        transaction_id: TransactionsList 的主键 ID
        current_attempts: 当前已尝试次数
    """
    logger.info(f"Scheduling callback retry for transaction {transaction_id} in {RETRY_INTERVAL} seconds (attempt #{current_attempts + 1})")
    
    # 使用固定间隔延迟执行
    retry_failed_callback.apply_async(args=[transaction_id], countdown=RETRY_INTERVAL)
