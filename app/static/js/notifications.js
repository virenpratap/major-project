/* ════════ NOTIFICATIONS ════════ */

// Real-time notification handler
// (Main logic is in app.js, this file handles notification-specific UI)

class NotificationManager {
    constructor() {
        this.pollInterval = null;
        this.init();
    }

    init() {
        // Start fallback polling if WebSocket is not connected
        setTimeout(() => {
            if (!socket || !socket.connected) {
                this.startPolling();
            }
        }, 5000);
    }

    startPolling() {
        this.pollInterval = setInterval(async () => {
            await loadNotificationCount();
        }, 30000); // Poll every 30 seconds
    }

    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new NotificationManager();
});
