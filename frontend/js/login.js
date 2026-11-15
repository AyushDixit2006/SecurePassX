const API_ORIGIN =
    window.location.port === "5500"
        ? "http://127.0.0.1:8000"
        : "";

const BASE_URL = `${API_ORIGIN}/api/auth`;

let faceRecoveryAuthorizationToken = null;

// =====================
// GET EMAIL
// =====================
function getEmail() {
    return (
        document.getElementById("email")?.value ||
        document.getElementById("faceEmail")?.value
    ).trim();
}


// =====================
// SEND NORMAL OTP
// =====================
async function sendOTP() {
    const email = getEmail();

    if (!email) {
        showError("Enter email");
        return;
    }

    try {
        const res = await fetch(`${BASE_URL}/send-otp/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, purpose: "login" })
        });

        const data = await res.json();

        if (!res.ok) {
            showError(data.error || "Server error");
            return;
        }

        showSuccess("OTP sent successfully.");

        document.getElementById("otpContainer").style.display = "flex";
        document.getElementById("loginBtn").style.display = "block";
        document.getElementById("sendOtpBtn").style.display = "none";
        document.getElementById("resendOtpBtn").style.display = "block";

        startOtpTimer();

    } catch (err) {
        console.error(err);
        showError("Server error");
    }
}


// =====================
// LOGIN WITH OTP
// =====================
async function loginOTP() {
    const email = document.getElementById("email").value.trim();
    const otp = getOTPValue();

    if (!email || !otp) {
        showError("Enter email and OTP");
        return;
    }

    try {
        const res = await fetch(`${BASE_URL}/login-otp/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, otp })
        });

        const data = await res.json();

        if (!res.ok) {
            showError(data.error || "Login failed");

            if (data.error?.includes("Too many attempts")) {
                document.querySelectorAll(".otp-container input").forEach(input => {
                    input.disabled = true;
                });

                const resendBtn = document.getElementById("resendOtpBtn");
                if (resendBtn) {
                    resendBtn.style.pointerEvents = "none";
                    resendBtn.style.opacity = "0.5";
                }

                const loginBtn = document.getElementById("loginBtn");
                if (loginBtn) loginBtn.disabled = true;
            }

            return;
        }

        if (data.access && data.refresh) {
            localStorage.setItem("user_email", email);
            localStorage.setItem("access_token", data.access);
            localStorage.setItem("refresh_token", data.refresh);

            showSuccess("Login successful.");

            setTimeout(() => {
                window.location.href = "dashboard.html";
            }, 800);
        }

    } catch (err) {
        console.error(err);
        showError("Server error");
    }
}


// =====================
// LOGIN WITH FACE
// =====================
async function loginFace() {
    const email = document.getElementById("faceEmail")?.value.trim();

    if (!email) {
        showError("Enter email first.");
        return;
    }

    // Never expose recovery controls before a qualifying liveness failure.
    hideFaceRecoveryControls();

    try {
        const blockResponse = await fetch(`${BASE_URL}/check-block/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email })
        });

        const blockData = await blockResponse.json();

        if (blockData.blocked) {
            updateScanText("Face login temporarily blocked.");

            showError(
                `Face login temporarily blocked. Try again in ${Math.ceil(blockData.remaining_seconds / 60)
                } minute(s). You can use normal OTP login.`
            );

            return;
        }

        await openCamera();

        const images = await captureAndStop();

        if (!images || images.length < 3) {
            showError("Face capture failed. Please try again.");
            return;
        }

        const res = await fetch(`${BASE_URL}/login-face/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, images })
        });

        const data = await res.json();

        if (res.ok && data.access && data.refresh) {
            localStorage.setItem("user_email", email);
            localStorage.setItem("access_token", data.access);
            localStorage.setItem("refresh_token", data.refresh);

            showSuccess("Face login successful.");

            setTimeout(() => {
                window.location.href = "dashboard.html";
            }, 800);

            return;
        }

        // Face mismatch block: never offer face recovery here.
        if (res.status === 429 && data.blocked) {
            hideFaceRecoveryControls();

            showError(
                "Face login blocked for 15 minutes. You can use normal OTP login."
            );

            return;
        }

        // First and second genuine face mismatch.
        if (res.status === 401 && Number.isInteger(data.failed_attempts)) {
            hideFaceRecoveryControls();

            const remaining = data.attempts_remaining;

            if (remaining === 1) {
                showError("Warning! This is your last attempt.");
            } else {
                showError(`Face mismatch. ${remaining} attempts remaining.`);
            }
            return;
        }

        // Registered face matched, but movement/liveness failed.
        if (
            data.liveness_failed_attempts &&
            data.recovery_required === true
        ) {
            showFaceRecoveryOTPControls();

            showError(
                "Insufficient movement detected after three attempts. Verify your registered email to recover your face."
            );

            return;
        }

        if (Number.isInteger(data.liveness_failed_attempts)) {
            showError(
                data.error || "Please move your face slightly and try again."
            );

            return;
        }

        showError(data.error || "Face login failed.");

    } catch (err) {
        console.error("Face login error:", err);
        showError("Unable to complete face login. Please try again.");
    }
}


// =====================
// RECOVERY UI
// =====================
function hideFaceRecoveryControls() {
    faceRecoveryAuthorizationToken = null;

    const section = document.getElementById("faceRecoverySection");
    const updateBtn = document.getElementById("updateFaceBtn");
    const otpContainer = document.getElementById("faceRecoveryOtpContainer");

    if (section) section.style.display = "none";
    if (updateBtn) updateBtn.style.display = "none";
    if (otpContainer) otpContainer.style.display = "none";

    const otpInput = document.getElementById("faceRecoveryOtp");
    if (otpInput) otpInput.value = "";

    const sendBtn = document.getElementById("sendFaceRecoveryOtpBtn");
    if (sendBtn) {
        sendBtn.style.display = "block";
        sendBtn.disabled = false;
    }
}

function showFaceRecoveryOTPControls() {
    const section = document.getElementById("faceRecoverySection");
    const updateBtn = document.getElementById("updateFaceBtn");

    if (section) section.style.display = "block";
    if (updateBtn) updateBtn.style.display = "none";

    const otpContainer = document.getElementById("faceRecoveryOtpContainer");
    if (otpContainer) otpContainer.style.display = "none";
}

window.showFaceRecoverySection = function () {
    if (!faceRecoveryAuthorizationToken) {
        showError("Verify your recovery OTP first.");
        return;
    }

    const section = document.getElementById("faceRecoverySection");
    if (section) section.style.display = "block";
};


// =====================
// SEND FACE RECOVERY OTP
// =====================
async function sendFaceRecoveryOTP() {


    // A new recovery OTP requires fresh verification.
    faceRecoveryAuthorizationToken = null;

    const updateBtn = document.getElementById("updateFaceBtn");
    if (updateBtn) updateBtn.style.display = "none";

    const email = document.getElementById("faceEmail")?.value.trim();

    if (!email) {
        showError("Enter your registered email first.");
        return;
    }

    try {
        const res = await fetch(`${BASE_URL}/send-otp/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                email,
                purpose: "face_recovery"
            })
        });

        const data = await res.json();

        if (!res.ok) {
            showError(data.error || "Unable to send recovery OTP.");
            return;
        }

        const otpContainer = document.getElementById("faceRecoveryOtpContainer");
        const sendBtn = document.getElementById("sendFaceRecoveryOtpBtn");

        if (otpContainer) otpContainer.style.display = "block";
        if (sendBtn) sendBtn.style.display = "none";

        showSuccess("Recovery OTP sent to your registered email.");

    } catch (err) {
        console.error("Recovery OTP error:", err);
        showError("Unable to send recovery OTP.");
    }
}


// =====================
// VERIFY FACE RECOVERY OTP
// =====================
async function verifyFaceRecoveryOTP() {
    const email = document.getElementById("faceEmail")?.value.trim();
    const otp = document.getElementById("faceRecoveryOtp")?.value.trim();

    if (!email || !otp) {
        showError("Enter your registered email and recovery OTP.");
        return;
    }

    try {
        const res = await fetch(`${BASE_URL}/verify-otp/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                email,
                otp,
                purpose: "face_recovery"
            })
        });

        const data = await res.json();

        if (!res.ok) {
            showError(data.error || "OTP verification failed.");
            return;
        }

        if (!data.authorization_token) {
            showError("Server did not return a recovery authorization token.");
            return;
        }

        faceRecoveryAuthorizationToken = data.authorization_token;

        const otpContainer = document.getElementById("faceRecoveryOtpContainer");
        const updateBtn = document.getElementById("updateFaceBtn");
        const sendBtn = document.getElementById("sendFaceRecoveryOtpBtn");

        if (otpContainer) otpContainer.style.display = "none";
        if (sendBtn) sendBtn.style.display = "none";
        if (updateBtn) updateBtn.style.display = "block";

        showSuccess("Recovery OTP verified. You can now update your face.");

    } catch (err) {
        console.error("Recovery verification error:", err);
        showError("Unable to verify recovery OTP.");
    }
}


// =====================
// UPDATE FACE
// =====================
async function updateFace() {
    const email = document.getElementById("faceEmail")?.value.trim();

    if (!faceRecoveryAuthorizationToken) {
        showError("Verify your face recovery OTP before updating your face.");
        return;
    }

    if (!email) {
        showError("Enter your registered email first.");
        return;
    }

    try {
        await openCamera();

        const images = await captureAndStop();

        if (!images || images.length < 3) {
            showError("Face capture failed. Please try again.");
            return;
        }

        const res = await fetch(`${BASE_URL}/update-face/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                email,
                images,
                authorization_token: faceRecoveryAuthorizationToken
            })
        });

        const data = await res.json();

        if (!res.ok) {
            showError(data.error || "Face update failed.");
            return;
        }

        if (data.message) {
            faceRecoveryAuthorizationToken = null;

            hideFaceRecoveryControls();

            showSuccess("Face updated successfully.");
        } else {
            showError(data.error || "Face update failed.");
        }

    } catch (err) {
        console.error("Face update error:", err);
        showError("Server error while updating face.");
    }
}


// =====================
// SHOW / HIDE FEEDBACK
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

    if (section) section.style.display = "block";
}


// =====================
// OTP TIMER
// =====================
function startOtpTimer() {
    const resendBtn = document.getElementById("resendOtpBtn");

    if (!resendBtn) return;

    let timeLeft = 60;

    resendBtn.style.pointerEvents = "none";
    resendBtn.style.opacity = "0.6";

    resendBtn.innerHTML = `Resend OTP (${timeLeft}s)`;

    const interval = setInterval(() => {
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
// TOKEN REFRESH
// =====================
async function refreshToken() {
    const refresh = localStorage.getItem("refresh_token");

    if (!refresh) {
        console.log("No refresh token found");
        return null;
    }

    try {
        const res = await fetch(`${API_ORIGIN}/api/token/refresh/`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ refresh })
        });

        const data = await res.json();

        if (!res.ok || !data.access) {
            console.log("Refresh failed");
            return null;
        }

        localStorage.setItem("access_token", data.access);

        if (data.refresh) {
            localStorage.setItem("refresh_token", data.refresh);
        }

        return data.access;

    } catch (err) {
        console.error("Refresh error:", err);
        return null;
    }
}
