const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const captureBtn = document.getElementById('captureBtn');
const uploadBtn = document.getElementById('uploadBtn');
const fileInput = document.getElementById('fileInput');
const resultContent = document.getElementById('resultContent');
const esp32Status = document.getElementById('esp32Status');
const cameraOverlay = document.getElementById('cameraOverlay');

let stream = null;
let currentImageUrl = null;

// Start camera
async function startCamera() {
    try {
        stream = await navigator.mediaDevices.getUserMedia({ 
            video: { facingMode: 'environment' }
        });
        video.srcObject = stream;
        console.log('✅ Camera started');
        
        setTimeout(() => {
            cameraOverlay.classList.add('active');
            setTimeout(() => {
                cameraOverlay.classList.remove('active');
            }, 1500);
        }, 500);
    } catch (err) {
        console.error('Camera error:', err);
        resultContent.innerHTML = `
            <div class="error">
                ❌ Cannot access camera. Please upload an image instead.
            </div>
        `;
    }
}

// Classify image
async function classifyImage(imageBlob) {
    resultContent.innerHTML = `
        <div class="loading">
            <div class="spinner"></div>
            <p>Analyzing waste with YOLO AI...</p>
        </div>
    `;
    
    if (currentImageUrl) {
        URL.revokeObjectURL(currentImageUrl);
    }
    currentImageUrl = URL.createObjectURL(imageBlob);
    
    const reader = new FileReader();
    reader.onload = async function(e) {
        try {
            const response = await fetch('/classify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: e.target.result })
            });
            
            const result = await response.json();
            
            if (!result.success) {
                throw new Error(result.error);
            }
            
            displayResult(result);
            
            if (result.esp32_triggered) {
                updateESP32Status(true, result.sent_to_esp32);
            } else if (result.detections?.length > 0) {
                updateESP32Status(false);
            }
            
        } catch (error) {
            console.error('Error:', error);
            resultContent.innerHTML = `
                ${currentImageUrl ? `<img src="${currentImageUrl}" class="preview-image" alt="Uploaded">` : ''}
                <div class="error">❌ Error: ${error.message}</div>
            `;
        }
    };
    reader.readAsDataURL(imageBlob);
}

// Display results
function displayResult(result) {
    const detections = result.detections;
    const processedImage = result.processed_image;
    
    if (!detections || detections.length === 0) {
        resultContent.innerHTML = `
            ${processedImage ? `<img src="data:image/jpeg;base64,${processedImage}" class="preview-image" alt="Processed">` : ''}
            <div class="empty-state">
                <div class="empty-icon">🤔</div>
                <p>No waste detected. Try showing metal, paper, or plastic.</p>
            </div>
        `;
        return;
    }
    
    let detectionsHtml = '';
    const instructions = {
        'plastic': '♻️ Rinse and place in PLASTIC recycling bin',
        'metal': '🥫 Clean and place in METAL recycling bin',
        'paper': '📄 Keep dry and place in PAPER recycling bin'
    };
    
    detections.forEach(det => {
        const instruction = instructions[det.type] || '♻️ Dispose properly';
        detectionsHtml += `
            <div class="detection-card ${det.type}">
                <div class="detection-type">${det.type.toUpperCase()}</div>
                <div class="detection-confidence">Confidence: ${det.confidence}%</div>
                ${result.sent_to_esp32 === det.type ? '<div class="detection-badge badge-esp32">✅ Sent to ESP32 - LED Triggered</div>' : ''}
                <div class="instruction">
                    <p>💡 ${instruction}</p>
                </div>
            </div>
        `;
    });
    
    resultContent.innerHTML = `
        <img src="data:image/jpeg;base64,${processedImage}" class="preview-image" alt="Detection result">
        ${detectionsHtml}
    `;
}

// Update ESP32 status
function updateESP32Status(connected, wasteType = null) {
    const statusDot = esp32Status.querySelector('.status-dot');
    const statusText = esp32Status.querySelector('span:last-child');
    
    if (connected) {
        statusDot.classList.add('connected');
        statusText.innerHTML = `ESP32: Triggered - ${wasteType.toUpperCase()}`;
        setTimeout(() => {
            statusText.innerHTML = `ESP32: Connected`;
        }, 3000);
    } else {
        statusDot.classList.remove('connected');
        statusText.innerHTML = `ESP32: Not reachable`;
    }
}

// Check health
async function checkHealth() {
    try {
        const response = await fetch('/health');
        const data = await response.json();
        
        const statusDot = esp32Status.querySelector('.status-dot');
        const statusText = esp32Status.querySelector('span:last-child');
        
        statusDot.classList.add('connected');
        statusText.innerHTML = `ESP32: Configured (${data.esp32_url})`;
    } catch (error) {
        console.error('Health check failed:', error);
    }
}

// Event listeners
captureBtn.onclick = () => {
    if (!video.videoWidth) {
        resultContent.innerHTML = '<div class="error">❌ Camera not ready</div>';
        return;
    }
    
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext('2d');
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    canvas.toBlob(blob => {
        classifyImage(blob);
    }, 'image/jpeg', 0.9);
};

uploadBtn.onclick = () => fileInput.click();
fileInput.onchange = (e) => {
    if (e.target.files && e.target.files[0]) {
        classifyImage(e.target.files[0]);
    }
};

// Initialize
startCamera();
checkHealth();
setInterval(checkHealth, 30000);

// Cleanup
window.addEventListener('beforeunload', () => {
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
    }
    if (currentImageUrl) {
        URL.revokeObjectURL(currentImageUrl);
    }
});