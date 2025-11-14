from rest_framework.decorators import api_view
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from datetime import datetime
from django.http import JsonResponse
from django.db.models import Max
from django.test import RequestFactory
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from asgiref.sync import async_to_sync
from .consumers import connections
from .models import TransactionsList, MobileList, TransactionsStatus, TransactionsGroupList, CallbackLog
import json
import boto3
import base64
import requests
from .consumers import connections


# ========== 辅助函数：发送callback并记录 ==========
def send_callback(callback_url=None, data=None):
    """
    发送callback并自动记录到CallbackLog
    
    Args:
        callback_url: callback的目标URL（可选，不传则使用配置的默认URL）
        data: 要发送的数据（字典）
    
    Returns:
        bool: 是否成功
    """
    # 如果没有传入 callback_url，使用配置中的默认URL
    if not callback_url:
        callback_url = getattr(settings, 'DEFAULT_CALLBACK_URL', None)
    
    if not callback_url:
        print("Warning: No callback URL configured")
        return False
    
    if not data:
        print("Warning: No data to send in callback")
        return False
    
    request_body = json.dumps(data, ensure_ascii=False)
    
    try:
        response = requests.post(
            callback_url,
            json=data,
            timeout=30,
            headers={'Content-Type': 'application/json'}
        )
        
        # 记录callback
        CallbackLog.objects.create(
            callback_url=callback_url,
            request_body=request_body,
            response_body=response.text[:10000],
            status_code=response.status_code,
            success=response.status_code == 200,
            error_message=None if response.status_code == 200 else f"Status code: {response.status_code}"
        )
        
        return response.status_code == 200
        
    except Exception as e:
        # 记录失败的callback
        CallbackLog.objects.create(
            callback_url=callback_url,
            request_body=request_body,
            response_body=None,
            status_code=None,
            success=False,
            error_message=str(e)
        )
        print(f"Callback failed: {e}")
        return False



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
    
    # beneficiaries 每个都带自己的 similarity_threshold
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
            "amount": str(order.amount),  # 转换 Decimal 为字符串
            "bene_acc_no": order.bene_acc_no,
            "bene_name": order.bene_name,
            "bank_code": order.bank_code,
            "recRef": order.recRef,
            "similarity_threshold": order.similarity_threshold if hasattr(order, 'similarity_threshold') else 0.7
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
            total_tran_amount=total_tran_amount,
            success_tran_amount=0,
            current_balance=0
        )
        for order in ready_orders:
            order.group = group_obj
            order.save()
    credentials = {
        "corp_id": mobile.corp_id,
        "user_id": mobile.user_id,
        "password": mobile.password,
        "tranPass": mobile.tran_pass,
        # 不再统一 similarityThreshold，直接下发 beneficiaries 列表，每个带自己的 similarity_threshold
        "beneficiaries": beneficiaries,
        "log_file": mobile.log_file,
        "device": mobile.device,
        "group_id": str(group_obj.id) if group_obj else "",
        "is_activated": 1 if getattr(mobile, "is_activated", False) else 0,
    }
    from asgiref.sync import async_to_sync
    from .consumers import connections
    resp = send_task_to_device(mobile, credentials, group_obj)
    return Response({
        "msg": "Assigned orders",
        "orders": assigned,
        "device": mobile.device,
        "group_id": str(group_obj.id) if group_obj else "",
        "beneficiaries": beneficiaries
    }, status=200)


# ========== update_is_busy ==========
@swagger_auto_schema(
    method="post",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "device": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Phone number"
            ),
            "is_busy": openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description="0 = Not Busy, 1 = Busy",
                enum=[0, 1]
            ),
        },
        required=["device", "is_busy"],
    ),
    responses={
        200: "Status updated successfully",
        400: "Missing required fields",
        404: "Phone number not found"
    },
)
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
        # ✅ 不需要传递 similarityThreshold，因为已经保存在数据库中
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
        # 处理空字符串转换为 None 或 0
        if success_tran_amount == "":
            success_tran_amount = 0
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
            # 处理空字符串转换为 None
            if current_balance == "":
                current_balance = None
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
            # 处理空字符串转换为 None
            if current_balance == "":
                current_balance = None
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
                    # 检查是否是不需要停用设备的错误类型
                    error_lower = error_message.lower() if error_message else ""
                    
                    # 不需要停用设备的错误类型:
                    # 1. 无效的银行或账号
                    is_invalid_bank_account = 'invalid bank or account number' in error_lower
                    # 2. 名字不匹配（包含 Expected 和 Actual）
                    is_name_mismatch = ('expected' in error_lower and 'actual' in error_lower)
                    
                    # 只有在非特殊错误类型时才自动停用设备
                    should_deactivate = not (is_invalid_bank_account or is_name_mismatch)
                    
                    if should_deactivate:
                        try:
                            mobile = MobileList.objects.get(device=device_number)
                            mobile.is_activated = False
                            mobile.save()
                        except MobileList.DoesNotExist:
                            print(f"⚠️ Device {device_number} config not found for deactivation")
                        except Exception as e:
                            print(f"❌ Failed to deactivate device: {e}")

                    # 获取 group_id（如果存在）
                    group_id = obj.group.id if obj.group else 'N/A'
                    
                    # 获取余额信息（从日志或数据库）
                    current_balance = msg_json.get('current_balance') or msg_json.get('remaining_balance', 'N/A')
                    required_amount = msg_json.get('required_amount') or msg_json.get('total_amount', 'N/A')
                    
                    # 如果日志中没有，尝试从数据库获取
                    if current_balance == 'N/A':
                        try:
                            mobile = MobileList.objects.get(device=device_number)
                            current_balance = mobile.current_balance or 'N/A'
                        except:
                            pass

                    # 发送错误通知（带按钮）
                    telegram_notifier.send_error_notification(
                        device=device_number,
                        error_data={
                            'status': status,
                            'tran_id': tran_id,
                            'group_id': str(group_id),
                            'current_balance': str(current_balance),
                            'required_amount': str(required_amount),
                            'message': message_text or error_message,
                            'errorMessage': error_message
                        }
                    )
                
    except json.JSONDecodeError:
        # 非 JSON 格式的日志，跳过 Telegram 通知
        pass
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
        "corp_id", "user_id", "password", "tran_pass",
        "last_error", "log_file"
    ]:
        if field in data:
            setattr(mobile, field, data[field])
    
    # 单独处理 current_balance，避免空字符串报错
    if "current_balance" in data:
        balance = data["current_balance"]
        if balance == "" or balance is None:
            mobile.current_balance = None
        else:
            mobile.current_balance = balance
    
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
    similarity_threshold = data.get("similarityThreshold", 0.7)  # ✅ 获取阈值
    
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
            error_message="Waiting",
            similarity_threshold=similarity_threshold  # ✅ 保存到数据库
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
    # ✅ 不需要传递 similarityThreshold，因为已经保存在数据库中
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
            "tran_id": openapi.Schema(type=openapi.TYPE_STRING),
        },
        required=["device", "fileName", "fileData", "tran_id"],
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
        tran_id = data.get("tran_id")
        
        # 使用默认的 bucket name（如果没有提供）
        bucket_name = data.get("bucketName", "affinmax-transfer-bucket")
        
        if not all([device, file_name, file_data, tran_id]):
            missing = []
            if not device: missing.append("device")
            if not file_name: missing.append("fileName")
            if not file_data: missing.append("fileData")
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
        
        # 保存 S3 路径到数据库
        try:
            transaction = TransactionsList.objects.get(tran_id=tran_id)
            # 根据文件类型保存到不同字段
            if file_name.lower().endswith('.pdf'):
                transaction.pdf_s3_path = s3_url
            else:
                transaction.screenshot_s3_path = s3_url
            transaction.save()
        except TransactionsList.DoesNotExist:
            # 如果找不到交易记录，记录日志但不影响上传成功的响应
            print(f"[upload_s3] Transaction not found for tran_id: {tran_id}")
        except Exception as db_error:
            print(f"[upload_s3] Failed to save S3 path to database: {db_error}")
        
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


# ========== test_telegram ==========
@swagger_auto_schema(
    method="post",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "message_type": openapi.Schema(
                type=openapi.TYPE_STRING, 
                description="error message type",
                enum=["simple", "error", "balance", "invalid_bank", "name_mismatch"]
            ),
            "device": openapi.Schema(type=openapi.TYPE_STRING, description="device number"),
            "test_message": openapi.Schema(type=openapi.TYPE_STRING, description="custom test message (for simple type)"),
        },
    ),
    responses={
        200: "Telegram message sent successfully",
        500: "Failed to send message"
    },
)
@csrf_exempt
@api_view(["POST"])
def test_telegram(request):
    """Error message type: simple, error, balance, invalid_bank, name_mismatch"""
    from .telegram_bot import telegram_notifier
    
    message_type = request.data.get("message_type", "simple")
    device = request.data.get("device", "0123456789")
    test_message = request.data.get("test_message", "")
    
    try:
        if message_type == "simple":
            # 发送简单消息
            msg = test_message or f"""
🧪 <b>Telegram 测试消息</b>

<b>测试时间:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
<b>设备号码:</b> {device}
<b>消息类型:</b> 简单测试消息

✅ 如果你看到这条消息，说明 Telegram 配置成功！
"""
            success = telegram_notifier.send_message(msg)
            
        elif message_type == "error":
            # 发送通用错误通知（带按钮）
            error_data = {
                'status': '3',
                'tran_id': 'TEST_001',
                'group_id': '999',
                'current_balance': '50000.00',
                'required_amount': '60000.00',
                'message': 'Test error message',
                'errorMessage': 'This is a test error for debugging'
            }
            success = telegram_notifier.send_error_notification(device, error_data)
            
        elif message_type == "balance":
            # 发送余额不足错误
            error_data = {
                'status': '3',
                'tran_id': 'TEST_002',
                'group_id': '998',
                'current_balance': '1000.00',
                'required_amount': '5000.00',
                'message': 'Insufficient balance',
                'errorMessage': 'Balance less than transfer amount. Current: 1000.00, Required: 5000.00'
            }
            success = telegram_notifier.send_error_notification(device, error_data)
            
        elif message_type == "invalid_bank":
            # 发送无效银行账号错误
            error_data = {
                'status': '3',
                'tran_id': 'TEST_003',
                'group_id': '997',
                'current_balance': '50000.00',
                'required_amount': '1000.00',
                'message': 'Invalid bank account',
                'errorMessage': 'Invalid bank or account number: 1234567890'
            }
            success = telegram_notifier.send_error_notification(device, error_data)
            
        elif message_type == "name_mismatch":
            # 发送名字不匹配错误
            error_data = {
                'status': '3',
                'tran_id': 'TEST_004',
                'group_id': '996',
                'current_balance': '50000.00',
                'required_amount': '1000.00',
                'message': 'Name mismatch',
                'errorMessage': 'Name verification failed. Expected: JOHN DOE, Actual: JANE DOE'
            }
            success = telegram_notifier.send_error_notification(device, error_data)
            
        else:
            return Response({
                "error": f"Unknown message_type: {message_type}",
                "available_types": ["simple", "error", "balance", "invalid_bank", "name_mismatch"]
            }, status=400)
        
        if success:
            return Response({
                "status": "success",
                "message": f"Telegram {message_type} message sent successfully",
                "chat_id": telegram_notifier.chat_id,
                "topic_id": getattr(telegram_notifier, 'topic_id', None),
                "device": device,
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        else:
            return Response({
                "status": "failed",
                "message": "Failed to send Telegram message",
                "enabled": telegram_notifier.enabled
            }, status=500)
            
    except Exception as e:
        import traceback
        return Response({
            "status": "error",
            "message": f"Exception occurred: {str(e)}",
            "traceback": traceback.format_exc()
        }, status=500)


# ========== send_callback_to_client ==========
@swagger_auto_schema(
    method="post",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "tran_id": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Transactions ID"
            ),
        },
        required=["tran_id"],
    ),
    responses={
        200: "Callback sent successfully",
        404: "Transaction not found",
        500: "Failed to send callback"
    },
)
@csrf_exempt
@api_view(["POST"])
def send_callback_to_client(request):
    try:
        data = request.data
        tran_id = data.get("tran_id")
        callback_url = data.get("callback_url")  # 可选，允许临时指定callback URL
        
        # 如果只提供了 tran_id，从数据库查询交易信息（手动callback模式）
        if tran_id and not data.get("status"):
            try:
                transaction = TransactionsList.objects.get(tran_id=tran_id)
                
                # 从数据库构建 callback 数据
                callback_data = {
                    "status": str(transaction.status),
                    "tran_id": str(transaction.tran_id),
                    "message": transaction.error_message or "Manual callback",
                    "errorMessage": transaction.error_message or "Manual callback triggered"
                }
                
                manual_mode = True
                transaction_info = {
                    "tran_id": transaction.tran_id,
                    "status": transaction.status,
                    "amount": transaction.amount,
                    "bene_name": transaction.bene_name,
                    "bene_acc_no": transaction.bene_acc_no,
                    "error_message": transaction.error_message,
                    "complete_date": transaction.complete_date.strftime('%Y-%m-%d %H:%M:%S') if transaction.complete_date else None
                }
                
            except TransactionsList.DoesNotExist:
                return Response({
                    "status": "error",
                    "message": f"Transaction with tran_id '{tran_id}' not found"
                }, status=404)
        else:
            # 正常模式：使用传入的数据
            callback_data = {
                "status": data.get("status"),
                "tran_id": data.get("tran_id"),
                "message": data.get("message"),
                "errorMessage": data.get("errorMessage")
            }
            manual_mode = False
            transaction_info = None
        
        # 如果没有提供 callback_url，使用默认的
        if not callback_url:
            from django.conf import settings
            callback_url = getattr(settings, 'DEFAULT_CALLBACK_URL', None)
        
        # 如果没有配置callback_url，返回提示
        if not callback_url:
            return Response({
                "status": "skipped",
                "message": "No callback URL configured in settings"
            }, status=200)
        
        # 调用send_callback函数发送callback（只发送核心字段）
        success = send_callback(callback_url, callback_data)
        
        if success:
            response_data = {
                "status": "success",
                "message": "Manual callback sent successfully" if manual_mode else "Callback sent successfully",
                "callback_url": callback_url,
                "tran_id": callback_data.get("tran_id"),
                "callback_data": callback_data
            }
            
            # 如果是手动模式，返回交易详情
            if manual_mode and transaction_info:
                response_data["transaction_info"] = transaction_info
            
            return Response(response_data)
        else:
            return Response({
                "status": "failed",
                "message": "Callback failed, check CallbackLog for details",
                "callback_url": callback_url,
                "tran_id": callback_data.get("tran_id")
            }, status=500)
            
    except Exception as e:
        import traceback
        return Response({
            "status": "error",
            "message": f"Exception occurred: {str(e)}",
            "traceback": traceback.format_exc()
        }, status=500)
