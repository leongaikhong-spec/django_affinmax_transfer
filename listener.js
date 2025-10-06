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
const MAX_RECONNECT = 20;

function connectWebSocket(onMessageCallback) {
    if (ws && ws.readyState === 1) {
        // 已连接，无需重复连接
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
        }, 15000); // 每 15 秒心跳
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
            onMessageCallback(data);
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
    if (!isConnected || !ws || ws.readyState !== 1) {
        log("❌ WebSocket not connected, retrying before running transfer.js...");
        connectWebSocket((reData) => {
            log("✅ Reconnected, running transfer.js...");
            let jsonString = JSON.stringify(reData);
            engines.execScript("Transfer Script", `
                let data = ${jsonString};
                let transfer = require("./affinmax_transfer.js");
                transfer.run_transfer_process(data);
            `);
        });
    } else {
        log("🚀 Launching transfer.js...");
        let jsonString = JSON.stringify(data);
        engines.execScript("Transfer Script", `
            let data = ${jsonString};
            let transfer = require("./affinmax_transfer.js");
            transfer.run_transfer_process(data);
        `);
    }
});

// 防止退出
setInterval(() => {}, 1000);
