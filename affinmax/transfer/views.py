from rest_framework.decorators import api_view
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from datetime import datetime
from django.http import JsonResponse
from django.db.models import Max
from django.test import RequestFactory
from django.views.decorators.csrf import csrf_exempt
from asgiref.sync import async_to_sync
from .consumers import connections
from .models import TransactionsList, MobileList, TransactionsStatus, TransactionsGroupList
import json
import boto3
import base64
from .consumers import connections





def send_task_to_device(mobile, credentials, group_obj):
    # 只有 is_online=1, is_activated=1, is_busy=0 才能派单
    if not mobile or not getattr(mobile, "is_online", False) or not getattr(mobile, "is_activated", False) or getattr(mobile, "is_busy", True):
        return Response({"status": "waiting", "msg": "No available device, order queued", "group_id": group_obj.id}, status=202)

    async_to_sync(connections[mobile.device].send)(
        text_data=json.dumps({
            "action": "start",
            "credentials": credentials,
        })
    )
    TransactionsList.objects.filter(group=group_obj).update(status=1)
    return JsonResponse({"message": f"Task pushed to {mobile.device}"})


# ========== assign_pending_orders ==========
@csrf_exempt
@api_view(["POST"])
def assign_pending_orders(request):
    # 查找空闲且已连接 WebSocket 的设备
    from .consumers import connections
    mobiles = MobileList.objects.filter(is_online=True, is_busy=False, is_activated=True)
    mobile = None
    for m in mobiles:
        if m.device in connections and getattr(m, "is_online", False) and getattr(m, "is_activated", False) and not getattr(m, "is_busy", True):
            mobile = m
            break
    if not mobile:
        return Response({"error": "No available idle device online"}, status=400)
    # 查找未分配的订单（status=0，phone_number为空）
    # 一次最多分配5个pending订单
    batch_orders = list(TransactionsList.objects.filter(status=0, phone_number="").order_by('id')[:5])
    if not batch_orders:
        return Response({"msg": "No pending orders to assign"}, status=200)
    # 先将订单分配给设备（phone_number/status=1），但不分组
    beneficiaries = []
    assigned = []
    total_tran_amount = 0
    for order in batch_orders:
        if getattr(mobile, "is_online", False) and getattr(mobile, "is_activated", False) and not getattr(mobile, "is_busy", True):
            order.phone_number = mobile.device
            order.status = 1
            order.error_message = "Pending"
        else:
            order.phone_number = ""
            order.status = 0
        order.save()
        assigned.append(order.tran_id)
        beneficiaries.append({
            "tran_id": order.tran_id,
            "amount": order.amount,
            "bene_acc_no": order.bene_acc_no,
            "bene_name": order.bene_name,
            "bank_code": order.bank_code,
            "recRef": order.recRef,
        })
        try:
            total_tran_amount += float(order.amount)
        except Exception:
            pass
    # 只有分配成功（phone_number和status=1）才创建 group 并归类
    ready_orders = [o for o in batch_orders if o.phone_number and o.status == 1]
    group_obj = None
    if ready_orders:
        group_obj = TransactionsGroupList.objects.create(
            total_tran_bene_acc=len(ready_orders),
            total_tran_amount=str(total_tran_amount),
            success_tran_amount="",
            current_balance=""
        )
        for order in ready_orders:
            order.group = group_obj
            order.save()
    credentials = {
        "corp_id": mobile.corp_id,
        "user_id": mobile.user_id,
        "password": mobile.password,
        "tranPass": mobile.tran_pass,
        "similarityThreshold": None,
        "beneficiaries": beneficiaries,
        "log_file": mobile.log_file,
        "device": mobile.device,
        "group_id": str(group_obj.id) if group_obj else "",
        "is_activated": 1 if getattr(mobile, "is_activated", False) else 0,
    }
    from asgiref.sync import async_to_sync
    from .consumers import connections
    resp = send_task_to_device(mobile, credentials, group_obj)
    return Response({"msg": "Assigned orders", "orders": assigned, "device": mobile.device, "group_id": str(group_obj.id) if group_obj else ""}, status=200)


# ========== update_is_busy ==========

@csrf_exempt
@api_view(["POST"])
def update_is_busy(request):
    device = request.data.get("device")
    is_busy = request.data.get("is_busy")
    if device is None or is_busy is None:
        return Response({"error": "Missing device or is_busy"}, status=400)
    try:
        mobile = MobileList.objects.get(device=device)
        mobile.is_busy = bool(int(is_busy))
        mobile.save()
        # 设备变空闲时自动调用 assign_pending_orders 实现自动派单
        if mobile.is_busy is False:
            import time
            time.sleep(2)  # 等待2秒
            factory = RequestFactory()
            assign_request = factory.post('/backend/assign_pending_orders/')
            assign_response = assign_pending_orders(assign_request)
            try:
                assign_data = assign_response.data
            except Exception:
                assign_data = None
            return Response({"status": "ok", "device": device, "is_busy": mobile.is_busy, "assign_result": assign_data})
        return Response({"status": "ok", "device": device, "is_busy": mobile.is_busy})
    except MobileList.DoesNotExist:
        return Response({"error": "Device not found"}, status=404)


# ========== update_group_success_amount ==========

@csrf_exempt
@api_view(["POST"])
def update_group_success_amount(request):
    group_id = request.data.get("group_id")
    success_tran_amount = request.data.get("success_tran_amount")
    if not group_id or success_tran_amount is None:
        return Response({"error": "Missing group_id or success_tran_amount"}, status=400)
    try:
        from .models import TransactionsGroupList
        group = TransactionsGroupList.objects.get(id=group_id)
        group.success_tran_amount = success_tran_amount
        group.save()
        return Response({"status": "ok"})
    except TransactionsGroupList.DoesNotExist:
        return Response({"error": "Group not found"}, status=404)

# ========== update_current_balance ==========


@csrf_exempt
@api_view(["POST"])
def update_current_balance(request):
    device = request.data.get("device")
    group_id = request.data.get("group_id")
    current_balance = request.data.get("current_balance")
    updated = []
    # Debug log
    print(f"[update_current_balance] device={device}, group_id={group_id}, current_balance={current_balance}")
    if device:
        from .models import MobileList
        try:
            mobile = MobileList.objects.get(device=device)
            mobile.current_balance = current_balance
            mobile.save()
            updated.append("mobile")
        except MobileList.DoesNotExist:
            print(f"[update_current_balance] MobileList not found for device={device}")
            pass
    if group_id:
        from .models import TransactionsGroupList
        try:
            group = TransactionsGroupList.objects.get(id=int(group_id))
            group.current_balance = current_balance
            group.save()
            updated.append("group")
        except TransactionsGroupList.DoesNotExist:
            print(f"[update_current_balance] TransactionsGroupList not found for id={group_id}")
            pass
        except Exception as e:
            print(f"[update_current_balance] Exception: {e}")
    if updated:
        print(f"[update_current_balance] Updated: {updated}")
        return Response({"status": "ok", "updated": updated})
    else:
        print(f"[update_current_balance] No record updated")
        return Response({"error": "No record updated"}, status=404)


# ========== add_transaction_status ==========
@swagger_auto_schema(
    method="post",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "status_name": openapi.Schema(type=openapi.TYPE_STRING)
        },
        required=["status_name"],
    ),
    responses={200: "TransactionStatus created"},
)

@csrf_exempt
@api_view(["POST"])
def add_transaction_status(request):
    status_name = request.data.get("status_name")
    if not status_name:
        return Response({"error": "Missing status_name"}, status=400)
    obj, created = TransactionsStatus.objects.get_or_create(status_name=status_name)
    return Response({"id": obj.id, "status_name": obj.status_name, "created": created})

@csrf_exempt
@api_view(["POST"])
def log(request):
    import os
    from .telegram_bot import telegram_notifier
    
    log_data = request.data
    log_dir = os.path.join(os.path.dirname(__file__), '../Log')
    log_dir = os.path.abspath(log_dir)
    os.makedirs(log_dir, exist_ok=True)
    device_number = log_data.get('device')
    if not device_number:
        return Response({"error": "Missing device number (device/phone_number/device_number)"}, status=400)
    log_file = os.path.join(log_dir, f'{device_number}.txt')
    from datetime import datetime
    msg = log_data.get('message', '')
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {msg}\n")

    # 自动同步 status 到 TransactionsList 并发送 Telegram 通知
    try:
        msg_json = json.loads(msg)
        tran_id = msg_json.get('tran_id')
        status = msg_json.get('status')
        error_message = msg_json.get('errorMessage')
        message_text = msg_json.get('message', '')
        
        # 只处理有 tran_id 且 status 的日志
        if tran_id and status is not None:
            qs = TransactionsList.objects.filter(tran_id=tran_id)
            if qs.exists():
                obj = qs.first()
                obj.status = str(status)
                if error_message:
                    obj.error_message = str(error_message)
                # 流程结束时，无论成功或失败都写入 complete_date
                from datetime import datetime
                obj.complete_date = datetime.now()
                obj.save()
                
                # 发送 Telegram 通知 - 只在出错时发送（status != "2"）
                # status = "2" 表示成功，其他状态表示错误
                if str(status) != "2":
                    # 自动停用设备 (is_activated = 0)
                    try:
                        mobile = MobileList.objects.get(device=device_number)
                        mobile.is_activated = False
                        mobile.save()
                    except MobileList.DoesNotExist:
                        print(f"⚠️ Device {device_number} config not found for deactivation")
                    except Exception as e:
                        print(f"❌ Failed to deactivate device: {e}")

                    # 发送错误通知（带按钮）
                    telegram_notifier.send_error_notification(
                        device=device_number,
                        error_data={
                            'status': status,
                            'tran_id': tran_id,
                            'message': message_text or error_message,
                            'errorMessage': error_message
                        }
                    )
        
        # 检测余额不足的日志
        if 'Insufficient balance' in msg or 'insufficient balance' in msg.lower():
            # 尝试解析余额信息
            try:
                balance_match = msg_json.get('remaining_balance') or msg_json.get('current_balance')
                if balance_match:
                    telegram_notifier.send_insufficient_balance_notification(
                        device=device_number,
                        current_balance=balance_match,
                        required_amount="N/A"
                    )
            except Exception:
                pass
                
    except json.JSONDecodeError:
        # 非 JSON 格式的日志，检查是否包含错误关键词
        error_keywords = ['❌', 'error', 'fail', 'exception', 'catch', 'Something went wrong']
        if any(keyword.lower() in msg.lower() for keyword in error_keywords):
            # 发送简单的错误通知
            telegram_notifier.send_automation_error(
                device=device_number,
                error_stage="Unknown",
                error_details=msg[:500]  # 限制消息长度
            )
    except Exception as e:
        # 非结构化日志或解析失败，跳过
        print(f"[log] Error processing message: {e}")
        pass

    return Response({"status": "ok"})


# ========== create_mobile ==========
@swagger_auto_schema(
    method="post",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "phone_number": openapi.Schema(type=openapi.TYPE_STRING),
            "corp_id": openapi.Schema(type=openapi.TYPE_STRING),
            "user_id": openapi.Schema(type=openapi.TYPE_STRING),
            "password": openapi.Schema(type=openapi.TYPE_STRING),
            "tran_pass": openapi.Schema(type=openapi.TYPE_STRING),
            "current_balance": openapi.Schema(type=openapi.TYPE_STRING),
            "is_online": openapi.Schema(type=openapi.TYPE_INTEGER, description="1=open, 0=close"),
            "is_activated": openapi.Schema(type=openapi.TYPE_INTEGER, description="1=open, 0=close"),
            "is_busy": openapi.Schema(type=openapi.TYPE_INTEGER, description="1=open, 0=close"),
            "last_error": openapi.Schema(type=openapi.TYPE_STRING),
            "log_file": openapi.Schema(type=openapi.TYPE_STRING),
        },
        required=["phone_number", "corp_id", "user_id", "password", "tran_pass", "current_balance", "is_online", "is_activated", "is_busy", "log_file"],
    ),
    responses={200: "Mobile created"},
)
@csrf_exempt
@api_view(["POST"])
def create_mobile(request):
    data = request.data
    phone_number = data.get("phone_number")
    if not phone_number:
        return Response({"error": "Missing phone_number"}, status=400)

    mobile, created = MobileList.objects.get_or_create(phone_number=phone_number)
    # 更新其它字段
    for field in [
        "corp_id", "user_id", "password", "tran_pass", "current_balance",
        "last_error", "log_file"
    ]:
        if field in data:
            setattr(mobile, field, data[field])
    for field in ["is_activated", "is_busy"]:
        if field in data:
            setattr(mobile, field, bool(int(data[field])))
    mobile.save()
    return Response({"status": "ok", "created": created})

credentials_map = {}


# ========== trigger ==========
@swagger_auto_schema(
    method="post",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "similarityThreshold": openapi.Schema(type=openapi.TYPE_NUMBER),
            "beneficiaries": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "tran_id": openapi.Schema(type=openapi.TYPE_STRING),
                        "amount": openapi.Schema(type=openapi.TYPE_STRING),
                        "bene_acc_no": openapi.Schema(type=openapi.TYPE_STRING),
                        "bene_name": openapi.Schema(type=openapi.TYPE_STRING),
                        "bank_code": openapi.Schema(type=openapi.TYPE_STRING),
                        "recRef": openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            )
        },
        required=["similarityThreshold", "beneficiaries"],
    ),
    responses={200: "Trigger set"},
)
@csrf_exempt
@api_view(["POST"])
def trigger(request):
    data = request.data
    # 查找可用 mobile（is_online=True, is_busy=False）
    from .consumers import connections
    # 只选 is_online=1, is_activated=1, is_busy=0 的设备
    mobiles = MobileList.objects.filter(is_online=True, is_busy=False, is_activated=True)
    mobile = None
    for m in mobiles:
        if m.device in connections and getattr(m, "is_online", False) and getattr(m, "is_activated", False) and not getattr(m, "is_busy", True):
            mobile = m
            break
    beneficiaries = data.get("beneficiaries", [])
    # 只在 TransactionsList 创建订单，不创建 group
    for bene in beneficiaries:
        TransactionsList.objects.create(
            tran_id=bene.get("tran_id"),
            amount=bene.get("amount"),
            bene_acc_no=bene.get("bene_acc_no"),
            bene_name=bene.get("bene_name"),
            bank_code=bene.get("bank_code"),
            recRef=bene.get("recRef"),
            phone_number="",
            status=0,
            error_message="Waiting"
        )

    # 没有可用设备，订单已入库，等待分配
    if not mobile:
        return Response({"status": "waiting", "msg": "No available device, order queued"}, status=202)

    # 只有设备 is_online 且 is_activated=1 时才推送任务
    if not getattr(mobile, "is_online", False) or not getattr(mobile, "is_activated", False):
        return Response({"status": "waiting", "msg": "No available device, order queued"}, status=202)

    credentials = {
        "corp_id": mobile.corp_id,
        "user_id": mobile.user_id,
        "password": mobile.password,
        "tranPass": mobile.tran_pass,
        "similarityThreshold": data.get("similarityThreshold"),
        "beneficiaries": beneficiaries,
        "log_file": mobile.log_file,
        "device": mobile.device,
        "group_id": "",  # 暂无 group_id
        "is_activated": 1 if getattr(mobile, "is_activated", False) else 0,
    }
    pn = mobile.device
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 自动调用 assign_pending_orders 派单
    from django.test import RequestFactory
    factory = RequestFactory()
    assign_request = factory.post('/backend/assign_pending_orders/')
    assign_response = assign_pending_orders(assign_request)
    try:
        assign_data = assign_response.data
    except Exception:
        assign_data = None
    return Response({
        "status": "triggered",
        "assign_result": assign_data
    })


# ========== upload_s3 ==========
@csrf_exempt
@swagger_auto_schema(
    method="post",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "device": openapi.Schema(type=openapi.TYPE_STRING),
            "fileName": openapi.Schema(type=openapi.TYPE_STRING),
            "fileData": openapi.Schema(type=openapi.TYPE_STRING, description="Base64 encoded file data"),
            "bucketName": openapi.Schema(type=openapi.TYPE_STRING),
            "tran_id": openapi.Schema(type=openapi.TYPE_STRING),
        },
        required=["device", "fileName", "fileData", "bucketName", "tran_id"],
    ),
    responses={200: "File uploaded to S3 successfully"},
)
@csrf_exempt
@api_view(["POST"])
def upload_s3(request):
    """上传文件到 AWS S3"""
    try:
        data = request.data
        device = data.get("device")
        file_name = data.get("fileName")
        file_data = data.get("fileData")
        bucket_name = data.get("bucketName")
        tran_id = data.get("tran_id")
        
        if not all([device, file_name, file_data, bucket_name, tran_id]):
            missing = []
            if not device: missing.append("device")
            if not file_name: missing.append("fileName")
            if not file_data: missing.append("fileData")
            if not bucket_name: missing.append("bucketName")
            if not tran_id: missing.append("tran_id")
            return Response({"error": f"Missing required fields: {missing}"}, status=400)
        
        # AWS S3 配置 - 从环境变量读取
        import os
        S3_CONFIG = {
            "AccessKey": os.environ.get("AWS_ACCESS_KEY_ID", ""),
            "SecretKey": os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
            "Region": os.environ.get("AWS_DEFAULT_REGION", "ap-southeast-1")
        }
        
        # 验证密钥是否存在
        if not S3_CONFIG["AccessKey"] or not S3_CONFIG["SecretKey"]:
            return Response({"error": "AWS credentials not configured"}, status=500)
        
        # 创建 S3 客户端
        try:
            import boto3
            s3_client = boto3.client(
                's3',
                aws_access_key_id=S3_CONFIG["AccessKey"],
                aws_secret_access_key=S3_CONFIG["SecretKey"],
                region_name=S3_CONFIG["Region"]
            )
        except ImportError as import_error:
            return Response({
                "status": "error",
                "message": f"boto3 not available: {import_error}"
            }, status=500)
        except Exception as client_error:
            return Response({
                "status": "error",
                "message": f"S3 client creation failed: {client_error}"
            }, status=500)
        
        # 解码 base64 数据
        try:
            file_content = base64.b64decode(file_data)
        except Exception as decode_error:
            return Response({
                "status": "error",
                "message": f"Base64 decode failed: {str(decode_error)}"
            }, status=400)
        
        # 构建 S3 对象键（文件路径）- 统一存储在 Affinmax/{device}/{tran_id}/ 下
        if file_name.lower().endswith('.pdf'):
            s3_key = f"Affinmax/{device}/{tran_id}/{file_name}"
            content_type = 'application/pdf'
        else:
            s3_key = f"Affinmax/{device}/{tran_id}/{file_name}"
            content_type = 'image/png'
        
        # 上传到 S3
        try:
            s3_client.put_object(
                Bucket=bucket_name,
                Key=s3_key,
                Body=file_content,
                ContentType=content_type,
                Metadata={
                    'device': device,
                    'upload_time': datetime.now().isoformat()
                }
            )
        except Exception as s3_error:
            return Response({
                "status": "error",
                "message": f"S3 upload failed: {str(s3_error)}"
            }, status=500)
        
        # 生成 S3 URL
        s3_url = f"https://{bucket_name}.s3.{S3_CONFIG['Region']}.amazonaws.com/{s3_key}"
        
        return Response({
            "status": "success",
            "message": "File uploaded successfully",
            "s3_url": s3_url,
            "s3_key": s3_key
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"[upload_s3] Error: {str(e)}")
        print(f"[upload_s3] Traceback: {error_details}")
        return Response({
            "status": "error",
            "message": f"Upload failed: {str(e)}",
            "traceback": error_details
        }, status=500)


# ========== telegram_webhook ==========
@csrf_exempt
@api_view(["POST"])
def telegram_webhook(request):
    """
    处理 Telegram Bot 的 webhook 回调
    用于处理 Activate/Deactivate 按钮点击事件
    """
    try:
        data = request.data
        print(f"[telegram_webhook] Received data: {json.dumps(data, indent=2)}")
        
        # 检查是否是 callback_query（按钮点击）
        if 'callback_query' not in data:
            return Response({"status": "ok", "message": "Not a callback query"})
        
        callback_query = data['callback_query']
        callback_data = callback_query.get('data', '')
        callback_id = callback_query.get('id', '')
        message = callback_query.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        message_id = message.get('message_id')
        
        # 解析 callback_data: "activate_0123456789" 或 "deactivate_0123456789"
        parts = callback_data.split('_', 1)
        if len(parts) != 2:
            return Response({"status": "error", "message": "Invalid callback data"}, status=400)
        
        action = parts[0]  # "activate" 或 "deactivate"
        device = parts[1]   # 设备号码
        
        # 查找设备
        try:
            mobile = MobileList.objects.get(device=device)
        except MobileList.DoesNotExist:
            # 回复用户
            answer_callback_query(callback_id, f"❌ 设备 {device} 未找到")
            return Response({"status": "error", "message": "Device not found"}, status=404)
        
        # 执行操作
        if action == "activate":
            mobile.is_activated = True
            mobile.save()
            response_text = f"✅ 设备 {device} 已激活\n\n设备现在可以接收新的交易任务。"
            answer_text = "✅ 设备已激活"
        elif action == "deactivate":
            mobile.is_activated = False
            mobile.save()
            response_text = f"❌ 设备 {device} 已停用\n\n设备将不会接收新的交易任务。"
            answer_text = "❌ 设备已停用"
        else:
            answer_callback_query(callback_id, "❌ 无效的操作")
            return Response({"status": "error", "message": "Invalid action"}, status=400)
        
        # 回复 callback query（移除 "加载中..." 提示）
        answer_callback_query(callback_id, answer_text)
        
        # 编辑原消息，添加操作结果
        edit_message_text(chat_id, message_id, response_text)
        
        return Response({
            "status": "success",
            "action": action,
            "device": device,
            "is_activated": mobile.is_activated
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"[telegram_webhook] Error: {str(e)}")
        print(f"[telegram_webhook] Traceback: {error_details}")
        return Response({
            "status": "error",
            "message": str(e),
            "traceback": error_details
        }, status=500)


def answer_callback_query(callback_query_id, text):
    """回复 callback query（显示提示消息）"""
    from django.conf import settings
    import requests
    
    bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not bot_token:
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
    payload = {
        'callback_query_id': callback_query_id,
        'text': text,
        'show_alert': False
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ answer_callback_query failed: {e}")
        return False


def edit_message_text(chat_id, message_id, new_text):
    """编辑消息内容"""
    from django.conf import settings
    import requests
    
    bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not bot_token:
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    payload = {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': new_text,
        'parse_mode': 'HTML'
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ edit_message_text failed: {e}")
        return False
