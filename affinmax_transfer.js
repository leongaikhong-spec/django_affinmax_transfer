"auto";
"ui";

const SERVER_IP = "47.130.115.16";  // Device IP Address
const SERVER_PORT = "9001";           // 你的服务器端口
const PHONE_NUMBER = "0123456789";    // Current device phone number

// AWS S3 配置 - 密钥将从后端获取
const S3_CONFIG = {
    "BucketName": "onepayrobot",
    "Region": "ap-southeast-1"
};

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

let error_status = "2";
let message = "Transaction Success";
let errorMessage = "Transaction Success";
let balance = null;

// 记录已上传 status 的 tran_id
let failedTranIds = [];

function safeInput(field, text) {
    if (field) {
        field.setText("");
        sleep(200);
        field.setText(text);
        sleep(200);
    } else {
        throw new Error("Field not found for input: " + text);
    }
}

function toNumber(val) {
    if (!val) return NaN;
    if (typeof val === "number") return val;
    if (typeof val === "string") {
        val = val.trim().replace(/[^\d.]/g, '');
        return parseFloat(val);
    }
    return NaN;
}

function scroll(startRatio = 0.8, endRatio = 0.5, duration = 500, direction = "vertical") {
    if (direction === "horizontal") {
        // 横向滑动：从右到左
        swipe(
            device.width * startRatio,
            device.height / 2,
            device.width * endRatio,
            device.height / 2,
            duration
        );
    } else {
        // 纵向滑动：从下到上
        swipe(
            device.width / 2,
            device.height * startRatio,
            device.width / 2,
            device.height * endRatio,
            duration
        );
    }
}

function close_app() {
    // 打开任务界面
    recents();
    sleep(1000);
    scroll(0.5, 0.2, 100, "horizontal"); // 横向滑动

    // 找到 AFFINMAX 卡片并向上滑动关闭
    let taskCard = id("task_icon").desc("Advanced options, AFFINMAX, Button").findOne(5000);
    if (taskCard) {

        sleep(1000);
        scroll(0.6, 0.2, 200); // 向上滑动关闭
        sleep(1000);
        home();

        log("-".repeat(74));
        log("✅ Closed AFFINMAX app from recents");
        log("-".repeat(74));

    } else {
        log("❌ AFFINMAX task card not found in recents");

        set_is_busy(0); // 流程结束后才设为 0
        exit(); // Exit the script after closing the app
    }
}

function complete_process() {
    set_is_busy(0); // 流程结束后才设为 0
    log("✅ Transaction process completed");
    exit(); // Exit the script after closing the app
}

function stringSimilarity(a, b) {
    // change to lower case and remove spaces
    a = a.toLowerCase().replace(/\s+/g, "");
    b = b.toLowerCase().replace(/\s+/g, "");

    let longer = a.length > b.length ? a : b;
    let shorter = a.length > b.length ? b : a;
    let longerLength = longer.length;
    if (longerLength === 0) return 1.0;

    return (longerLength - editDistance(longer, shorter)) / parseFloat(longerLength);
}

function editDistance(s1, s2) {
    s1 = s1.toLowerCase();
    s2 = s2.toLowerCase();

    let costs = [];
    for (let i = 0; i <= s1.length; i++) {
        let lastValue = i;
        for (let j = 0; j <= s2.length; j++) {
            if (i === 0)
                costs[j] = j;
            else {
                if (j > 0) {
                    let newValue = costs[j - 1];
                    if (s1.charAt(i - 1) !== s2.charAt(j - 1))
                        newValue = Math.min(Math.min(newValue, lastValue),
                            costs[j]) + 1;
                    costs[j - 1] = lastValue;
                    lastValue = newValue;
                }
            }
        }
        if (i > 0)
            costs[s2.length] = lastValue;
    }
    return costs[s2.length];
}

// ------ Utility functions for backend sync ------

// 🔔 发送单个callback - 只传递核心字段
function send_single_callback(status, tran_id, message, errorMessage) {
    try {
        let callbackData = {
            status: String(status),
            tran_id: String(tran_id),
            message: message,
            errorMessage: errorMessage
        };
        
        // 设置5秒超时，避免等待过久
        let response = http.postJson(
            "http://" + SERVER_IP + ":" + SERVER_PORT + "/backend/send_callback/", 
            callbackData,
            {
                headers: {'Content-Type': 'application/json'},
                timeout: 1000  // 1秒超时
            }
        );
        if (response && response.statusCode === 200) {
            log("✅ Callback sent for tran_id: " + tran_id + " with status: " + status);
        } else {
            log("⚠️ Callback may have failed for tran_id: " + tran_id);
        }
    } catch (e) {
        log("❌ Failed to send callback for tran_id " + tran_id + ": " + e);
    }
}

// ------ Utility functions for backend sync ------


// AWS S3 上传函数
function uploadToS3(filePath, fileName, tran_id) {
    try {
        // 检查文件是否存在
        if (!files.exists(filePath)) {
            log("❌ File does not exist: " + filePath);
            return false;
        }

        // 读取文件为字节数组
        let fileBytes = files.readBytes(filePath);
        if (!fileBytes) {
            log("❌ Failed to read file bytes: " + filePath);
            return false;
        }

        // 将字节数组转换为 base64
        let base64Data = android.util.Base64.encodeToString(fileBytes, android.util.Base64.NO_WRAP);
        
        // 构建上传请求
        let uploadResponse = null;
        try {
            uploadResponse = http.postJson("http://" + SERVER_IP + ":" + SERVER_PORT + "/backend/upload_s3/", {
                device: PHONE_NUMBER,
                fileName: fileName,
                fileData: base64Data,
                bucketName: S3_CONFIG.BucketName,
                tran_id: tran_id
            });
        } catch (httpError) {
            log("❌ HTTP request failed: " + httpError.toString());
            return false;
        }
        
        if (uploadResponse) {
            
            if (uploadResponse.statusCode === 200) {
                log("✅ Successfully uploaded " + fileName + "to S3 ");
                return true;
            } else {
                log("❌ Upload failed with status: " + uploadResponse.statusCode);
                // 显示错误信息
                if (uploadResponse.body && uploadResponse.body.message) {
                    log("📤 Server message: " + uploadResponse.body.message);
                }
                return false;
            }
        } else {
            log("❌ No response received from server");
            return false;
        }
        
    } catch (e) {
        log("❌ Error uploading to S3: " + e.toString());
        return false;
    }
}

function upload_transfer_log(beneficiaries, failedTranIds, error_status, message, errorMessage, balance) {
    if (typeof beneficiaries !== "undefined" && Array.isArray(beneficiaries)) {
        beneficiaries.forEach(function (bene) {
            if (!failedTranIds.includes(String(bene.tran_id))) {
                http.postJson("http://" + SERVER_IP + ":" + SERVER_PORT + "/backend/log/", {
                    device: PHONE_NUMBER,
                    message: JSON.stringify({
                        status: error_status,
                        tran_id: String(bene.tran_id),
                        message: message,
                        errorMessage: errorMessage
                        // 不再显示 balance 字段
                    })
                });
            }
        });
    } else {
        log(JSON.stringify({
            status: error_status,
            message: message,
            errorMessage: errorMessage
            // 不再显示 balance 字段
        }));
    }
}

function calc_success_amount(beneficiaries, failedTranIds) {
    let successAmount = 0;
    if (typeof beneficiaries !== "undefined" && Array.isArray(beneficiaries)) {
        beneficiaries.forEach(function (bene) {
            if (!failedTranIds.includes(String(bene.tran_id))) {
                successAmount += toNumber(bene.amount);
            }
        });
    }
    return successAmount;
}

function update_backend_group_and_balance(group_id, successAmount, balance) {
    if (typeof group_id !== "undefined") {
        http.postJson("http://" + SERVER_IP + ":" + SERVER_PORT + "/backend/update_group_success_amount/", {
            group_id: String(group_id),
            success_tran_amount: String(successAmount)
        });
        // 用 grab_balance() 获取最新余额
        let final_balance = typeof balance !== "undefined" ? balance : grab_balance();
        http.postJson("http://" + SERVER_IP + ":" + SERVER_PORT + "/backend/update_current_balance/", {
            device: PHONE_NUMBER,
            group_id: String(group_id),
            current_balance: final_balance  // send as number or null, not string "null"
        });
    }
}

// 设置 is_busy 状态
function set_is_busy(val) {
    try {
        http.postJson("http://" + SERVER_IP + ":" + SERVER_PORT + "/backend/update_is_busy/", {
            device: PHONE_NUMBER,
            is_busy: val
        });
        log(`✅ Set is_busy = ${val}`);
    } catch (e) {
        log(`❌ Failed to set is_busy = ${val}: ` + e);
    }
}




// 加stay在主页有单就pass掉login的process

// ------ Automation functions start here ------
function transfer_info(beneficiaries) {

    for (let i = 0; i < beneficiaries.length; i++) {
        let bene = beneficiaries[i];
        log("➡️ Beneficiary Details " + (i + 1));
        log("   Transfer ID     : " + bene.tran_id);
        log("   Name            : " + bene.bene_name);
        log("   Account No      : " + bene.bene_acc_no);
        log("   Transfer Amount : " + bene.amount);
        log("   Bank Code       : " + bene.bank_code);
        log("-".repeat(74));
    }
}

function open_app() {
    auto.waitFor();
    app.launchPackage("com.affin.ntbs");
    log("✅ Opened AffinMax app");
    //sleep(3000);
}

// function close_notify() {
//     let fallbackBtn = id("ab9d4931-56e0-419b-8e44-2f3a8cda6826").findOnce();
//     if (fallbackBtn) {
//         fallbackBtn.click();
//         log("✅ Clicked close notify button.");
//     }
// }

function fill_corporate_and_user_id(corp_id, user_id) {
    let corpIdLayout = id("fit_corp_id").findOne(60000);
    let corpIdField = corpIdLayout.findOne(className("android.widget.EditText"));
    safeInput(corpIdField, corp_id);
    log("✅ Filled corporate ID");

    let userIdLayout = id("fit_user_id").findOne(60000);
    let userIdField = userIdLayout.findOne(className("android.widget.EditText"));
    safeInput(userIdField, user_id);
    log("✅ Filled user ID");

    id("btn_next").findOne(60000).click();
    log("✅ Clicked next button");
}

function fill_password(password) {
    log("👉 Filling login password...");
    let pwdLayout = id("fit_password").findOne(60000);
    let pwdField = pwdLayout.findOne(className("android.widget.EditText"));
    safeInput(pwdField, password);
    log("✅ Password filled");

    id("btn_login").findOne(60000).click();
    log("✅ Clicked login button");
}

function show_balance() {
    //sleep(1000);
    let balanceBtn = id("ib_masking_balance").findOne(60000);
    if (balanceBtn) {
        //click(465, 410); 
        balanceBtn.click();
        log("✅ Clicked Show Balance button");
    }
}

function check_balance(beneficiaries) {
    let start = new Date().getTime();
    let balanceValue = null;
    let balanceText = "";
    let balanceTextView = null;
    let found = false;
    while (new Date().getTime() - start < 60000) { // 最多等60秒
        balanceTextView = id("tv_total_available_balance").findOne(1000);
        if (balanceTextView) {
            balanceText = balanceTextView.text();
            balanceValue = toNumber(balanceText);
            if (!isNaN(balanceValue) && balanceValue !== null) {
                found = true;
                break;
            } else {
                throw new Error("Cannot capture valid balance");
            }
        } else {
            throw new Error("Cannot capture valid balance");
        }
    }
    if (!found) {
        log("❌ Unable to retrieve valid balance after 60 seconds, skip insufficient balance check");
        return null;
    }
    // Calculate total transfer amount
    let totalAmount = 0;
    for (let i = 0; i < beneficiaries.length; i++) {
        totalAmount += toNumber(beneficiaries[i].amount);
    }
    log("💰 Current balance: " + balanceValue + " | Total transfer amount: " + totalAmount);
    if (totalAmount > balanceValue) {
        log("❌ Insufficient balance, stopping transfer");
        return balanceValue; // ❌ 余额不足，返回 null
    } else {
        log("✅ Balance is sufficient, continue transfer");
        return balanceValue; // ✅ 返回数字余额
    }
}

function click_duit_now() {
    let duitNowBtn = id("rl_container").findOne(60000);
    if (!duitNowBtn) {
        log("❌ DuitNow button not found after 60 seconds");
        throw new Error("DuitNow button not found");
    }
    duitNowBtn.click();
    log("✅ Clicked DuitNow button");
    sleep(500);

    let duitNowTransferBtn = id("tv_label").text("DuitNow Transfer").findOne(60000);
    if (duitNowTransferBtn) {
        let center = duitNowTransferBtn.center();
        click(center.x, center.y);
        log(`✅ Clicked DuitNow Transfer button at (${center.x}, ${center.y})`);
        sleep(500);
    } else {
        log("❌ DuitNow Transfer button not found after 60 seconds");
        throw new Error("DuitNow Transfer button not found");
    }

    let payToAccountBtn = id("tv_label").text("Pay to Account").findOne(60000);
    if (payToAccountBtn) {
        let center = payToAccountBtn.center();
        click(center.x, center.y);
        log(`✅ Clicked Pay to Account button at (${center.x}, ${center.y})`);
        sleep(500);
    } else {
        log("❌ Pay to Account button not found after 60 seconds");
        throw new Error("Pay to Account button not found");
    }

    let newTransferBtn = id("tv_label").text("New Transfer").findOne(60000);
    if (newTransferBtn) {
        let center = newTransferBtn.center();
        click(center.x, center.y);
        log(`✅ Clicked New Transfer button at (${center.x}, ${center.y})`);
        sleep(500);
    } else {
        log("❌ New Transfer button not found after 60 seconds");
        throw new Error("New Transfer button not found");
    }

    if (!id("text_input_end_icon").findOne(60000)) {

    }
    log("✅ Bank selection button found");
}

function transaction_details() {
    id('text_input_end_icon').findOne(60000).click();
    log("✅ Clicked dropdown button");

    //sleep(1000);
    //click(360, 395);
    let debitAcc = id("btn_balance_inquiry").text("Balance Inquiry").findOne(60000);
    if (debitAcc) {
        let center = debitAcc.center();
        sleep(1000);
        click(center.x, center.y);
        log(`✅ Chosen debit from account no./currency at (${center.x}, ${center.y})`);
    } else {
        log("❌ Debit from account no./currency option not found");
        throw new Error("Debit from account no./currency option not found");
    }
}

function add_beneficiary_button() {
    id('btn_add_bene').findOne(60000).click();
    log("✅ Clicked Add Beneficiary button");
}

function choose_open_bene() {
    // // 首先确认是否在 Beneficiary 页面
    // let title = id("tv_bene_details").findOne(60000);
    // if (!title) {
    //     log("❌ Not on Beneficiary page (tv_bene_details not found)");
    //     throw new Error("Not on Beneficiary page - tv_bene_details element not found");
    // }
    
    // if (title.text() !== "Beneficiary") {
    //     log("❌ Not on correct Beneficiary page, title text is: " + title.text());
    //     throw new Error("Not on correct Beneficiary page - expected 'Beneficiary' but got: " + title.text());
    // }
    
    // log("✅ Confirmed on Beneficiary page");

    // 点击选择受益人类型，并确保 btn_select_favourite_bene 消失
    let startTime = new Date().getTime();
    let timeout = 60000; // 60秒超时
    let favouriteBeneBtn = null;
    
    do {
        // 点击 rb_open_bene
        let openBeneBtn = id('rb_open_bene').findOne(60000);
        if (openBeneBtn) {
            openBeneBtn.click();
            log("✅ Clicked rb_open_bene (Open Beneficiary)");
            sleep(500);
        } else {
            log("❌ rb_open_bene button not found");
            throw new Error("rb_open_bene button not found");
        }
        
        // 检查是否还有 btn_select_favourite_bene
        favouriteBeneBtn = id('btn_select_favourite_bene').findOne(1000);
        
        if (favouriteBeneBtn) {
            log("⚠️ btn_select_favourite_bene still exists, retrying rb_open_bene...");
        } else {
            log("✅ btn_select_favourite_bene not found, continuing to next step");
            break;
        }
        
        // 检查是否超时
        if (new Date().getTime() - startTime > timeout) {
            log("❌ Timeout: Failed to remove btn_select_favourite_bene after 60 seconds");
            throw new Error("Timeout: Failed to remove btn_select_favourite_bene after 60 seconds");
        }
        
    } while (favouriteBeneBtn);
    
    log("✅ Chosen beneficiary type");
}

function beneficiary_details(amount, accNo, name) {
    id('text_input_end_icon').findOne(60000).click();
    log("✅ Clicked dropdown button for transaction type");

    // sleep(1000);
    // click(200, 466);
    let transType = id("fic_transaction_amount").findOne(60000);
    if (transType) {
        let center = transType.center();
        sleep(1000);
        click(center.x, center.y);
        log(`✅ Chosen transaction type at (${center.x}, ${center.y})`);
    } else {
        log("❌ Transaction type option not found");
        throw new Error("Transaction type option not found");
    }

    let transAmount = id("fic_transaction_amount").findOne(60000);
    let amountField = transAmount.findOne(className("android.widget.EditText"));
    safeInput(amountField, amount);
    log("✅ Filled transaction amount");

    let beneAcc = id("fit_bene_acc_no").findOne(60000);
    let accNoField = beneAcc.findOne(className("android.widget.EditText"));
    safeInput(accNoField, accNo);
    log("✅ Filled beneficiary account no");

    let beneName = id("fit_bene_name").findOne(60000);
    let nameField = beneName.findOne(className("android.widget.EditText"));
    safeInput(nameField, name);
    log("✅ Filled beneficiary name");
}

function choose_bank(bankCode) {
    let bankMap = {
        1: "AEON BANK",
        2: "AFFIN BANK BERHAD",
        3: "AGROBANK",
        4: "AL RAJHI BANK  INV CORP BHD",
        5: "ALLIANCE BANK MALAYSIA BHD",
        6: "AMBANK BHD",
        7: "BANK ISLAM MALAYSIA BERHAD",
        8: "BANK KERJASAMA RAKYAT",
        9: "BANK MUAMALAT MALAYSIA BHD",
        10: "BANK OF AMERICA (MALAYSIA) BERHAD",
        11: "BANK OF CHINA (MALAYSIA) BHD",
        12: "BANK SIMPANAN NASIONAL BERHAD",
        13: "BNP PARIBAS MALAYSIA BERHAD",
        14: "BOOST BANK",
        15: "BEEZFINTECH",
        16: "BIGPAY",
        17: "BOOST EWALLET",
        18: "CHINA CONSTRUCTION BANK (MALAYSIA) BERHAD",
        19: "CIMB BANK BERHAD",
        20: "CITIBANK",
        21: "CO-OPBANK PERTAMA",
        22: "CURLEC",
        23: "DEUTSCHE BANK (MALAYSIA) BHD",
        24: "FASSPAY",
        25: "FAVE",
        26: "FINEXUS",
        27: "GHL",
        28: "GLOBAL PAYMENTS ASIA-PACIFIC",
        29: "GX BANK",
        30: "GRABPAY",
        31: "HONG LEONG BANK",
        32: "HSBC BANK MALAYSIA BHD",
        33: "IND & COMM BANK OF CHINA",
        34: "INSTAPAY",
        35: "J.P MORGAN CHASE BANK BERHAD",
        36: "KAF DIGITAL BANK BERHAD",
        37: "KUWAIT FINANCE HOUSE (MALAYSIA) BERHAD",
        38: "KIPLEPAY",
        39: "MAYBANK",
        40: "MBSB BANK BERHAD",
        41: "MIZUHO BANK (MALAYSIA) BERHAD",
        42: "MUFG BANK (MALAYSIA) BERHAD",
        43: "MERCHANTRADE",
        44: "MOBILITYONE",
        45: "OCBC BANK",
        46: "PIDM",
        47: "PUBLIC BANK",
        48: "PAYEX",
        49: "RHB BANK",
        50: "RAZER MERCHANT SERVICES",
        51: "REVENUE",
        52: "RYT BANK",
        53: "STANDARD CHARTERED BANK",
        54: "SUMITOMO MITSUI BANK BHD",
        55: "SETEL",
        56: "SHOPEE",
        57: "SILICONNET",
        58: "STRIPE",
        59: "TOUCH N GO EWALLET",
        60: "UNITED OVERSEAS BANK BERHAD",
        61: "UNIPIN",
        62: "IPAY88"
    };

    if (!bankMap[bankCode]) {
        log("❌ Invalid bank code: " + bankCode);
        return;
    }

    id('btn_select_beneficiary_bank').findOne(60000).click();
    log("✅ Clicked select beneficiary bank button");

    let targetBank = bankMap[bankCode];
    log("🔍 Selecting bank: " + targetBank);

    if (!findAndClickBank(targetBank)) {
        log("❌ Bank not found: " + targetBank);
    }
}

function findAndClickBank(bankName) {
    let bankItem;
    log("🔍 Searching bank");
    // First try with 6 scrolls
    for (let i = 0; i < 7; i++) { // 2
        bankItem = id("tv_name").text(bankName).findOne(1000);
        if (bankItem) {
            bankItem.parent().click();
            log("✅ Selected " + bankName);
            return true;
        }
        scroll(0.8, 0.25);
        // scrollDown(0.95, 0.05);
        sleep(200);
    }

    // If not found, try clicking "Load More"
    let loadMoreBtn = id("cstly_load_more").findOne(60000);
    if (loadMoreBtn) {
        click(360, 1457);
        log("✅ Clicked More Result button");

        // After load more, scroll 2 more times
        for (let j = 0; j < 3; j++) { // 2
            bankItem = id("tv_name").text(bankName).findOne(1000);
            if (bankItem) {
                bankItem.parent().click();
                log("✅ Selected " + bankName);
                return true;
            }
            scroll(0.8, 0.25);
            // scrollDown(0.95, 0.05);
            sleep(200);
        }
    } else {
        log("❌ Load More button not found");
    }

    return false; // Bank not found after all attempts
}

function resident_option() {
    id('rb_resident_yes').findOne(60000).click();
    log("✅ Resident option selected");
}

function additional_beneficiary_details(recRef) {
    scroll();
    log("✅ Scrolled down");

    let recipientReference = id("fit_recipient_ref").findOne(60000);
    let recRefFeild = recipientReference.findOne(className("android.widget.EditText"));
    safeInput(recRefFeild, recRef);
    log("✅ Filled recipient reference");
}

function click_order_details() {
    id('rb_not_related').findOne(60000).click();
    log("✅ Clicked order details");
}

function click_ok() {
    let okBtn = id('btn_ok').findOne(60000);
    if (okBtn) {
        okBtn.click();
        log("✅ Clicked OK button on finish adding beneficiary");
        sleep(1000);
        // 检查 check_bene 需要的元素是否出现
        let msgView = id("tv_message").findOne(3000);
        if (!msgView) {
            log("🔄 Retrying OK button click (element not found)");
            okBtn = id('btn_ok').findOne(5000);
            if (okBtn) {
                okBtn.click();
                log("✅ Clicked OK button again");
            } else {
                log("❌ OK button not found for retry");
            }
        }
    } else {
        log("❌ OK button not found");
    }
}

function check_bene(expectedName, similarityThreshold, tran_id, data, failedTranIds, balance, start_time) {
    let msgView = id("tv_message").findOne(60000);
    let msgText = msgView.text();

    const errorKeywords = [
        "Your transaction is not successful",
        "U280: CertPathNotConfig.",
        "U272: MandateEndDtLessEqualsThanCurrentDt.",
        "U282: CryptoRuleNotFound.",
        "common.text.rpp.host.err.U854.long"
    ];

    if (errorKeywords.some(err => msgText.indexOf(err) !== -1)) {
        log(JSON.stringify({
            status: 4,
            tran_id: tran_id,
            message: "Invalid bank or account number.",
            errorMessage: "Invalid bank or account number."
        }));

        send_single_callback("4", tran_id, "Invalid bank or account number.", "Invalid bank or account number.");

        // 记录已上传 status 的 tran_id
        if (!failedTranIds.includes(String(tran_id))) {
            failedTranIds.push(String(tran_id));
        }
        handle_failed_beneficiary(tran_id, data, failedTranIds, balance, start_time);
        return false;
    } else if (match = msgText.match(/Account No\. is registered as\s+([\s\S]+?)\.\s*Click confirm to proceed payment/)) {
        let actualName = match[1].trim();
        log("👤 Registered name: " + actualName);
        log("👤 Fill in name  : " + expectedName);

        let similarity = stringSimilarity(expectedName, actualName);

        if (similarity >= similarityThreshold) {
            log("✅ - The names are at least " + (similarityThreshold * 100) + "% similar.");
            return true;
        } else {
            // 记录到日志
            let errorMsg = "Expected: " + expectedName + ", Actual: " + actualName + ", Similarity Threshold: " + (similarityThreshold * 100) + "%";
            log(JSON.stringify({
                status: 4,
                tran_id: tran_id,
                message: "Name similarity below threshold. The similarity threshold is " + (similarityThreshold * 100) + "%.",
                errorMessage: errorMsg
            }));
            
            // 发送callback
            send_single_callback("4", tran_id, "Name not match", errorMsg);
            
            // 记录已上传 status 的 tran_id
            if (!failedTranIds.includes(String(tran_id))) {
                failedTranIds.push(String(tran_id));
            }
            name_not_match();
            return false;
        }
    } else {
        return true;
    }

}

function name_not_match() {
    let cancelBtn = id('btn_cancel').findOne(60000);
    if (cancelBtn) cancelBtn.click();
    log("✅ Clicked Cancel button after name mismatch");

    let backBtn = id('btn_title_left').findOne(60000);
    if (backBtn) backBtn.click();
    log("✅ Clicked Back button after name mismatch");

    log("❌ Fail to add beneficiary");
}

function handle_failed_beneficiary(tran_id, data, failedTranIds, balance, start_time) {
    try {
        let okBtn = id('btn_ok').findOne(60000);
        if (okBtn) okBtn.click();
        log("✅ Clicked OK button on error dialog");

        let backBtn = id('btn_title_left').findOne(60000);
        if (backBtn) backBtn.click();
        log("✅ Clicked Back button");

        log("❌ Fail to add beneficiary");

    } catch (e) {
        log("❌ Error in handle_failed_beneficiary: " + e);
        
        // 计算运行时间
        let runtime = (new Date() - start_time) / 1000;
        log("-".repeat(22) + ` Total runtime: ${runtime} seconds ` + "-".repeat(21));
        
        // 上传日志
        upload_transfer_log(data.beneficiaries, failedTranIds, "7", "Something went wrong, will try agian", "Step fail at handle_failed_beneficiary", balance);
        
        // 更新后端余额
        if (typeof data.group_id !== "undefined" && balance !== null && balance !== "null") {
            let successAmount = calc_success_amount(data.beneficiaries, failedTranIds);
            update_backend_group_and_balance(data.group_id, successAmount, balance);
        }
        
        // 发送callback
        if (tran_id) {
            send_single_callback("7", tran_id, "Something went wrong, will try agian", "Step fail at handle_failed_beneficiary");
        }
        
        // 关闭应用并完成流程
        close_app();
        return complete_process();
    }
}

function save_screenshot(tran_id) {
    let screenshotPath = "/sdcard/Pictures/affinmax_confirm_custname_" + tran_id + ".png";
    captureScreen(screenshotPath);
    log("📸 Screenshot saved: " + screenshotPath);
    
    // 直接上传截图到 S3
    let s3FileName = "affinmax_confirm_custname_" + tran_id + ".png";
    uploadToS3(screenshotPath, s3FileName, tran_id);
}

function click_confirm() {
    id('btn_confirm').findOne(60000).click();
    log("✅ Clicked Confirm button");
}

function preview_button() {
    log("-".repeat(18) + (" Finished filling beneficiary details ") + "-".repeat(18));
    id('btn_preview').findOne(60000).click();
    log("✅ Clicked Preview button");
}

function confirm_transfer() {
    // 使用循环重试机制，类似 choose_open_bene
    let startTime = new Date().getTime();
    let timeout = 60000; // 60秒超时
    let errorMsg = null;
    
    do {
        // 勾选 checkbox
        id('checkbox').findOne(60000).click();
        log("✅ Clicked t&c checkbox");

        id('btn_submit').findOne(60000).click();
        log("✅ Clicked Submit button");
        
        // 检查是否有 Terms and Conditions 错误提示
        sleep(1000);
        errorMsg = id('tv_message').findOne(3000);
        
        if (errorMsg && errorMsg.text().indexOf("Please accept Terms and Conditions before proceeding") !== -1) {
            log("⚠️ Terms and Conditions not accepted, retrying...");
            
            // 点击 OK 按钮关闭错误提示
            let okBtn = id('btn_ok').findOne(5000);
            if (okBtn) {
                okBtn.click();
                log("✅ Clicked OK button on Terms and Conditions error");
                sleep(500);
            } else {
                log("❌ OK button not found on error dialog");
                throw new Error("OK button not found on Terms and Conditions error dialog");
            }
        } else {
            // 没有错误消息，说明提交成功
            log("✅ Terms and Conditions accepted successfully");
            break;
        }
        
        // 检查是否超时
        if (new Date().getTime() - startTime > timeout) {
            log("❌ Timeout: Failed to accept Terms and Conditions after 60 seconds");
            throw new Error("Timeout: Failed to accept Terms and Conditions after 60 seconds");
        }
        
    } while (errorMsg && errorMsg.text().indexOf("Please accept Terms and Conditions before proceeding") !== -1);
    
    log("✅ Confirmed transfer with Terms and Conditions");
}

function approve() {
    id('btn_approve').findOne(60000).click();
    log("✅ Clicked Approve button");
}

function transfer_password(tranPass) {
    log("👉 Filling transaction password...");
    let passField = id("edit_security").findOne(60000);
    safeInput(passField, tranPass);
    log("✅ Filled transaction password");

    id('btn_ok').findOne(60000).click();
    log("✅ Clicked OK button");
}

function success_transfer() {
    if (id('tv_status_title').text("SUCCESSFUL").findOne(60000)) {
        id('btn_done').findOne(60000).click();
        log("✅ Transfer successful, clicked Done button");
    }
}

function download_transfer_slip() {
    sleep(10000);
    id('tv_download').findOne(60000).click();
    log("✅ Clicked Download button");
}

// function click_pdf_ref_no(bene_name) {
//     let name = id("tv_title").text(bene_name).findOne(10000);
//     if (name) {
//         let parent = name.parent();
//         if (parent && parent.className() === "android.view.ViewGroup") {
//             parent.click();
//             log(`✅ Clicked ViewGroup for bene_name '${bene_name}'`);
//             sleep(2000); // 等待页面响应（打开或关闭）
//             return true;
//         } else {
//             log(`❌ ViewGroup parent not found for bene_name '${bene_name}'`);
//             return false;
//         }
//     } else {
//         log(`❌ Beneficiary name '${bene_name}' not found in list`);
//         return false;
//     }
// }

function click_pdf_ref_no_by_index(index) {
    // 获取所有受益人名称元素
    let nameElements = id("tv_title").find(10000);

    if (!nameElements || nameElements.length === 0) {
        log(`❌ No beneficiary names found in list`);
        return false;
    }

    // 直接使用传入的index（从1开始，跳过index 0）
    if (index < 0 || index >= nameElements.length) {
        log(`❌ Index ${index} out of bounds, only ${nameElements.length} elements found`);
        return false;
    }

    // 点击指定索引的受益人
    let targetName = nameElements[index];
    let parent = targetName.parent();

    if (parent && parent.className() === "android.view.ViewGroup") {
        parent.click();
        log(`✅ Clicked beneficiary at index ${index} (name: '${targetName.text()}')`);
        sleep(2000); // 等待页面响应（打开或关闭）
        return true;
    } else {
        log(`❌ ViewGroup parent not found for beneficiary at index ${index}`);
        return false;
    }
}

function get_pdf_ref_no(tran_id) {
    // 获取 reference no
    let refView = id("tv_reference_no").findOne(60000);
    if (!refView) {
        log(`❌ Reference number not found for tran_id: ${tran_id}`);
        return null;
    }
    let referenceNo = refView.text();
    // 获取当前日期
    let now = new Date();
    // 格式化日期为 DD MMM YYYY
    let day = String(now.getDate()).padStart(2, '0');
    let monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    let month = monthNames[now.getMonth()];
    let year = now.getFullYear();
    let dateStr = `${day} ${month} ${year}`;
    // 拼接文件名
    let pdfName = `AFFINMAX_${referenceNo}_${dateStr}.pdf`;
    log(`📄 PDF name: ${pdfName}`);
    log(`📄 Transaction ID: ${tran_id}`);
    
    // 查找并上传PDF文件到S3
    let pdfPath = `/sdcard/Download/${pdfName}`;
    
    // 检查文件是否存在
    if (files.exists(pdfPath)) {
        // 上传PDF到S3
        uploadToS3(pdfPath, pdfName, tran_id);
        return pdfName;
    } else {
        // 尝试常见的下载目录路径
        let altPaths = [
            `/sdcard/downloads/${pdfName}`,
            `/sdcard/Downloads/${pdfName}`,
            `/storage/emulated/0/Download/${pdfName}`,
            `/storage/emulated/0/downloads/${pdfName}`,
            `/storage/emulated/0/Downloads/${pdfName}`
        ];
        
        let found = false;
        for (let altPath of altPaths) {
            log(`🔍 Trying alternative path: ${altPath}`);
            if (files.exists(altPath)) {
                log(`✅ PDF file found at: ${altPath}`);
                uploadToS3(altPath, pdfName, tran_id);
                found = true;
                break;
            }
        }
        
        if (!found) {
            log(`❌ PDF file not found in any location: ${pdfName}`);
        }
        
        return found ? pdfName : null;
    }
}

function ok_button_after_transfer() {
    log("-".repeat(74));
    id('btn_ok').findOne(60000).click();
    log("✅ Clicked OK button to finish transfer");
}

function nav_accounts() {
    id('accounts').findOne(60000).click();
    log("✅ Navigated to Accounts tab");
}

function grab_balance() {
    sleep(500);
    let accountTypeTitle = id('tv_account_type_title').findOne(60000);
    if (!accountTypeTitle) return null;

    let balanceTextView = id('tv_total_available_balance').findOne(60000);
    if (balanceTextView) {
        let balanceText = balanceTextView.text();
        let balanceValue = toNumber(balanceText);
        return balanceValue;
    }
    return null;
}

function report_transfer_result(data, failedTranIds, error_status, message, errorMessage, start_time) {
    let runtime = (new Date() - start_time) / 1000;
    let balance = grab_balance();
    log("-".repeat(22) + ` Total runtime: ${runtime} seconds ` + "-".repeat(21));
    upload_transfer_log(data.beneficiaries, failedTranIds, error_status, message, errorMessage, null); // 不传balance

    let successAmount = calc_success_amount(data.beneficiaries, failedTranIds);
    update_backend_group_and_balance(data.group_id, successAmount);

    // 最后单独写一条剩余余额日志
    http.postJson("http://" + SERVER_IP + ":" + SERVER_PORT + "/backend/log/", {
        device: PHONE_NUMBER,
        message: JSON.stringify({
            remaining_balance: balance
        })
    });

    log("Total success transfer amount: " + successAmount);
    
    // 🔔 发送成功的callback - 为每个成功的交易发送
    if (data.beneficiaries && Array.isArray(data.beneficiaries)) {
        data.beneficiaries.forEach(function(bene) {
            if (!failedTranIds.includes(String(bene.tran_id))) {
                send_single_callback("2", bene.tran_id, "Transaction success", "Transaction success");
            }
        });
    }
    
    return { runtime, balance, successAmount };
}





// ------ Automation functions end here ------

function run_transfer_process(data) { // error_status, message, errorMessage not yet confirmed and correct

    let start_time = new Date();

    log('-'.repeat(74));
    log(`Make Transaction Script run started at ${start_time}`);
    log('-'.repeat(74));

    set_is_busy(1);

    try {
        transfer_info(data.beneficiaries);
        open_app();
    } catch (e) {
        error_status = "7";
        message = "Something went wrong, will try agian";
        errorMessage = "Step fail at open_app";
        printError();
        return;
    }

    try {
        fill_corporate_and_user_id(data.corp_id, data.user_id);
    } catch (e) {
        error_status = "7";
        message = "Something went wrong, will try agian";
        errorMessage = "Step fail at fill_corporate_and_user_id";
        printError();
        return;
    }

    try {
        fill_password(data.password);
    } catch (e) {
        error_status = "7";
        message = "Something went wrong, will try agian";
        errorMessage = "Step fail at fill_password";
        printError();
        return;
    }

    try {
        show_balance();
    } catch (e) {
        error_status = "7";
        message = "Something went wrong, will try agian";
        errorMessage = "Step fail at show_balance";
        printError();
        return;
    }

    try {
        let balanceCheckResult = check_balance(data.beneficiaries);
        if (balanceCheckResult === null) {
            // 余额不足 - 获取当前余额和所需金额
            let currentBalance = "N/A";
            let totalAmount = 0;
            
            // 计算总金额
            data.beneficiaries.forEach(function(bene) {
                totalAmount += toNumber(bene.amount);
            });
            
            // 尝试获取当前余额
            let balanceTextView = id("tv_total_available_balance").findOne(3000);
            if (balanceTextView) {
                currentBalance = balanceTextView.text();
            }
            
            // 🔔 余额不足时，为每个交易发送callback
            data.beneficiaries.forEach(function(bene) {
                http.postJson("http://" + SERVER_IP + ":9001/backend/log/", {
                    device: PHONE_NUMBER,
                    message: JSON.stringify({
                        status: "3",
                        tran_id: String(bene.tran_id),
                        message: "Insufficient balance",
                        errorMessage: "Balance less than transfer amount",
                        current_balance: currentBalance,
                        required_amount: totalAmount.toFixed(2),
                        balance: null
                    })
                });
            });

            // 🔔 余额不足时，为每个交易发送callback
            data.beneficiaries.forEach(function(bene) {
                send_single_callback("3", bene.tran_id, "Insufficient balance", "Insufficient balance");
            });
            
            close_app();
            return complete_process();
        }
        balance = balanceCheckResult;

        // ...existing code...
    } catch (e) {
        error_status = "7";
        message = "Something went wrong, will try agian";
        errorMessage = "Step fail at check_balance";
        printError();
        return;
    }

    try {
        click_duit_now();
    } catch (e) {
        error_status = "7";
        message = "Something went wrong, will try agian";
        errorMessage = "Step fail at click_duit_now";
        return printError();
    }

    try {
        transaction_details();
    } catch (e) {
        error_status = "7";
        message = "Something went wrong, will try agian";
        errorMessage = "Step fail at transaction_details";
        return printError();
    }

    for (let i = 0; i < data.beneficiaries.length; i++) { // If one of the beneficiaries fail, stop the whole process or pass to next beneficiary?
        let bene = data.beneficiaries[i];
        log("-".repeat(22) + " Adding beneficiary details " + (i + 1) + " " + "-".repeat(22));

        try {
            add_beneficiary_button();
        } catch (e) {
            error_status = "7";
            message = "Something went wrong, will try agian";
            errorMessage = "Step fail at add_beneficiary_button";
            return printError();
        }

        try {
            choose_open_bene();
        } catch (e) {
            error_status = "7";
            message = "Something went wrong, will try agian";
            errorMessage = "Step fail at choose_open_bene";
            return printError();
        }

        try {
            beneficiary_details(bene.amount, bene.bene_acc_no, bene.bene_name);
        } catch (e) {
            error_status = "7";
            message = "Something went wrong, will try agian";
            errorMessage = "Step fail at beneficiary_details";
            return printError();
        }

        try {
            choose_bank(bene.bank_code);
        } catch (e) {
            error_status = "7";
            message = "Something went wrong, will try agian";
            errorMessage = "Step fail at choose_bank";
            return printError();
        }

        try {
            resident_option();
        } catch (e) {
            error_status = "7";
            message = "Something went wrong, will try agian";
            errorMessage = "Step fail at resident_option";
            return printError();
        }

        try {
            additional_beneficiary_details(bene.recRef);
        } catch (e) {
            error_status = "7";
            message = "Something went wrong, will try agian";
            errorMessage = "Step fail at additional_beneficiary_details";
            return printError();
        }

        try {
            click_order_details();
        } catch (e) {
            error_status = "7";
            message = "Something went wrong, will try agian";
            errorMessage = "Step fail at order_details";
            return printError();
        }

        try {
            click_ok();
        } catch (e) {
            error_status = "7";
            message = "Something went wrong, will try agian";
            errorMessage = "Step fail at click_ok";
            return printError();
        }

        try {
            // 使用每个 bene 的 similarity_threshold 字段
            let similarityThreshold = (typeof bene.similarity_threshold !== 'undefined') ? bene.similarity_threshold : 0.7;
            if (!check_bene(bene.bene_name, similarityThreshold, bene.tran_id, data, failedTranIds, balance, start_time)) {
                // check_bene 失败时已 log 并记录 tran_id
                continue;
            }
        } catch (e) {
            error_status = "7";
            message = "Something went wrong, will try agian";
            errorMessage = "Step fail at check_bene";
            return printError();
        }

        try {
            save_screenshot(bene.tran_id);
        } catch (e) {
            error_status = "7";
            message = "Something went wrong, will try agian";
            errorMessage = "Step fail at save_screenshot";
            return printError();
        }

        try {
            click_confirm();
        } catch (e) {
            error_status = "7";
            message = "Something went wrong, will try agian";
            errorMessage = "Step fail at click_confirm";
            return printError();
        }

        log("✅ Finished adding beneficiary details " + (i + 1));
    }

    // 检查是否所有交易都已失败，如果是则结束流程
    if (failedTranIds.length === data.beneficiaries.length) {
        error_status = "4";
        message = "All transactions failed";
        errorMessage = "All transactions failed during beneficiary validation";
        return printError();
    }

    // 检查是否有成功的交易（至少有一个不在failedTranIds中）
    let hasSuccessfulTrans = data.beneficiaries.some(function(bene) {
        return !failedTranIds.includes(String(bene.tran_id));
    });

    if (!hasSuccessfulTrans) {
        error_status = "4";
        message = "No successful transactions";
        errorMessage = "No valid transactions remaining to process";
        return printError();
    }

    try {
        preview_button();
    } catch (e) {
        error_status = "7";
        message = "Something went wrong, will try agian";
        errorMessage = "Step fail at preview_button";
        return printError();
    }

    try {
        confirm_transfer();
    } catch (e) {
        error_status = "7";
        message = "Something went wrong, will try agian";
        errorMessage = "Step fail at confirm_transfer";
        return printError();
    }

    try {
        approve();
    } catch (e) {
        error_status = "7";
        message = "Something went wrong, will try agian";
        errorMessage = "Step fail at approve";
        return printError();
    }

    try {
        transfer_password(data.tranPass);
    } catch (e) {
        error_status = "6";
        message = "Something went wrong, will try agian";
        errorMessage = "Step fail at transfer_password";
        return printError();
    }

    try {
        success_transfer();
    } catch (e) {
        error_status = "6";
        message = "Something went wrong, will try agian";
        errorMessage = "Step fail at success_transfer";
        return printError();
    }

    try {
        download_transfer_slip();
    } catch (e) {
        error_status = "5";
        message = "Transaction Success";
        errorMessage = "Step fail at download_transfer_slip";
        return printError();
    }

    // 为每个受益人点击并获取PDF收据
    try {
        // 只处理成功的受益人（不在 failedTranIds 中）
        let successfulBeneficiaries = [];
        for (let i = 0; i < data.beneficiaries.length; i++) {
            let bene = data.beneficiaries[i];
            if (!failedTranIds.includes(String(bene.tran_id))) {
                successfulBeneficiaries.push({
                    originalIndex: i,
                    listIndex: successfulBeneficiaries.length,  // 在列表中的实际位置
                    bene: bene
                });
            }
        }
        
        log(`📋 Processing ${successfulBeneficiaries.length} successful transactions for PDF download`);
        
        for (let i = 1; i <= successfulBeneficiaries.length; i++) {
            let item = successfulBeneficiaries[i - 1];
            let bene = item.bene;
            log(`-`.repeat(22) + ` Processing PDF for beneficiary ${item.originalIndex + 1} (list position ${i}) ` + `-`.repeat(22));

            // 使用1-based索引点击受益人打开详情页
            if (!click_pdf_ref_no_by_index(i)) {
                log(`❌ Failed to open beneficiary at index ${i}, skipping PDF download`);
                continue;
            }

            // 获取并上传PDF
            get_pdf_ref_no(bene.tran_id);

            // 点击关闭当前详情页（除了最后一个，最后一个不需要关闭）
            if (i < successfulBeneficiaries.length) {
                if (!click_pdf_ref_no_by_index(i)) {
                    log(`❌ Failed to close beneficiary at index ${i} details`);
                }
            }
        }
    } catch (e) {
        error_status = "5";
        message = "Transaction Success";
        errorMessage = "Step fail at get PDF receipts: " + e.toString();
        printError();
        return;
    }

    try {
        ok_button_after_transfer();
    } catch (e) {
        error_status = "5";
        message = "Something went wrong, will try agian";
        errorMessage = "Step fail at ok_button_after_transfer";
        return printError();
    }

    try {
        nav_accounts();
    } catch (e) {
        error_status = "5";
        message = "Something went wrong, will try agian";
        errorMessage = "Step fail at nav_accounts";
        return printError();
    }

    try {
        report_transfer_result(data, failedTranIds, error_status, message, errorMessage, start_time);
    } catch (e) {
        error_status = "7";
        message = "Something went wrong, will try agian";
        errorMessage = "Step fail at report_transfer_result";
        return printError();
    }

    try {
        close_app();
    } catch (e) {
        error_status = "7";
        message = "Something went wrong, will try agian";
        errorMessage = "Step fail at close_app";
        return printError();
    }

    try {
        complete_process();
    } catch (e) {
        error_status = "7";
        message = "Something went wrong, will try agian";
        errorMessage = "Step fail at complete_process";
        return printError();
    }

    

    function printError() {
        let runtime = (new Date() - start_time) / 1000;
        log("-".repeat(22) + ` Total runtime: ${runtime} seconds ` + "-".repeat(21));

        // 统一用工具函数上传日志
        upload_transfer_log(data.beneficiaries, failedTranIds, error_status, message, errorMessage, balance);

        // 失败时立即更新 current_balance（只用 check_balance 的结果，不用 grab_balance）
        if (typeof data.group_id !== "undefined" && balance !== null && balance !== "null") {
            update_backend_group_and_balance(data.group_id, null, balance);
        }

        // 🔔 发送失败的callback
        if (data.beneficiaries && Array.isArray(data.beneficiaries)) {
            data.beneficiaries.forEach(function(bene) {
                // 只为还没发送过callback的交易发送
                // 如果tran_id不在failedTranIds里（还没发过callback），则发送
                if (!failedTranIds.includes(String(bene.tran_id))) {
                    send_single_callback(error_status, bene.tran_id, message, errorMessage);
                }
            });
        }

        close_app();
        return complete_process();

    }
}


// 兼容直接 require/execScript 调用
if (typeof run_transfer_process === "function" && typeof data !== "undefined") {
    run_transfer_process(data);
}

module.exports = {
    run_transfer_process
};