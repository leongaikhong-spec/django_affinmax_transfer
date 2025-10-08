"auto";
"ui";

const SERVER_IP = "192.168.100.162";  // 你的服务器IP
const PHONE_NUMBER = "0123456789";    // 你的设备号码

function log(msg) {
    try {
        http.postJson("http://" + SERVER_IP + ":3000/log/", {
            device: PHONE_NUMBER,
            message: msg
        });
    } catch (e) {
        console.error("❌ Failed to send log: " + e);
    }
    console.log(msg);
}

let ws;
let isConnected = false;
let heartbeatInterval = null;
let reconnectAttempts = 0;
const MAX_RECONNECT = 5;
let pendingData = null; // 保留未派单数据

function connectWebSocket(onMessageCallback) {
    if (ws && ws.readyState === 1) {
        // 已连接，无需重复连接
        // 如果有未派单数据，自动派单
        if (pendingData) {
            sendTransfer(pendingData);
            pendingData = null;
        }
        return;
    }
    ws = new WebSocket("ws://" + SERVER_IP + ":3000/ws/" + PHONE_NUMBER + "/");
    ws.on("open", () => {
        isConnected = true;
        reconnectAttempts = 0;
        log("");
        log("✅ WebSocket connected");
        log("");
        // 启动心跳
        if (heartbeatInterval) clearInterval(heartbeatInterval);
        heartbeatInterval = setInterval(() => {
            if (ws && ws.readyState === 1) {
                ws.send(JSON.stringify({type: "ping", device: PHONE_NUMBER}));
            }
        }, 5000); // 每 5 秒心跳
        // 如果有未派单数据，自动派单
        if (pendingData) {
            sendTransfer(pendingData);
            pendingData = null;
        }
    });
    ws.on("close", () => {
        isConnected = false;
        log("❌ WebSocket disconnected, retrying...");
        if (heartbeatInterval) clearInterval(heartbeatInterval);
        if (reconnectAttempts < MAX_RECONNECT) {
            reconnectAttempts++;
            setTimeout(() => connectWebSocket(onMessageCallback), 2000 * reconnectAttempts); // 指数退避
        } else {
            log("❌ Too many reconnect attempts, please check network or server.");
        }
    });
    ws.on("message", (msg) => {
        // 过滤心跳回复
        if (msg === "pong" || msg === "ping") return;
        log("📩 Received message: " + msg);
        let json;
        try {
            json = JSON.parse(msg);
        } catch (err) {
            log("❌ JSON parse error: " + err);
            return;
        }
        if (json.action === "start") {
            let data = json.credentials || {};
            // 始终直接调用 sendTransfer，确保每次都能执行
            sendTransfer(data);
        }
    });
    ws.on("error", (e) => {
        isConnected = false;
        log("❌ WebSocket error: " + e);
    });
}

function startListener(onMessageCallback) {
    connectWebSocket(onMessageCallback);
}

// 启动 listener，收到消息时执行 transfer.js，先检查连接状态
startListener((data) => {
    // 逻辑已在 ws.on("message") 里直接调用 sendTransfer，无需重复判断
});

function sendTransfer(data) {
    log("🚀 Launching transfer.js...");
    let jsonString = JSON.stringify(data);
    engines.execScript("Transfer Script", `
        let data = ${jsonString};
        let transfer = require("./affinmax_transfer.js");
        transfer.run_transfer_process(data);
    `);
}

// 防止退出
setInterval(() => {}, 1000);
