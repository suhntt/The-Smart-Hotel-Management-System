// Receptionist Camera and Verification Interface Manager

let videoStream = null;
const videoEl = document.getElementById('webcam-feed');
const cameraSelect = document.getElementById('camera-source');

// OCR and Face states
let ocrResultData = null;
let faceResultData = null;

function startCamera() {
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        const constraints = {
            video: {
                width: { ideal: 640 },
                height: { ideal: 480 }
            }
        };

        navigator.mediaDevices.getUserMedia(constraints)
            .then(function(stream) {
                videoStream = stream;
                videoEl.srcObject = stream;
                videoEl.play();
                document.getElementById('camera-placeholder').classList.add('d-none');
                videoEl.classList.remove('d-none');
                showToast("Webcam connected successfully", "success");
            })
            .catch(function(err) {
                console.warn("Camera access failed, falling back to manual upload mode:", err);
                showToast("Camera access blocked. Using file upload fallback.", "warning");
                enableManualUploadFallback();
            });
    } else {
        showToast("Webcam API not supported. Using file upload fallback.", "warning");
        enableManualUploadFallback();
    }
}

function stopCamera() {
    if (videoStream) {
        videoStream.getTracks().forEach(track => track.stop());
        videoStream = null;
    }
}

function enableManualUploadFallback() {
    const fallbacks = document.querySelectorAll('.camera-fallback-input');
    fallbacks.forEach(el => el.classList.remove('d-none'));
}

// Draw the current video frame into a Blob
function getFrameBlob() {
    if (!videoStream || videoEl.paused) {
        return null;
    }
    
    const canvas = document.createElement('canvas');
    canvas.width = videoEl.videoWidth || 640;
    canvas.height = videoEl.videoHeight || 480;
    
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
    
    return new Promise((resolve) => {
        canvas.toBlob((blob) => {
            resolve(blob);
        }, 'image/jpeg', 0.9);
    });
}

// 1. Process Aadhaar OCR Scan
async function scanAadhaar(bookingId, simulateAi = false) {
    const scanBtn = document.getElementById('btn-scan-aadhaar');
    const statusDiv = document.getElementById('ocr-results-status');
    const fallbackFile = document.getElementById('aadhaar-file-fallback').files[0];
    
    let imageBlob = null;
    
    if (videoStream) {
        imageBlob = await getFrameBlob();
    }
    
    if (!imageBlob && fallbackFile) {
        imageBlob = fallbackFile;
    }
    
    if (!imageBlob) {
        alert("Please enable the webcam or choose a mock Aadhaar Card image file to scan.");
        return;
    }
    
    scanBtn.disabled = true;
    scanBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Extracting Text...';
    statusDiv.innerHTML = '<span class="text-muted">Extracting text and scanning details using EasyOCR...</span>';
    
    const formData = new FormData();
    formData.append('scanned_aadhaar', imageBlob, 'aadhaar_scan.jpg');
    
    // Add simulation URL flag if required
    let url = `/admin/checkin-verify/ocr/${bookingId}`;
    if (simulateAi) {
        url += '?simulate=true';
    }
    
    fetch(url, {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        scanBtn.disabled = false;
        scanBtn.innerHTML = '<i class="fas fa-id-card me-2"></i>Scan Physical Aadhaar';
        
        if (data.success) {
            ocrResultData = data;
            
            // Render OCR Results in panel
            const matchClass = data.aadhaar_match ? 'text-success' : 'text-danger';
            const matchIcon = data.aadhaar_match ? 'fa-check-circle' : 'fa-times-circle';
            
            statusDiv.innerHTML = `
                <div class="card bg-light p-3 border-0">
                    <h6 class="fw-bold mb-2">OCR Text Match Results:</h6>
                    <div class="row g-2 small">
                        <div class="col-6"><strong>Scanned Aadhaar:</strong> ${data.scanned_aadhaar_number}</div>
                        <div class="col-6"><strong>DB Aadhaar:</strong> ${data.db_aadhaar_number}</div>
                        <div class="col-6"><strong>Scanned Name:</strong> ${data.scanned_name}</div>
                        <div class="col-6"><strong>DB Cust Name:</strong> ${data.db_name}</div>
                        <div class="col-12 mt-2 pt-2 border-top">
                            <span class="${matchClass} fw-bold">
                                <i class="fas ${matchIcon} me-1"></i>
                                Aadhaar Number Match: ${data.aadhaar_match ? 'PASSED' : 'MISMATCH'}
                            </span>
                            <br>
                            <span class="fw-semibold text-muted">
                                Name Similarity Match: ${data.name_match_score}% (OCR Conf: ${data.confidence.toFixed(1)}%)
                            </span>
                        </div>
                    </div>
                </div>
            `;
            
            // Enable checkout completion if face match is also done
            evaluateOverallMatch();
        } else {
            statusDiv.innerHTML = `<span class="text-danger"><i class="fas fa-times-circle me-1"></i>Error: ${data.error}</span>`;
        }
    })
    .catch(err => {
        console.error(err);
        scanBtn.disabled = false;
        scanBtn.innerHTML = '<i class="fas fa-id-card me-2"></i>Scan Physical Aadhaar';
        statusDiv.innerHTML = `<span class="text-danger">Failed to scan Aadhaar. network error occurred.</span>`;
    });
}

// 2. Process Face Recognition Match
async function matchFace(bookingId, simulateAi = false) {
    const matchBtn = document.getElementById('btn-match-face');
    const statusDiv = document.getElementById('face-results-status');
    const fallbackFile = document.getElementById('face-file-fallback').files[0];
    
    let imageBlob = null;
    
    if (videoStream) {
        imageBlob = await getFrameBlob();
    }
    
    if (!imageBlob && fallbackFile) {
        imageBlob = fallbackFile;
    }
    
    if (!imageBlob) {
        alert("Please enable the webcam or choose a live snapshot image file to match.");
        return;
    }
    
    matchBtn.disabled = true;
    matchBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Comparing Faces...';
    statusDiv.innerHTML = '<span class="text-muted">Extracting face geometry and matching with database...</span>';
    
    const formData = new FormData();
    formData.append('live_frame', imageBlob, 'live_face.jpg');
    
    let url = `/admin/checkin-verify/face/${bookingId}`;
    if (simulateAi) {
        url += '?simulate=true';
    }
    
    fetch(url, {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        matchBtn.disabled = false;
        matchBtn.innerHTML = '<i class="fas fa-user-check me-2"></i>Compare Face & Webcam';
        
        if (data.success) {
            faceResultData = data;
            
            const matchClass = data.match ? 'text-success' : 'text-danger';
            const matchIcon = data.match ? 'fa-check-circle' : 'fa-times-circle';
            
            statusDiv.innerHTML = `
                <div class="card bg-light p-3 border-0">
                    <h6 class="fw-bold mb-2">Facial Comparison Results:</h6>
                    <div class="row g-2 small">
                        <div class="col-12">
                            <span class="${matchClass} fw-bold">
                                <i class="fas ${matchIcon} me-1"></i>
                                Biometric Verification: ${data.match ? 'MATCH VERIFIED' : 'MISMATCH / UNVERIFIED'}
                            </span>
                        </div>
                        <div class="col-12">
                            <strong>Biometric Match Score:</strong> ${data.score}%
                        </div>
                        <div class="col-12">
                            <strong>Face Distance Value:</strong> ${data.distance.toFixed(4)} (Threshold: &lt; 0.6)
                        </div>
                    </div>
                </div>
            `;
            
            evaluateOverallMatch();
        } else {
            statusDiv.innerHTML = `<span class="text-danger"><i class="fas fa-times-circle me-1"></i>Error: ${data.error}</span>`;
        }
    })
    .catch(err => {
        console.error(err);
        matchBtn.disabled = false;
        matchBtn.innerHTML = '<i class="fas fa-user-check me-2"></i>Compare Face & Webcam';
        statusDiv.innerHTML = `<span class="text-danger">Failed to process face encoding. Network error.</span>`;
    });
}

// 3. Evaluate Match States
function evaluateOverallMatch() {
    const finalCard = document.getElementById('final-checkin-card');
    const finalBtn = document.getElementById('btn-finalize-checkin');
    
    if (!ocrResultData || !faceResultData) {
        return;
    }
    
    finalCard.classList.remove('d-none');
    
    const isPassed = ocrResultData.aadhaar_match && faceResultData.match;
    
    if (isPassed) {
        document.getElementById('overall-match-badge').className = 'badge bg-success p-2 fs-6';
        document.getElementById('overall-match-badge').innerHTML = '<i class="fas fa-check-double me-1"></i>Verification Success (All Matches Passed)';
        finalBtn.className = 'btn btn-success w-100 fw-bold';
        finalBtn.innerHTML = 'Complete Check-In & Generate Pass';
    } else {
        document.getElementById('overall-match-badge').className = 'badge bg-danger p-2 fs-6';
        document.getElementById('overall-match-badge').innerHTML = '<i class="fas fa-exclamation-triangle me-1"></i>Verification Failed (Mismatch Detected)';
        finalBtn.className = 'btn btn-danger w-100 fw-bold';
        finalBtn.innerHTML = 'Force Check-In (Admin Override)';
    }
}

// 4. Submit Verification Logs and Update booking status
function finalizeCheckin(bookingId) {
    const finalBtn = document.getElementById('btn-finalize-checkin');
    const isPassed = ocrResultData.aadhaar_match && faceResultData.match;
    const finalStatus = isPassed ? 'VERIFIED' : 'FAILED';
    
    finalBtn.disabled = true;
    finalBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving Logs...';
    
    fetch(`/admin/checkin-verify/finalize/${bookingId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            status: finalStatus,
            scanned_aadhaar: ocrResultData.scanned_aadhaar_number,
            scanned_name: ocrResultData.scanned_name,
            ocr_confidence: ocrResultData.confidence,
            face_score: faceResultData.score
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            stopCamera();
            if (finalStatus === 'VERIFIED') {
                showToast("Check-In Complete! Pass generated.", "success");
                setTimeout(() => {
                    window.location.href = `/admin/bookings`;
                }, 1500);
            } else {
                showToast("Check-In Denied! Log saved.", "danger");
                setTimeout(() => {
                    window.location.href = `/admin/bookings`;
                }, 1500);
            }
        } else {
            alert("Failed to save verification logs.");
            finalBtn.disabled = false;
        }
    })
    .catch(err => {
        console.error(err);
        alert("Unexpected error finalising checkin.");
        finalBtn.disabled = false;
    });
}
