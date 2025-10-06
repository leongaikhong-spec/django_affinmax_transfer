from rest_framework.decorators import api_view
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from datetime import datetime
from django.http import JsonResponse
from asgiref.sync import async_to_sync
from .consumers import connections
from .models import TransferList, MobileList
from django.db.models import Max
import json

# ========== log ==========
from rest_framework.decorators import api_view
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
    for field in ["is_online", "is_activated", "is_busy"]:
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
    # 查找可用 mobile（is_busy=0）
    mobile = MobileList.objects.filter(is_busy=False).first()
    if not mobile:
        return Response({"error": "No available mobile device"}, status=400)

    # 组装 credentials
    credentials = {
        "corp_id": mobile.corp_id,
        "user_id": mobile.user_id,
        "password": mobile.password,
        "tranPass": mobile.tran_pass,
        "similarityThreshold": data.get("similarityThreshold"),
        "beneficiaries": data.get("beneficiaries", []),
        "log_file": mobile.log_file,
        "device": mobile.device,
    }
    pn = mobile.device


    beneficiaries = data.get("beneficiaries", [])
    # 保存单次转账的 group 记录
    from .models import TransferGroupList
    total_tran = len(beneficiaries)
    total_tran_amount = str(sum([float(b.get("amount",0)) for b in beneficiaries]))
    group_obj = TransferGroupList.objects.create(
        total_tran=total_tran,
        total_tran_amount=total_tran_amount,
        success_tran_amount="",
        current_balance=""
    )
    group = str(group_obj.id)
    # 保存每个 beneficiary 到 TransferList
    for bene in beneficiaries:
        TransferList.objects.create(
            group=group_obj,  # 不是 group_id=group_id，也不是 group_id=group_obj.id
            tran_id=bene.get("tran_id"),
            amount=bene.get("amount"),
            bene_acc_no=bene.get("bene_acc_no"),
            bene_name=bene.get("bene_name"),
            bank_code=bene.get("bank_code"),
            recRef=bene.get("recRef"),
            phone_number=pn,
            status=bene.get("success", "fail")
        )

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 只保留 WebSocket 推送和日志
    if pn in connections:
        async_to_sync(connections[pn].send)(
            text_data=json.dumps({
                "action": "start",
                "credentials": credentials,
            })
        )
        import os
        log_dir = os.path.join(os.path.dirname(__file__), '../Log')
        log_dir = os.path.abspath(log_dir)
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f'{pn}.txt')
        log_msg = f"[\n{timestamp}] Trigger pushed via WebSocket"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_msg)
        return JsonResponse({"message": f"Task pushed to {pn}"})
    else:
        return Response({"error": f"Device {pn} not online"}, status=400)




