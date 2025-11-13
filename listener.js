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
let heartbeatTimer = null;  // 用于存储心跳定时器
let wsReady = false;  // 手动跟踪 WebSocket 状态

function connectWebSocket(onMessageCallback) {
    if (ws && wsReady) {
        // 已连接，无需重复连接
        return;
    }
    
    wsReady = false;
    ws = new WebSocket("ws://" + SERVER_IP + ":" + SERVER_PORT + "/ws/" + PHONE_NUMBER + "/");
    
    // 心跳发送函数
    function sendHeartbeat() {
        if (wsReady && ws) {
            try {
                ws.send(JSON.stringify({type: "ping", device: PHONE_NUMBER}));
                heartbeatTimer = setTimeout(sendHeartbeat, 5000);  // 5秒后再次发送
            } catch (e) {
                log("❌ Heartbeat send failed: " + e);
                wsReady = false;  // 标记为不可用
            }
        }
    }
    
    ws.on("open", () => {
        wsReady = true;  // 标记为已连接
        isConnected = true;
        reconnectAttempts = 0;
        log("");
        log("✅ WebSocket connected");
        log("");
        
        // 清除旧的心跳定时器（如果有）
        if (heartbeatTimer) {
            clearTimeout(heartbeatTimer);
            heartbeatTimer = null;
        }
        
        // 立即发送一次心跳测试
        try {
            ws.send(JSON.stringify({type: "ping", device: PHONE_NUMBER}));
        } catch (e) {
            log("❌ Initial heartbeat failed: " + e);
        }
        
        // 5秒后启动定期心跳
        heartbeatTimer = setTimeout(sendHeartbeat, 5000);
    });
    ws.on("close", () => {
        wsReady = false;  // 标记为已断开
        isConnected = false;
        log("❌ WebSocket disconnected, retrying...");
        // 清除心跳定时器
        if (heartbeatTimer) {
            clearTimeout(heartbeatTimer);
            heartbeatTimer = null;
        }
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
        wsReady = false;  // 标记为出错
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
