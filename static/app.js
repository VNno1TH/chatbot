/**
 * app.js — Chat frontend logic
 * Handles message sending/receiving, markdown rendering, and user feedback.
 */

const messagesArea    = document.getElementById('messagesArea');
const welcomeScreen   = document.getElementById('welcomeScreen');
const typingIndicator = document.getElementById('typingIndicator');
const userInput       = document.getElementById('userInput');
const sendBtn         = document.getElementById('sendBtn');
const stopBtn         = document.getElementById('stopBtn');

let currentController = null;

let chatStarted = false;
let autoSpeakerOn = false;

// ── Session ID (persists for the browser tab lifetime) ──────────────────────
let sessionId = sessionStorage.getItem('haui_session_id');
if (!sessionId) {
    sessionId = 'sess_' + crypto.randomUUID();
    sessionStorage.setItem('haui_session_id', sessionId);
}

// ── Markdown renderer ────────────────────────────────────────────────────────
marked.setOptions({ breaks: true, gfm: true, headerIds: false });

// ── Input helpers ────────────────────────────────────────────────────────────
function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

function autoResize() {
    userInput.style.height = 'auto';
    userInput.style.height = Math.min(userInput.scrollHeight, 120) + 'px';
}

userInput.addEventListener('input', autoResize);

function sendSuggestion(btn) {
    const lines = btn.innerText.split('\n');
    const query = lines[lines.length - 1].trim();
    userInput.value = query;
    sendMessage();
}

// ── Send message ─────────────────────────────────────────────────────────────
async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    if (!chatStarted) {
        chatStarted = true;
        welcomeScreen.style.display = 'none';
    }

    addMessage(message, 'user');
    userInput.value = '';
    userInput.style.height = 'auto';
    sendBtn.style.display = 'none';
    stopBtn.style.display = 'block';

    typingIndicator.classList.add('show');
    scrollToBottom();

    currentController = new AbortController();

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, session_id: sessionId }),
            signal: currentController.signal
        });

        const data = await response.json();
        typingIndicator.classList.remove('show');

        if (data.answer) {
            addMessage(data.answer, 'bot', {
                intent:   data.intent,
                time:     data.time,
                chunks:   data.num_chunks,
                question: message,
            });
            if (autoSpeakerOn) readText(data.answer);
        } else {
            addMessage('Xin lỗi, em không thể xử lý câu hỏi này.', 'bot');
        }
    } catch (e) {
        typingIndicator.classList.remove('show');
        if (e.name === 'AbortError') {
            addMessage('Đã dừng tạo câu trả lời.', 'bot');
        } else {
            addMessage('Xin lỗi, có lỗi kết nối. Vui lòng thử lại sau.', 'bot');
        }
    } finally {
        sendBtn.style.display = 'block';
        stopBtn.style.display = 'none';
        userInput.focus();
        currentController = null;
    }
}

function stopMessage() {
    if (currentController) {
        currentController.abort();
    }
}

// ── Render message ───────────────────────────────────────────────────────────
function addMessage(text, type, meta = {}) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${type}`;

    // Avatar
    let avatar;
    if (type === 'bot') {
        avatar = document.createElement('img');
        avatar.className = 'message-avatar bot-avatar';
        avatar.src = '/favicon.png';
        avatar.alt = 'Bot';
    } else {
        avatar = document.createElement('div');
        avatar.className = 'message-avatar user-avatar';
        avatar.textContent = '👤';
    }

    const content = document.createElement('div');
    content.className = 'message-content';

    if (type === 'bot') {
        content.innerHTML = marked.parse(text);
    } else {
        content.textContent = text;
    }

    // Meta line (intent, time, chunks)
    if (type === 'bot' && (meta.intent || meta.time)) {
        const metaDiv = document.createElement('div');
        metaDiv.className = 'message-meta';
        const parts = [];
        if (meta.intent) parts.push(`Intent: ${meta.intent}`);
        if (meta.time)   parts.push(`${meta.time}s`);
        if (meta.chunks) parts.push(`${meta.chunks} chunks`);
        metaDiv.textContent = parts.join(' • ');
        content.appendChild(metaDiv);
    }

    // Feedback buttons (bot messages only)
    if (type === 'bot') {
        const fbDiv = document.createElement('div');
        fbDiv.className = 'feedback-buttons';
        fbDiv.dataset.question = meta.question || '';
        fbDiv.dataset.answer   = text.slice(0, 300);
        fbDiv.innerHTML = `
            <button class="fb-btn" onclick="sendFeedback(this, 'up')"   title="Câu trả lời hữu ích">👍</button>
            <button class="fb-btn" onclick="sendFeedback(this, 'down')" title="Câu trả lời chưa tốt">👎</button>
        `;
        content.appendChild(fbDiv);
    }

    msgDiv.appendChild(avatar);
    msgDiv.appendChild(content);
    messagesArea.insertBefore(msgDiv, typingIndicator);
    scrollToBottom();
}

// ── Feedback ─────────────────────────────────────────────────────────────────
async function sendFeedback(btn, type) {
    const container = btn.closest('.feedback-buttons');
    const question  = container.dataset.question || '';
    const answer    = container.dataset.answer   || '';

    // Ask for comment on thumbs-down
    let comment = '';
    if (type === 'down') {
        comment = prompt('Câu trả lời chưa tốt ở điểm nào? (bỏ trống nếu không muốn ghi)') || '';
    }

    try {
        await fetch('/api/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type, question, answer, comment }),
        });
    } catch { /* silent — feedback is best-effort */ }

    // Visual confirmation: replace buttons with thank-you text
    container.innerHTML = type === 'up'
        ? '<span class="fb-thanks">✅ Cảm ơn phản hồi của bạn!</span>'
        : '<span class="fb-thanks">📝 Đã ghi nhận, em sẽ cải thiện!</span>';
}

// ── Scroll helper ─────────────────────────────────────────────────────────────
function scrollToBottom() {
    setTimeout(() => { messagesArea.scrollTop = messagesArea.scrollHeight; }, 50);
}

// Focus input on load
userInput.focus();

// ── Voice Integration (Web Speech API) ───────────────────────────────────────
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let isRecording = false;

if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.lang = 'vi-VN';
    recognition.continuous = false; // continuous = true đôi khi gây lỗi network trên HTTP
    recognition.interimResults = true; // Hiển thị kết quả tạm thời để người dùng thấy mic đang hoạt động

    recognition.onstart = function() {
        isRecording = true;
        const btn = document.getElementById('voiceBtn');
        if (btn) btn.classList.add('recording');
        userInput.placeholder = "Đang nghe... (Nói xong nhấn lại nút Mic hoặc Enter để gửi)";
        userInput.value = '';
    };

    recognition.onresult = function(event) {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                finalTranscript += event.results[i][0].transcript;
            } else {
                interimTranscript += event.results[i][0].transcript;
            }
        }
        
        // Gộp text đã nhận diện
        const currentText = finalTranscript || interimTranscript;
        if (currentText) {
            userInput.value = currentText;
            autoResize();
        }
    };

    recognition.onerror = function(event) {
        console.error("Speech recognition error:", event.error);
        if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
            alert("Không có quyền truy cập Micro. Vui lòng kiểm tra cài đặt trình duyệt (Cho phép dùng Micro).");
        } else if (event.error === 'network') {
            alert("Lỗi mạng Speech API! Các nguyên nhân thường gặp:\n1. Bạn đang dùng Brave/Chromium (thiếu Google API).\n2. Bạn truy cập bằng 127.0.0.1 thay vì localhost.\n3. Máy tính bị tắt quyền Micro ở (Settings > Privacy > Microphone).\n\nCách khắc phục: Hãy mở web này bằng Google Chrome chuẩn qua địa chỉ http://localhost:5000");
        } else if (event.error !== 'no-speech') {
            // Không alert với no-speech vì nó hay xảy ra khi im lặng
            console.log("Lỗi nhận dạng giọng nói: " + event.error);
        }
        stopRecording();
    };

    recognition.onend = function() {
        // Tự động stop và khôi phục giao diện
        stopRecording();
        
        // Tự động gửi nếu có chữ và vừa kết thúc
        if (userInput.value.trim().length > 0) {
            sendMessage();
        }
    };
} else {
    // Ẩn nút mic nếu trình duyệt không hỗ trợ
    const vBtn = document.getElementById('voiceBtn');
    if (vBtn) vBtn.style.display = 'none';
}

function toggleRecording() {
    if (!recognition) {
        alert("Trình duyệt của bạn không hỗ trợ nhận dạng giọng nói. Vui lòng dùng Google Chrome, Edge hoặc Safari bản mới nhất.");
        return;
    }
    
    if (isRecording) {
        recognition.stop(); // Sẽ gọi onend -> sendMessage
    } else {
        try {
            recognition.start();
        } catch (e) {
            console.error("Lỗi khi start mic:", e);
        }
    }
}

function stopRecording() {
    isRecording = false;
    const btn = document.getElementById('voiceBtn');
    if (btn) btn.classList.remove('recording');
    userInput.placeholder = "Nhập câu hỏi về tuyển sinh HaUI...";
}

function toggleSpeaker() {
    autoSpeakerOn = !autoSpeakerOn;
    const btn = document.getElementById('speakerBtn');
    if (autoSpeakerOn) {
        btn.classList.add('active');
        btn.innerHTML = '🔊 Đang bật âm';
    } else {
        btn.classList.remove('active');
        btn.innerHTML = '🔇 Âm thanh';
        if (window.speechSynthesis) window.speechSynthesis.cancel();
    }
}

function readText(text) {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel(); // Dừng câu đang đọc (nếu có) trước khi đọc câu mới

    // Lọc bỏ ký tự Markdown báo lỗi phát âm
    const cleanText = text
        .replace(/[#*_`\[\]]/g, '')
        .replace(/https?:\/\/[^\s]+/g, 'đường dẫn liên kết');
    
    // Tách thành các đoạn ngắn hơn nếu cần (giúp Chrome API không bị nghẽn), nhưng ở đây tạm đọc cả câu.
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = 'vi-VN';
    utterance.rate = 1.0;
    window.speechSynthesis.speak(utterance);
}

