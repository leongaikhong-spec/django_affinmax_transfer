from rest_framework.decorators import api_view
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from datetime import datetime
from django.http import JsonResponse
from django.db.models import Max
from django.test import RequestFactory
from asgiref.sync import async_to_sync
from .consumers import connections
from .models import TransactionsList, MobileList, TransactionsStatus, TransactionsGroupList
import json






# 查询设备 is_online 状态接口

from django.http import JsonResponse


# ========== assign_pending_orders ==========
@api_view(["POST"])
def assign_pending_orders(request):
    # 查找空闲且已连接 WebSocket 的设备
    from .consumers import connections
    mobiles = MobileList.objects.filter(is_online=True, is_busy=False)
    mobile = None
    for m in mobiles:
        if m.device in connections:
            mobile = m
            break
    if not mobile:
        return Response({"error": "No available idle device online"}, status=400)
    # 查找未分配的订单（status=0，phone_number为空）
    pending_orders = TransactionsList.objects.filter(status=0, phone_number="")
    if not pending_orders.exists():
        return Response({"msg": "No pending orders to assign"}, status=200)
    assigned = []
    for order in pending_orders:
        order.phone_number = mobile.device
        order.status = 1
        order.save()
        # 推送任务到设备（WebSocket）
        group = order.group
        beneficiaries = TransactionsList.objects.filter(group=group)
        credentials = {
            "corp_id": mobile.corp_id,
            "user_id": mobile.user_id,
            "password": mobile.password,
            "tranPass": mobile.tran_pass,
            "similarityThreshold": None,
            "beneficiaries": [
                {
                    "tran_id": o.tran_id,
                    "amount": o.amount,
                    "bene_acc_no": o.bene_acc_no,
                    "bene_name": o.bene_name,
                    "bank_code": o.bank_code,
                    "recRef": o.recRef,
                } for o in beneficiaries
            ],
            "log_file": mobile.log_file,
            "device": mobile.device,
            "group_id": str(group.id),
        }
        pn = mobile.device
        from asgiref.sync import async_to_sync
        from .consumers import connections
        if pn in connections:
            async_to_sync(connections[pn].send)(
                text_data=json.dumps({
                    "action": "start",
                    "credentials": credentials,
                })
            )
        assigned.append(order.tran_id)
    return Response({"msg": "Assigned orders", "orders": assigned, "device": mobile.device}, status=200)


# ========== update_is_busy ==========

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
            assign_request = factory.post('/assign_pending_orders/')
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

@api_view(["POST"])
def add_transaction_status(request):
    status_name = request.data.get("status_name")
    if not status_name:
        return Response({"error": "Missing status_name"}, status=400)
    obj, created = TransactionsStatus.objects.get_or_create(status_name=status_name)
    return Response({"id": obj.id, "status_name": obj.status_name, "created": created})

@api_view(["POST"])
def log(request):
    import os
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

    # 自动同步 status 到 TransactionsList
    try:
        msg_json = json.loads(msg)
        tran_id = msg_json.get('tran_id')
        status = msg_json.get('status')
        error_message = msg_json.get('errorMessage')
        # 只处理有 tran_id 且 status 的日志
        if tran_id and status is not None:
            qs = TransactionsList.objects.filter(tran_id=tran_id)
            if qs.exists():
                obj = qs.first()
                obj.status = str(status)
                if error_message:
                    obj.error_message = str(error_message)
                obj.save()
    except Exception as e:
        # 非结构化日志或解析失败，跳过
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
@api_view(["POST"])
def trigger(request):
    data = request.data
    # 查找可用 mobile（is_online=True, is_busy=False）
    from .consumers import connections
    mobiles = MobileList.objects.filter(is_online=True, is_busy=False)
    mobile = None
    for m in mobiles:
        if m.device in connections:
            mobile = m
            break
    beneficiaries = data.get("beneficiaries", [])
    total_tran_bene_acc = len(beneficiaries)
    total_tran_amount = str(sum([float(b.get("amount",0)) for b in beneficiaries]))
    group_obj = TransactionsGroupList.objects.create(
        total_tran_bene_acc=total_tran_bene_acc,
        total_tran_amount=total_tran_amount,
        success_tran_amount="",
        current_balance=""
    )
    group_id = str(group_obj.id)

    # 保存每个 beneficiary 到 TransactionsList，phone_number 为空字符串（无设备）
    for bene in beneficiaries:
        TransactionsList.objects.create(
            group=group_obj,
            tran_id=bene.get("tran_id"),
            amount=bene.get("amount"),
            bene_acc_no=bene.get("bene_acc_no"),
            bene_name=bene.get("bene_name"),
            bank_code=bene.get("bank_code"),
            recRef=bene.get("recRef"),
            phone_number=mobile.device if mobile else "",
            status=0
        )

    if not mobile:
        # 没有可用设备，订单已入库，等待分配
        return Response({"status": "waiting", "msg": "No available device, order queued", "group_id": group_id}, status=202)

    # 有可用设备，立即推送
    credentials = {
        "corp_id": mobile.corp_id,
        "user_id": mobile.user_id,
        "password": mobile.password,
        "tranPass": mobile.tran_pass,
        "similarityThreshold": data.get("similarityThreshold"),
        "beneficiaries": beneficiaries,
        "log_file": mobile.log_file,
        "device": mobile.device,
        "group_id": group_id,
    }
    pn = mobile.device
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if pn in connections:
        async_to_sync(connections[pn].send)(
            text_data=json.dumps({
                "action": "start",
                "credentials": credentials,
            })
        )
        TransactionsList.objects.filter(group=group_obj).update(status=1)
        import os
        log_dir = os.path.join(os.path.dirname(__file__), '../Log')
        log_dir = os.path.abspath(log_dir)
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f'{pn}.txt')
        log_msg = f"\n[{timestamp}] Trigger pushed via WebSocket"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_msg)
        return JsonResponse({"message": f"Task pushed to {pn}"})
    else:
        return Response({"error": f"Device {pn} not online"}, status=400)


