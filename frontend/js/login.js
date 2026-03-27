const BASE_URL = "http://127.0.0.1:8000/api/auth";


// =====================
// GET EMAIL (SMART)
// =====================
function getEmail() {
    return (
        document.getElementById("email")?.value ||
        document.getElementById("faceEmail")?.value
    );
}


// =====================
// SEND OTP
// =====================
async function sendOTP() {

    let email = getEmail();

    if (!email) {
        alert("Enter email");
        return;
    }

    try {
        let res = await fetch(`${BASE_URL}/send-otp/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, purpose: "login" })
        });

        let data;
        try {
            data = await res.json();
        } catch {
            throw new Error("Invalid server response");
        }

        if (!res.ok) {
            showError(data.error || "Server error");
            return;
        }

        if (data.message) {

            showSuccess("OTP sent successfully 📩");

            // ✅ SHOW OTP INPUT
            document.getElementById("otpContainer").style.display = "flex";
            document.getElementById("loginBtn").style.display = "block";

            // ✅ HIDE SEND BUTTON
            document.getElementById("sendOtpBtn").style.display = "none";

            // ✅ SHOW RESEND BUTTON
            const resendBtn = document.getElementById("resendOtpBtn");
            resendBtn.style.display = "block";

            // ✅ START TIMER
            startOtpTimer();

        } else {
            showError(data.error);
        }

    } catch (err) {
        console.error(err);
        showError("Server error");
    }
}


// =====================
// LOGIN WITH OTP
// =====================
async function loginOTP() {

    let email = document.getElementById("email").value;
    let otp = getOTPValue();

    if (!email || !otp) {
        alert("Enter email and OTP");
        return;
    }

    try {
        let res = await fetch(`${BASE_URL}/login-otp/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, otp })
        });

        let data = await res.json();

        if (data.message) {

            // ✅ SAVE TOKEN (NEW)
            if (data.access) {
                localStorage.setItem("user_email", email);
                localStorage.setItem("access_token", data.access);
                localStorage.setItem("refresh_token", data.refresh);
            }

            showSuccess("Login Successful ✅");

            setTimeout(() => {
                window.location.href = "dashboard.html";
            }, 800);

        } else {

            showError(data.error);

            // 🚫 BLOCK UI AFTER MAX ATTEMPTS
            if (data.error && data.error.includes("Too many attempts")) {

                // Disable OTP inputs
                document.querySelectorAll(".otp-container input").forEach(input => {
                    input.disabled = true;
                });


                // Disable resend
                const resendBtn = document.getElementById("resendOtpBtn");
                if (resendBtn) {
                    resendBtn.style.pointerEvents = "none";
                    resendBtn.style.opacity = "0.5";
                }


                // Disable login button
                const loginBtn = document.getElementById("loginBtn");
                if (loginBtn) {
                    loginBtn.disabled = true;

                }

            }
        }

    } catch (err) {
        showError("Server error");
    }
}




// =====================
// LOGIN WITH FACE
// =====================
async function loginFace() {

    let email = document.getElementById("faceEmail")?.value;

    if (!email) {
        alert("Enter email first");
        return;
    }

    // ===============================
    // 🔥 CHECK BLOCK BEFORE CAMERA
    // ===============================
    try {
        let res = await fetch(`${BASE_URL}/check-block/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email })
        });

        let data = await res.json();

        if (data.blocked) {
            showError("You are blocked. Try again after 1 hour");
            return; // 🚫 STOP HERE (NO CAMERA)
        }

    } catch (err) {
        console.error("Block check failed:", err);
    }


    updateScanText("Opening camera...");
    await openCamera();   // 🔥 ADD THIS LINE

    try {
        let images = await captureAndStop();

        if (!images || images.length < 3) {
            updateScanText("Capture failed ❌");
            showError("Face capture failed");
            return;
        }

        updateScanText("Verifying...");

        let res = await fetch(`${BASE_URL}/login-face/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, images })
        });

        let data = await res.json();

        if (data.message) {

            // ✅ SAVE TOKEN (NEW)
            if (data.access) {
                localStorage.setItem("user_email", email);
                localStorage.setItem("access_token", data.access);
                localStorage.setItem("refresh_token", data.refresh);
                // 🔥 RESET FAIL COUNT
                localStorage.removeItem("face_fail_count");

            }

            updateScanText("Access Granted ✅");
            showSuccess("Face Login Success");

            setTimeout(() => {
                window.location.href = "dashboard.html";
            }, 800);

        } else {

            updateScanText("Face mismatch ❌");
            showError(data.error);

            // 🔥 GET FAIL COUNT
            let failCount = localStorage.getItem("face_fail_count") || 0;
            failCount = parseInt(failCount) + 1;

            localStorage.setItem("face_fail_count", failCount);

            console.log("Face Fail Count:", failCount);

            // 🔔 WARNING BEFORE FINAL ATTEMPT
            if (failCount === 2) {
                showError("⚠️ One more failed attempt will enable face update");
            }

            // 🔥 SHOW UPDATE BUTTON AFTER 3 FAILS
            if (failCount >= 3) {
                showUpdateButton();
            }
        }


    } catch (err) {
        console.error(err);
        updateScanText("Error ❌");
        showError("Server error");
    }
}


// =====================
// UPDATE FACE
// =====================
async function updateFace() {

    let email = getEmail();

    if (!email) {
        alert("Enter email first");
        return;
    }

    updateScanText("Opening camera...");

    // 🔥 FIX: REOPEN CAMERA
    await openCamera();

    updateScanText("Re-capturing face...");

    try {
        let images = await captureAndStop();

        if (!images || images.length < 3) {
            showError("Capture failed");
            return;
        }

        let res = await fetch(`${BASE_URL}/update-face/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, images })
        });

        let data = await res.json();

        if (data.message) {
            updateScanText("Face Updated ✅");
            showSuccess("Face updated successfully");

            // 🔥 RESET FAIL COUNT
            localStorage.removeItem("face_fail_count");

        } else {
            showError(data.error);
        }

    } catch (err) {
        console.error(err);
        showError("Server error");
    }
}


// =====================
// SHOW UPDATE BUTTON
// =====================
function showUpdateButton() {
    let btn = document.getElementById("updateFaceBtn");
    if (btn) btn.style.display = "block";
}


// =====================
// UI FEEDBACK SYSTEM
// =====================
function showSuccess(msg) {
    alert(msg);
}

function showError(msg) {
    alert(msg);
}


// =====================
// SHOW OTP SECTION
// =====================
function showOTPSection() {
    const section = document.getElementById("otpSection");

    if (section) {
        section.style.display = "block";
    }
}



// =====================
// Start OTP Timer
// =====================

function startOtpTimer() {

    let resendBtn = document.getElementById("resendOtpBtn");

    let timeLeft = 60;

    resendBtn.style.pointerEvents = "none";
    resendBtn.style.opacity = "0.6";

    resendBtn.innerHTML = `Resend OTP (${timeLeft}s)`;

    let interval = setInterval(() => {

        timeLeft--;

        resendBtn.innerHTML = `Resend OTP (${timeLeft}s)`;

        if (timeLeft <= 0) {
            clearInterval(interval);

            resendBtn.innerHTML = "Resend OTP";
            resendBtn.style.pointerEvents = "auto";
            resendBtn.style.opacity = "1";
        }

    }, 1000);
}


// =====================
//    TOKEN REFRESH 
// =====================
async function refreshToken() {

    const refresh = localStorage.getItem("refresh_token");

    if (!refresh) {
        console.log("No refresh token found");
        return null;
    }

    try {
        let res = await fetch("http://127.0.0.1:8000/api/token/refresh/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ refresh })
        });

        let data = await res.json();

        if (data.access) {
            localStorage.setItem("access_token", data.access);
            return data.access;
        } else {
            console.log("Refresh failed");
            return null;
        }

    } catch (err) {
        console.error("Refresh error:", err);
        return null;
    }
}