/**
 * app.js — Chat frontend logic
 * Handles message sending/receiving, markdown rendering, auto-scroll
 */

const messagesArea = document.getElementById('messagesArea');
const welcomeScreen = document.getElementById('welcomeScreen');
const typingIndicator = document.getElementById('typingIndicator');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');

let chatStarted = false;

// Configure marked for markdown rendering
marked.setOptions({
    breaks: true,
    gfm: true,
    headerIds: false
});

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
    const text = btn.textContent.replace(/^[\s\S]*?\n/, '').trim();
    const lines = btn.innerText.split('\n');
    const query = lines[lines.length - 1].trim();
    userInput.value = query;
    sendMessage();
}

async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    // Hide welcome screen
    if (!chatStarted) {
        chatStarted = true;
        welcomeScreen.style.display = 'none';
    }

    // Add user message
    addMessage(message, 'user');
    userInput.value = '';
    userInput.style.height = 'auto';
    sendBtn.disabled = true;

    // Show typing
    typingIndicator.classList.add('show');
    scrollToBottom();

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });

        const data = await response.json();

        // Hide typing
        typingIndicator.classList.remove('show');

        if (data.answer) {
            addMessage(data.answer, 'bot', {
                intent: data.intent,
                time: data.time,
                chunks: data.num_chunks
            });
        } else {
            addMessage('Xin lỗi, em không thể xử lý câu hỏi này.', 'bot');
        }
    } catch (error) {
        typingIndicator.classList.remove('show');
        addMessage('Xin lỗi, có lỗi kết nối. Vui lòng thử lại sau.', 'bot');
    }

    sendBtn.disabled = false;
    userInput.focus();
}

function addMessage(text, type, meta = {}) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${type}`;

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

    // Add meta info for bot messages
    if (type === 'bot' && (meta.intent || meta.time)) {
        const metaDiv = document.createElement('div');
        metaDiv.className = 'message-meta';
        const parts = [];
        if (meta.intent) parts.push(`Intent: ${meta.intent}`);
        if (meta.time) parts.push(`${meta.time}s`);
        if (meta.chunks) parts.push(`${meta.chunks} chunks`);
        metaDiv.textContent = parts.join(' • ');
        content.appendChild(metaDiv);
    }

    msgDiv.appendChild(avatar);
    msgDiv.appendChild(content);

    // Insert before typing indicator
    messagesArea.insertBefore(msgDiv, typingIndicator);
    scrollToBottom();
}

function scrollToBottom() {
    setTimeout(() => {
        messagesArea.scrollTop = messagesArea.scrollHeight;
    }, 50);
}

// Focus input on load
userInput.focus();
