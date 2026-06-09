/* ════════ CHAT JAVASCRIPT ════════ */

let currentRoom = null;
let typingTimeout = null;

document.addEventListener('DOMContentLoaded', () => {
    // Check if we're in a room page
    if (typeof ROOM_ID !== 'undefined' && ROOM_ID) {
        initChatRoom(ROOM_ID);
    } else {
        loadConversations();
    }
});

// ─── Conversations list ───
async function loadConversations() {
    const data = await api('/chat/api/conversations');

    document.getElementById('conv-skeleton').style.display = 'none';
    const list = document.getElementById('conversation-list');
    list.style.display = 'block';

    if (!data || data.length === 0) {
        list.innerHTML = `
            <div class="empty-state" style="padding: var(--space-xl);">
                <div class="empty-icon">💬</div>
                <h3>No conversations yet</h3>
                <p style="font-size: var(--font-size-sm);">Start a new chat!</p>
            </div>`;
        return;
    }

    list.innerHTML = data.map(c => `
        <div class="conversation-item" onclick="openConversation('${c.room}')">
            <div class="user-avatar">${c.avatar}</div>
            <div class="conversation-info">
                <div class="conversation-name">${c.name}</div>
                <div class="conversation-preview">${c.last_message || 'No messages yet'}</div>
            </div>
            <div class="conversation-meta">
                <div class="conversation-time">${c.last_time ? timeAgo(c.last_time) : ''}</div>
                ${c.unread > 0 ? `<div class="conversation-unread">${c.unread}</div>` : ''}
            </div>
        </div>
    `).join('');
}

function openConversation(room) {
    window.location.href = `/chat/room/${room}`;
}

// ─── Chat Room ───
function initChatRoom(roomId) {
    currentRoom = roomId;

    // Join room via WebSocket
    if (socket) {
        socket.emit('join_room', { room: roomId });

        socket.on('new_message', (data) => {
            if (data.room === currentRoom) {
                appendMessage(data);
                scrollToBottom();

                // Send read receipt
                socket.emit('read_receipt', {
                    room: currentRoom,
                    message_ids: [data.id]
                });
            }
        });

        socket.on('user_typing', (data) => {
            if (data.room === currentRoom) {
                document.getElementById('typing-area').style.display = 'block';
                document.getElementById('typing-user').textContent = data.username;
            }
        });

        socket.on('user_stop_typing', (data) => {
            if (data.room === currentRoom) {
                document.getElementById('typing-area').style.display = 'none';
            }
        });

        socket.on('message_ack', (data) => {
            console.log('Message delivered:', data.id);
        });
    }

    // Load history
    loadChatHistory(roomId);

    // Set room info
    const parts = roomId.split('_');
    if (parts[0] === 'dm') {
        document.getElementById('room-status').textContent = 'Direct Message';
    } else {
        document.getElementById('room-status').textContent = 'Group Chat';
    }

    // Input events
    const input = document.getElementById('message-input');
    if (input) {
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });

        input.addEventListener('input', () => {
            if (socket) {
                socket.emit('typing', { room: currentRoom });
                clearTimeout(typingTimeout);
                typingTimeout = setTimeout(() => {
                    socket.emit('stop_typing', { room: currentRoom });
                }, 2000);
            }
        });
    }
}

async function loadChatHistory(roomId) {
    const data = await api(`/chat/api/history/${roomId}`);
    const container = document.getElementById('chat-messages');

    if (data && data.messages) {
        container.innerHTML = '';

        if (data.messages.length === 0) {
            container.innerHTML = `
                <div class="chat-empty">
                    <div class="empty-icon">💬</div>
                    <h3>Start the conversation!</h3>
                </div>`;
            return;
        }

        data.messages.forEach(msg => appendMessage(msg));
        scrollToBottom();

        // Set room name from first other user's message
        const otherMsg = data.messages.find(m => !m.is_mine);
        if (otherMsg) {
            document.getElementById('room-name').textContent = otherMsg.sender_name;
            document.getElementById('room-avatar').textContent = otherMsg.sender_avatar;
        }
    }

    document.getElementById('room-status').textContent = 'Online';
}

function appendMessage(msg) {
    const container = document.getElementById('chat-messages');
    const isMine = msg.is_mine || (typeof CURRENT_USER_ID !== 'undefined' && msg.sender_id === CURRENT_USER_ID);

    const div = document.createElement('div');
    div.className = `message-bubble ${isMine ? 'sent' : 'received'}`;
    div.innerHTML = `
        ${!isMine ? `<div class="message-sender">${msg.sender_name}</div>` : ''}
        <div>${msg.content}</div>
        <div class="message-time">${msg.created_at ? timeAgo(msg.created_at) : 'now'}</div>
    `;
    container.appendChild(div);
}

function sendMessage() {
    const input = document.getElementById('message-input');
    const content = input.value.trim();
    if (!content || !currentRoom || !socket) return;

    socket.emit('send_message', {
        room: currentRoom,
        message: content
    });

    input.value = '';

    // Stop typing indicator
    socket.emit('stop_typing', { room: currentRoom });
}

function scrollToBottom() {
    const container = document.getElementById('chat-messages');
    if (container) container.scrollTop = container.scrollHeight;
}

// ─── New chat ───
function showNewChatModal() {
    document.getElementById('new-chat-modal').style.display = 'flex';
}

async function searchChatUser(query) {
    if (query.length < 2) {
        document.getElementById('new-chat-results').innerHTML = '';
        return;
    }

    const data = await api(`/api/search/users?q=${encodeURIComponent(query)}`);
    const results = document.getElementById('new-chat-results');

    if (data && data.length) {
        results.innerHTML = data.map(u => `
            <div style="display:flex;align-items:center;gap:8px;padding:8px;cursor:pointer;border-radius:8px;transition:background 0.15s;" onmouseover="this.style.background='var(--bg-glass-hover)'" onmouseout="this.style.background=''" onclick="startDM(${u.id})">
                <div class="user-avatar" style="width:32px;height:32px;font-size:12px;">${u.avatar}</div>
                <div><div style="font-weight:600;font-size:var(--font-size-sm);">${u.name}</div><div style="font-size:11px;color:var(--text-muted);">@${u.username}</div></div>
            </div>
        `).join('');
    } else {
        results.innerHTML = '<div style="padding:8px;color:var(--text-muted);font-size:var(--font-size-sm);">No users found</div>';
    }
}

async function startDM(userId) {
    const data = await api(`/chat/api/dm/${userId}`);
    if (data) {
        window.location.href = `/chat/room/${data.room}`;
    }
}
