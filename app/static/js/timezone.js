/* ════════ IST TIMEZONE UTILITIES ════════ */

/**
 * Format an ISO UTC string to Indian Standard Time.
 * @param {string} isoString - ISO 8601 date string (UTC)
 * @returns {string} Formatted IST string like "13 May 2026, 10:40 PM IST"
 */
function formatIST(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    }) + ' IST';
}

/**
 * Short IST format for compact views.
 */
function formatISTShort(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: '2-digit',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    });
}

/**
 * Date-only IST format.
 */
function formatISTDate(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    });
}

/**
 * Relative time in IST context (e.g., "2h ago", "yesterday").
 */
function timeAgoIST(isoString) {
    if (!isoString) return '';
    const now = new Date();
    const date = new Date(isoString);
    const diff = Math.floor((now - date) / 1000);

    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    if (diff < 172800) return 'yesterday';
    if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
    return formatISTShort(isoString);
}
