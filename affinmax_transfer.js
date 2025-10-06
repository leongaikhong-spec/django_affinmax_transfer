"auto";
"ui";

const SERVER_IP = "192.168.100.162";  // Device IP Address
const PHONE_NUMBER = "0123456789";    // Current device phone number

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

// ...existing code...

let error_status = "2";
let message = "Transaction Success";
let errorMessage = "null";
let balance = "null";

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

function clickButton(desc, selector, timeout = 5000) {
    let btn = (typeof selector === "string")
        ? id(selector).findOne(timeout)
        : selector.findOne(timeout);

    if (btn) {
        btn.click();
        log(`✅ Clicked ${desc}`);
        return true;
    } else {
        log(`❌ ${desc} not found`);
        close_app();
    }
}

function scrollDown(startRatio = 0.8, endRatio = 0.5, duration = 500) {
    swipe(
        device.width / 2,
        device.height * startRatio,
        device.width / 2,
        device.height * endRatio,
        duration
    );
}


// function close_app() {
//     recents();  
//     sleep(1000);
//     let clearAllBtn = id("clear_all").findOne(5000);
//     if (clearAllBtn) {
//         clearAllBtn.click();
//         log("✅ Closed affinmax app")
//     } else {
//         log("❌ Not found Clear All button");
//     }

//     log("-".repeat(30));
//     return false; // Return false to indicate app closure
// }

function close_app() { // Need to advance this function to close the app properly
    for (let i = 0; i < 5; i++) { 
        back();
        sleep(400); 
    } 
    
    app.startActivity({ 
        action: "android.intent.action.MAIN", 
        category: "android.intent.category.HOME", 
        flags: ["activity_new_task"] 
    }); 
    
    id('btn_ok').findOne(5000).click(); 
    log("-".repeat(74));
    log("✅ Closed affinmax app") 
    log("-".repeat(74));
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
    sleep(3000);
}

// function close_notify() {
//     let fallbackBtn = id("ab9d4931-56e0-419b-8e44-2f3a8cda6826").findOnce();
//     if (fallbackBtn) {
//         fallbackBtn.click();
//         log("✅ Clicked close notify button.");
//     }
// }

function fill_corporate_and_user_id(corp_id, user_id) {
    let corpIdLayout = id("fit_corp_id").findOne(10000);
    let corpIdField = corpIdLayout.findOne(className("android.widget.EditText"));
    safeInput(corpIdField, corp_id);
    log("✅ Filled corporate ID");

    let userIdLayout = id("fit_user_id").findOne(10000);
    let userIdField = userIdLayout.findOne(className("android.widget.EditText"));
    safeInput(userIdField, user_id);
    log("✅ Filled user ID");

    id("btn_next").findOne(10000).click();
    log("✅ Clicked next button");
}

function fill_password(password) {
    log("👉 Filling login password...");
    let pwdLayout = id("fit_password").findOne(10000);
    let pwdField = pwdLayout.findOne(className("android.widget.EditText"));
    safeInput(pwdField, password);
    log("✅ Password filled");

    id("btn_login").findOne(10000).click();
    log("✅ Clicked login button");
}

function show_balance() {
    sleep(8000);
    let balanceBtn = id("ib_masking_balance").findOne(10000);
    if (balanceBtn) {
        //click(465, 410); 
        balanceBtn.click();
        log("✅ Clicked Show Balance button");
    }
}

function check_balance(beneficiaries) {
    sleep(1000);
    let balanceTextView = id("tv_total_available_balance").findOne(10000);
    if (!balanceTextView) {
        log("❌ Could not find balance element");
        return null;
    }

    let balanceText = balanceTextView.text();
    let balanceValue = toNumber(balanceText);

    if (isNaN(balanceValue)) {
        log("❌ Unable to retrieve balance (NaN)");
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
        return null; // ❌ 余额不足，返回 null
    } else {
        log("✅ Balance is sufficient, continue transfer");
        return balanceValue; // ✅ 返回数字余额
    }
}

function click_duit_now() {
    let duitNowBtn = id("rl_container").findOne(10000);
    if (!duitNowBtn) {

    }
    duitNowBtn.click();
    log("✅ Clicked DuitNow button");
    sleep(500);

    if (id("tv_label").text("DuitNow Transfer").findOne(10000)) {
        click(197, 603);
        log("✅ Clicked DuitNow Transfer button");
        sleep(500);
    } else {

    }

    if (id("tv_label").text("Pay to Account").findOne(10000)) {
        click(197, 603);
        log("✅ Clicked Pay to Account button");
        sleep(500);
    } else {

    }

    if (id("tv_label").text("New Transfer").findOne(10000)) {
        click(197, 603);
        log("✅ Clicked New Transfer button");
        sleep(500);
    } else {

    }

    if (!id("text_input_end_icon").findOne(10000)) {

    }
    log("✅ Bank selection button found");
}

function transaction_details() {
    id('text_input_end_icon').findOne(10000).click();
    log("✅ Clicked dropdown button");

    sleep(1000);
    click(360, 395);
    log("✅ Chosen debit from account no./currency");
}

function add_beneficiary_button() {
    id('btn_add_bene').findOne(10000).click();
    log("✅ Clicked Add Beneficiary button");
}

function beneficiary_details(amount, accNo, name) {
    let title = id("tv_bene_details").findOne(10000);
    if (!title || title.text() !== "Beneficiary") {
        log("❌ Not on Beneficiary page, cannot proceed.");

    }

    id('rb_open_bene').click();
    log("✅ Chosen beneficiary type");

    id('text_input_end_icon').findOne(10000).click();
    log("✅ Clicked dropdown button for transaction type");

    sleep(1000);        
    click(200, 466);
    log("✅ Chosen transaction type");

    let transAmount = id("fic_transaction_amount").findOne(10000);
    let amountField = transAmount.findOne(className("android.widget.EditText"));
    safeInput(amountField, amount);
    log("✅ Filled transaction amount");

    let beneAcc = id("fit_bene_acc_no").findOne(10000);
    let accNoField = beneAcc.findOne(className("android.widget.EditText"));
    safeInput(accNoField, accNo);
    log("✅ Filled beneficiary account no");

    let beneName = id("fit_bene_name").findOne(10000);
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

    id('btn_select_beneficiary_bank').findOne(10000).click();
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
    // First try with 5 scrolls
    for (let i = 0; i < 5; i++) { // 2
        bankItem = id("tv_name").text(bankName).findOne(1000);
        if (bankItem) {
            bankItem.parent().click();
            log("✅ Selected " + bankName);
            return true;
        }
        scrollDown(0.8, 0.25);
        // scrollDown(0.95, 0.05);
        sleep(200);
    }

    // If not found, try clicking "Load More"
    let loadMoreBtn = id("cstly_load_more").findOne(10000);
    if (loadMoreBtn) {
        click(360, 1457);
        log("✅ Clicked More Result button");

        // After load more, scroll 2 more times
        for (let j = 0; j < 2; j++) { // 2
            bankItem = id("tv_name").text(bankName).findOne(1000);
            if (bankItem) {
                bankItem.parent().click();
                log("✅ Selected " + bankName);
                return true;
            }
            scrollDown(0.8, 0.25);
            // scrollDown(0.95, 0.05);
            sleep(200);
        }
    } else {
        log("❌ Load More button not found");
    }

    return false; // Bank not found after all attempts
}

function resident_option() {
    id('rb_resident_yes').findOne(10000).click();
    log("✅ Resident option selected");
}

function additional_beneficiary_details(recRef) {
    scrollDown();
    log("✅ Scrolled down");

    let recipientReference = id("fit_recipient_ref").findOne(10000);
    let recRefFeild = recipientReference.findOne(className("android.widget.EditText"));
    safeInput(recRefFeild, recRef);
    log("✅ Filled recipient reference");
}

function click_order_details() {
    id('rb_not_related').findOne(10000).click();
    log("✅ Clicked order details");
}

function click_ok() {
    id('btn_ok').findOne(10000).click();
    log("✅ Clicked OK button on finish adding beneficiary");
}

function check_bene(expectedName, similarityThreshold, tran_id) {
    let msgView = id("tv_message").findOne(10000);
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
        handle_failed_beneficiary();
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
            log(JSON.stringify({
                status: 4,
                tran_id: tran_id,
                message: "Name similarity below threshold.",
                errorMessage: `Expected: ${expectedName}, Actual: ${actualName}`
            }));
            name_not_match();            
            return false;
        }
    } else {
        return true;
    }

}

function name_not_match() {
    let cancelBtn = id('btn_cancel').findOne(10000);
    if (cancelBtn) cancelBtn.click();
    log("✅ Clicked Cancel button after name mismatch");

    let backBtn = id('btn_title_left').findOne(10000);
    if (backBtn) backBtn.click();
    log("✅ Clicked Back button after name mismatch");

    log("❌ Fail to add beneficiary");
}

function handle_failed_beneficiary() {
    try {
        let okBtn = id('btn_ok').findOne(10000);
        if (okBtn) okBtn.click();
        log("✅ Clicked OK button on error dialog");

        let backBtn = id('btn_title_left').findOne(10000);
        if (backBtn) backBtn.click();
        log("✅ Clicked Back button");

        log("❌ Fail to add beneficiary");


    } catch (e) {
        error_status = "3";
        message = "Something went wrong";
        errorMessage = "Automation fail at handle_failed_beneficiary";
        return printError();
    }
}

function save_screenshot(tran_id) {
    let screenshotPath = "/sdcard/Pictures/affinmax_confirm_custname_" + tran_id + ".png";
    captureScreen(screenshotPath);
    log("📸 Screenshot saved: " + screenshotPath);
}

function click_confirm() {
    id('btn_confirm').findOne(10000).click();
    log("✅ Clicked Confirm button");
}

function preview_button() {
    log("-".repeat(18) + (" Finished filling beneficiary details ") + "-".repeat(18));
    id('btn_preview').findOne(10000).click();
    log("✅ Clicked Preview button");
}

function confirm_transfer() {
    id('checkbox').findOne(10000).click();
    log("✅ Clicked t&c checkbox");

    id('btn_submit').findOne(10000).click();
    log("✅ Clicked Submit button");
}

function approve() {
    id('btn_approve').findOne(10000).click();
    log("✅ Clicked Approve button");
}

function transfer_password(tranPass) {
    log("👉 Filling transaction password...");
    let passField = id("edit_security").findOne(10000);
    safeInput(passField, tranPass);
    log("✅ Filled transaction amount");

    id('btn_ok').findOne(10000).click();
    log("✅ Clicked OK button");
}

function success_transfer() {
    if (id('tv_status_title').text("SUCCESSFUL").findOne(10000)) {
        id('btn_done').findOne(10000).click();
        log("✅ Transfer successful, clicked Done button");
    }
}

function download_transfer_slip() {
    sleep(2000);
    id('tv_download').findOne(10000).click();
    log("✅ Clicked Download button");

    id('btn_ok').findOne(10000).click();
    log("✅ Clicked OK button");
}

function nav_accounts() {
    id('accounts').findOne(10000).click();
    log("✅ Navigated to Accounts tab");
}

function grab_balance() {
    sleep(500);
    let accountTypeTitle = id('tv_account_type_title').findOne(30000);
    if (!accountTypeTitle) return null;

    let balanceTextView = id('tv_total_available_balance').findOne(10000);
    if (balanceTextView) {
        let balanceText = balanceTextView.text();
        let balanceValue = toNumber(balanceText);
        return balanceValue;
    }
    return null;
}





// ------ Automation functions end here ------

function run_transfer_process(data) { // error_status, message, errorMessage not yet confirmed and correct
    
    let start_time = new Date();

    log('-'.repeat(74));
    log(`Script run started at ${start_time}`);
    log('-'.repeat(74));

    try {
        transfer_info(data.beneficiaries);
        open_app();
    } catch (e) {
        error_status = "3";
        message = "Something went wrong";
        errorMessage = "Automation fail at open_app";
        printError();
        return;
    }

    try {
        fill_corporate_and_user_id(data.corp_id, data.user_id);
    } catch (e) {
        error_status = "3";
        message = "Something went wrong";
        errorMessage = "Automation fail at fill_corporate_and_user_id";
        printError();
        return;
    }

    try {
        fill_password(data.password);
    } catch (e) {
        error_status = "3";
        message = "Something went wrong";
        errorMessage = "Automation fail at fill_password";
        printError();
        return;
    }

    try {
        show_balance();
    } catch (e) {
        error_status = "3";
        message = "Something went wrong";
        errorMessage = "Automation fail at show_balance";
        printError();
        return;
    }

    try {
        let bal = check_balance(data.beneficiaries);
        if (bal === null) {
            error_status = "4";
            message = "Insufficient balance";
            errorMessage = "Balance less than transfer amount";
            printError();
            return;
        }
        balance = bal;
    } catch (e) {
        error_status = "3";
        message = "Something went wrong";
        errorMessage = "Automation fail at check_balance";
        printError();
        return;
    }

    try {
        click_duit_now();
    } catch (e) {
        error_status = "3";
        message = "Something went wrong";
        errorMessage = "Automation fail at click_duit_now";
        return printError();
    }

    try {
        transaction_details();
    } catch (e) {
        error_status = "3";
        message = "Something went wrong";
        errorMessage = "Automation fail at transaction_details";
        return printError();
    }

    for (let i = 0; i < data.beneficiaries.length; i++) { // If one of the beneficiaries fail, stop the whole process or pass to next beneficiary?
        let bene = data.beneficiaries[i];
        log("-".repeat(22) + " Adding beneficiary details " + (i + 1) + " " + "-".repeat(22));

        try {
            add_beneficiary_button();
        } catch (e) {
            error_status = "3";
            message = "Something went wrong";
            errorMessage = "Automation fail at add_beneficiary_button";
            return printError();
        }

        try {
            beneficiary_details(bene.amount, bene.bene_acc_no, bene.bene_name);
        } catch (e) {
            error_status = "3";
            message = "Something went wrong";
            errorMessage = "Automation fail at beneficiary_details";
            return printError();
        }

        try {
            choose_bank(bene.bank_code);
        } catch (e) {
            error_status = "3";
            message = "Something went wrong";
            errorMessage = "Automation fail at choose_bank";
            return printError();
        }

        try {
            resident_option();
        } catch (e) {
            error_status = "3";
            message = "Something went wrong";
            errorMessage = "Automation fail at resident_option";
            return printError();
        }

        try {
            additional_beneficiary_details(bene.recRef);
        } catch (e) {
            error_status = "3";
            message = "Something went wrong";
            errorMessage = "Automation fail at additional_beneficiary_details";
            return printError();
        }

        try {
            click_order_details();
        } catch (e) {
            error_status = "3";
            message = "Something went wrong";
            errorMessage = "Automation fail at order_details";
            return printError();
        }

        try {
            click_ok();
        } catch (e) {
            error_status = "3";
            message = "Something went wrong";
            errorMessage = "Automation fail at click_ok";
            return printError();
        }

        try {
            if (!check_bene(bene.bene_name, data.similarityThreshold, bene.tran_id)) {
                continue;
            }
        } catch (e) {
            error_status = "3";
            message = "Something went wrong";
            errorMessage = "Automation fail at check_bene";
            return printError();
        }

        try {
            save_screenshot(bene.tran_id);
        } catch (e) {
            error_status = "3";
            message = "Something went wrong";
            errorMessage = "Automation fail at save_screenshot";
            return printError();
        }

        try {
            click_confirm();
        } catch (e) {
            error_status = "3";
            message = "Something went wrong";
            errorMessage = "Automation fail at click_confirm";
            return printError();
        }

        log("✅ Finished adding beneficiary details " + (i + 1));
    }

    try {
        preview_button();
    } catch (e) {
        error_status = "3";
        message = "Something went wrong";
        errorMessage = "Automation fail at preview_button";
        return printError();
    }

    try {
        confirm_transfer();
    } catch (e) {
        error_status = "3";
        message = "Something went wrong";
        errorMessage = "Automation fail at confirm_transfer";
        return printError();
    }

    try {
        approve();
    } catch (e) {
        error_status = "3";
        message = "Something went wrong";
        errorMessage = "Automation fail at approve";
        return printError();
    }

    try {
        transfer_password(data.tranPass);
    } catch (e) {
        error_status = "3";
        message = "Something went wrong";
        errorMessage = "Automation fail at transfer_password";
        return printError();
    }

    try {
        success_transfer();
    } catch (e) {
        error_status = "3";
        message = "Something went wrong";
        errorMessage = "Automation fail at success_transfer";
        return printError();
    }


    try {
        download_transfer_slip();
    } catch (e) {
        error_status = "5";
        message = "Transaction Success";
        errorMessage = "Fail to download slip";
        return printError();
    }

    try {
        nav_accounts();

        let runtime = (new Date() - start_time) / 1000;
        let balance = grab_balance();
        log("-".repeat(22) + ` Total runtime: ${runtime} seconds ` + "-".repeat(21));
        log(JSON.stringify({
            status: error_status,
            message: message,
            errorMessage: errorMessage,
            balance: balance
        }));

        return close_app();
    } catch (e) {
        error_status = "3";
        message = "Something went wrong";
        errorMessage = "Automation fail at nav_accounts";
        return printError();
    }

    function printError() {
        let runtime = (new Date() - start_time) / 1000;
        log("-".repeat(22) + ` Total runtime: ${runtime} seconds ` + "-".repeat(21));
        log(JSON.stringify({
            status: error_status,
            message: message,
            errorMessage: errorMessage,
            balance: balance
        }));
        return close_app();
    }
}

module.exports = {
    run_transfer_process
};