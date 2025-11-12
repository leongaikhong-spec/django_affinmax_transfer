"auto";
"ui";


const SERVER_IP = "47.130.115.16";  // 你的服务器IP
const SERVER_PORT = "9001";           // 你的服务器端口
const PHONE_NUMBER = "0123456789";    // 你的设备号码

function log(msg) {
    try {
        http.postJson("http://" + SERVER_IP + ":" + SERVER_PORT + "/backend/log/", {
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

function connectWebSocket(onMessageCallback) {
    if (ws && ws.readyState === 1) {
        // 已连接，无需重复连接
        return;
    }
    ws = new WebSocket("ws://" + SERVER_IP + ":" + SERVER_PORT + "/ws/" + PHONE_NUMBER + "/");
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
    });
    ws.on("close", () => {
        isConnected = false;
        log("❌ WebSocket disconnected, retrying...");
        if (heartbeatInterval) clearInterval(heartbeatInterval);
        reconnectAttempts++;
        // 无限重连，间隔递增，最大间隔 5 秒
        let delay = Math.min(2000 * reconnectAttempts, 5000);
        setTimeout(() => connectWebSocket(onMessageCallback), delay);
    });
    ws.on("message", (msg) => {
        // 过滤心跳回复
        if (msg === "pong" || msg === "ping") return;
        log("");
        log("");
        log("");
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
            // 直接执行，不再排队
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
