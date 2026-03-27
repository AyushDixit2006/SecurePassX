const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const context = canvas.getContext("2d");

let stream = null;

// =====================
// OPEN CAMERA
// =====================
async function openCamera() {

    try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
        video.srcObject = stream;

        await new Promise(resolve => {
            video.onloadedmetadata = () => resolve();
        });


        toggleScanLine(true); // ✅ START SCAN

        console.log("✅ Camera started");
        updateScanText("Camera Ready");



    } catch (err) {
        console.error("❌ Camera error:", err);
        alert("Camera access denied");
    }
}


// =====================
// STOP CAMERA
// =====================
function stopCamera() {

    if (stream) {
        stream.getTracks().forEach(track => track.stop());
        video.srcObject = null;
        stream = null;

        toggleScanLine(false); // ❌ STOP SCAN

        updateScanText("Camera Stopped");
    }
}


// =====================
// CAPTURE FRAME
// =====================
function captureFrame() {

    if (!video.videoWidth) {
        console.error("❌ Video not ready");
        return null;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    context.drawImage(video, 0, 0);

    return canvas.toDataURL("image/jpeg");
}


// =====================
// CAPTURE MULTIPLE FRAMES (IMPROVED)
// =====================
async function captureMultipleFrames() {

    let images = [];

    updateScanText("Align your face...");

    // Wait for camera stability
    await new Promise(resolve => setTimeout(resolve, 600));

    for (let i = 0; i < 3; i++) {

        updateScanText(`Scanning ${i + 1}/3`);

        await new Promise(resolve => setTimeout(resolve, 800));

        let frame = captureFrame();

        if (frame) {
            images.push(frame);
        }
    }

    if (images.length < 3) {
        updateScanText("Capture failed ❌");
        return [];
    }

    updateScanText("Processing...");

    console.log("📸 Captured Frames:", images.length);

    return images;
}


// =====================
// SCAN TEXT UPDATE
// =====================
function updateScanText(text) {

    const el = document.getElementById("scanText");

    if (el) {
        el.innerText = text;
    }
}


// =====================
// AUTO STOP CAMERA AFTER USE (NEW)
// =====================
async function captureAndStop() {

    let images = await captureMultipleFrames();

    stopCamera();

    return images;
}


function toggleScanLine(isActive) {

    const cameraBox = document.querySelector(".camera-circle");

    if (!cameraBox) return;

    const scanLine = cameraBox.querySelector(".scan-line");

    if (!scanLine) return;

    if (isActive) {
        scanLine.classList.add("active");
    } else {
        scanLine.classList.remove("active");
    }
}