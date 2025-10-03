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


should_run_script_map = {}
credentials_map = {}

# ========== trigger ==========
@swagger_auto_schema(
    method="post",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "corp_id": openapi.Schema(type=openapi.TYPE_STRING),
            "user_id": openapi.Schema(type=openapi.TYPE_STRING),
            "password": openapi.Schema(type=openapi.TYPE_STRING),
            "tranPass": openapi.Schema(type=openapi.TYPE_STRING),
            "similarityThreshold": openapi.Schema(type=openapi.TYPE_NUMBER),
            "beneficiaries": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(   # ✅ 这里应该是 Schema，而不是 Items
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
        required=["tran_id", "amount", "bene_acc_no", "bene_name", "bank_code", "recRef"],
    ),
    responses={200: "Trigger set"},
)
@api_view(["POST"])
def trigger(request, pn):
    data = request.data
    credentials = {
        "corp_id": data.get("corp_id"),
        "user_id": data.get("user_id"),
        "password": data.get("password"),
        "tranPass": data.get("tranPass"),
        "similarityThreshold": data.get("similarityThreshold"),
        "beneficiaries": data.get("beneficiaries", []),
    }
    credentials_map[pn] = credentials

    last_group = TransferList.objects.aggregate(Max('group_id'))['group_id__max']
    try:
        new_group_id = str(int(last_group) + 1) if last_group else "1"
    except (TypeError, ValueError):
        new_group_id = "1"

    beneficiaries = data.get("beneficiaries", [])
    for bene in beneficiaries:
        TransferList.objects.create(
            group_id=new_group_id,
            tran_id=bene.get("tran_id"),
            amount=bene.get("amount"),
            bene_acc_no=bene.get("bene_acc_no"),
            bene_name=bene.get("bene_name"),
            bank_code=bene.get("bank_code"),
            recRef=bene.get("recRef"),
            phone_number=pn
        )

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ✅ 如果设备在线，直接通过 WebSocket 推送
    if pn in connections:
        async_to_sync(connections[pn].send)(
            text_data=json.dumps({
                "action": "start",
                "credentials": credentials,
            })
        )
        log_msg = f"[{timestamp}] Trigger pushed via WebSocket"
        with open(f"{pn}.txt", "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")
        return JsonResponse({"message": f"Task pushed to {pn} (via WebSocket)"})

    # ❌ 如果设备不在线，走原有轮询机制
    should_run_script_map[pn] = True
    with open(f"{pn}.txt", "a", encoding="utf-8") as f:
        f.write(f"\n[{timestamp}] Trigger stored (waiting for pull)\n")

    return Response({"message": f"Trigger stored for {pn}"})


# ========== run_script ==========
@swagger_auto_schema(
    method="get",
    manual_parameters=[
        openapi.Parameter("pn", openapi.IN_QUERY, description="Phone number", type=openapi.TYPE_STRING),
    ],
    responses={200: "Script action"},
)
@api_view(["GET"])
def run_script(request):
    pn = request.GET.get("pn")
    if not pn:
        return Response({"error": "Missing phone number (pn)"}, status=400)

    if should_run_script_map.get(pn):
        should_run_script_map[pn] = False
        return Response({
            "action": "start",
            "credentials": credentials_map.get(pn)
        })
    else:
        return Response({"action": "wait"})


# ========== receive_log ==========
@swagger_auto_schema(
    method="post",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "pn": openapi.Schema(type=openapi.TYPE_STRING),
            "message": openapi.Schema(type=openapi.TYPE_STRING),
        },
        required=["pn", "message"],
    ),
    responses={200: "Log stored"},
)
@api_view(["POST"])
def receive_log(request):
    data = request.data
    pn = data.get("pn", "unknown")
    message = data.get("message", "")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_line = f"[{timestamp}] {message}"


    # ✅ 也写 txt
    with open(f"{pn}.txt", "a", encoding="utf-8") as f:
        f.write(log_line + "\n")

    return Response({"status": "ok"})
