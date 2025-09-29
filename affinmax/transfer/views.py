from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
import json

should_run_script_map = {}
credentials_map = {}

@csrf_exempt
def trigger(request, pn):
    if request.method == "POST":
        data = json.loads(request.body)
        credentials_map[pn] = {
            "corp_id": data.get("corp_id"),
            "user_id": data.get("user_id"),
            "password": data.get("password"),
            "tranPass": data.get("tranPass"),
            "similarityThreshold": data.get("similarityThreshold"),
            "beneficiaries": data.get("beneficiaries", []),
        }
        should_run_script_map[pn] = True
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(f"{pn}.txt", "a", encoding="utf-8") as f:
            f.write(f"\n[{timestamp}] Trigger received\n")

        return JsonResponse({"message": f"Trigger set for {pn}"})
    return JsonResponse({"error": "Invalid request"}, status=400)


def run_script(request):
    pn = request.GET.get("pn")
    if not pn:
        return JsonResponse({"error": "Missing phone number (pn)"}, status=400)

    if should_run_script_map.get(pn):
        should_run_script_map[pn] = False
        return JsonResponse({
            "action": "start",
            "credentials": credentials_map.get(pn)
        })
    else:
        return JsonResponse({"action": "wait"})


@csrf_exempt
def receive_log(request):
    if request.method == "POST":
        data = json.loads(request.body)
        pn = data.get("pn", "unknown")
        message = data.get("message", "")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log_line = f"[{timestamp}] {message}"

        with open(f"{pn}.txt", "a", encoding="utf-8") as f:
            f.write(log_line + "\n")

        return JsonResponse({"status": "ok"})
    return JsonResponse({"error": "Invalid request"}, status=400)
