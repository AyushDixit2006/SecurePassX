const BASE_URL = "http://127.0.0.1:8000/api/auth";


// =====================
// GET EMAIL
// =====================
function getEmail() {
    return document.getElementById("email").value;
}


// =====================
// SEND OTP (STEP 1 → 2)
// =====================
async function sendOTP() {

    let email = getEmail();

    if (!email) {
        showError("Enter email");
        return;
    }

    try {
        let res = await fetch(`${BASE_URL}/send-otp/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, purpose: "register" })
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

            // 👉 Move to STEP 2 (KEEP SAME)
            goToStep(2);

            // ✅ SHOW RESEND BUTTON
            const resendBtn = document.getElementById("resendOtpBtn");
            if (resendBtn) {
                resendBtn.style.display = "block";
            }

            // ✅ START TIMER (KEEP YOUR FUNCTION)
            startOtpTimerReg();

        } else {

            showError(data.error);

            // 🔁 EXISTING REDIRECT (KEEP SAFE)
            if (data.error && data.error.includes("already registered")) {

                setTimeout(() => {
                    window.location.href = `login.html?email=${encodeURIComponent(email)}`;
                }, 1200);
            }
        }

    } catch (err) {
        console.error(err);
        showError("Server error");
    }
}


// =====================
// VERIFY OTP (STEP 2 → 3)
// =====================
async function verifyOTP() {

    let email = getEmail();
    let otp = getOTPValue();

    if (!email || !otp) {
        showError("Enter OTP");
        return;
    }

    try {
        let res = await fetch(`${BASE_URL}/verify-otp/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, otp })
        });

        let data = await res.json();

        if (data.message) {

            showSuccess("OTP Verified ✅");

            // 👉 Move to STEP 3
            goToStep(3);

        } else {

            showError(data.error);

            // 🚫 BLOCK UI AFTER MAX ATTEMPTS
            if (data.error && data.error.includes("Too many attempts")) {

                document.querySelectorAll(".otp-container input").forEach(input => {
                    input.disabled = true;
                });

                const resendBtn = document.getElementById("resendOtpBtn");
                if (resendBtn) {
                    resendBtn.style.pointerEvents = "none";
                    resendBtn.style.opacity = "0.5";
                }

                // 🚫 Disable Verify button
                const verifyBtn = document.querySelector(".btn.primary");
                if (verifyBtn) {
                    verifyBtn.disabled = true;
                }
            }
        }

    } catch (err) {
        console.error(err);
        showError("Server error");
    }
}


// =====================
// REGISTER FACE
// =====================
async function registerFace() {

    let email = getEmail();

    if (!email) {
        showError("Enter email first");
        return;
    }

    updateScanText("Opening camera...");
    await openCamera();

    try {
        let images = await captureAndStop();

        if (!images || images.length < 3) {
            updateScanText("Capture failed ❌");
            showError("Face capture failed");
            return;
        }

        updateScanText("Verifying face...");

        let res = await fetch(`${BASE_URL}/face-register/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, images })
        });

        let data = await res.json();

        if (data.message) {

            updateScanText("Face Registered ✅");
            showSuccess("Registration Complete 🎉");

            setTimeout(() => {
                window.location.href = "login.html";
            }, 1200);

        } else {
            updateScanText("Failed ❌");
            showError(data.error);
        }

    } catch (err) {
        console.error(err);
        updateScanText("Error ❌");
        showError("Server error");
    }
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
// Start OTP Timer
// =====================

function startOtpTimerReg() {

    let resendBtn = document.getElementById("resendOtpBtn");
    let timerEl = document.getElementById("timer");

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