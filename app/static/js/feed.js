/* ════════ FEED JAVASCRIPT ════════ */
let feedPage = 1;
let feedLoading = false;
let currentScope = 'global';

document.addEventListener('DOMContentLoaded', () => {
    loadFeed();
});

function switchScope(scope) {
    if (scope === currentScope) return;
    currentScope = scope;
    feedPage = 1;

    // Update tab UI
    document.querySelectorAll('.feed-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`[data-scope="${scope}"]`)?.classList.add('active');

    // Clear and reload
    document.getElementById('feed-container').innerHTML = '';
    loadFeed();
}

async function loadFeed() {
    if (feedLoading) return;
    feedLoading = true;

    const data = await api(`/social/api/feed?page=${feedPage}&scope=${currentScope}`);

    document.getElementById('feed-skeleton').style.display = 'none';
    document.getElementById('feed-container').style.display = 'block';

    if (data && data.posts) {
        const container = document.getElementById('feed-container');

        if (feedPage === 1 && data.posts.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">📰</div>
                    <h3>${currentScope === 'department' ? 'No department posts yet' : 'Your feed is empty'}</h3>
                    <p>${currentScope === 'department' ? 'Be the first to post in your department!' : 'Start posting or connect with others to see content here!'}</p>
                </div>
            `;
        } else {
            data.posts.forEach(post => {
                container.insertAdjacentHTML('beforeend', renderPost(post));
            });
        }

        if (data.has_more) {
            document.getElementById('load-more').style.display = 'block';
        } else {
            document.getElementById('load-more').style.display = 'none';
        }
    }

    feedLoading = false;
}

function loadMore() {
    feedPage++;
    loadFeed();
}

function renderPost(post) {
    const content = post.content.replace(/#(\w+)/g, '<span class="hashtag">#$1</span>');
    const scopeBadge = post.scope === 'department' && post.department
        ? `<span class="badge badge-info" style="font-size:9px;margin-left:4px;">${post.department}</span>`
        : '';
    return `
        <div class="post-card" id="post-${post.id}">
            <div class="post-header">
                <div class="user-avatar">${post.avatar_letter}</div>
                <div class="post-meta">
                    <div class="post-author">
                        <a href="/profile/${post.author_id}" style="color:var(--text-primary)">${post.author_name || post.author}</a>
                        <span class="badge role-badge-${post.author_role}" style="font-size:10px; margin-left:6px;">${post.author_role}</span>
                        ${scopeBadge}
                    </div>
                    <div class="post-details">
                        ${post.author_title ? `<span>${post.author_title}</span> ·` : ''}
                        <span>${timeAgoIST(post.created_at)}</span>
                    </div>
                </div>
            </div>
            <div class="post-content">${content}</div>
            <div class="post-actions">
                <button class="post-action ${post.liked ? 'liked' : ''}" onclick="toggleLike(${post.id}, this)">
                    <span class="action-icon">${post.liked ? '❤️' : '🤍'}</span>
                    <span class="action-count">${post.like_count}</span>
                </button>
                <button class="post-action" onclick="toggleComments(${post.id})">
                    <span class="action-icon">💬</span>
                    <span>${post.comment_count}</span>
                </button>
            </div>
            <div class="comments-section" id="comments-${post.id}" style="display:none;">
                <div id="comments-list-${post.id}"></div>
                <div class="comment-input">
                    <input type="text" id="comment-input-${post.id}" placeholder="Write a comment..." onkeypress="if(event.key==='Enter')addComment(${post.id})">
                    <button class="btn btn-sm btn-primary" onclick="addComment(${post.id})">Send</button>
                </div>
            </div>
        </div>
    `;
}

async function createPost() {
    const textarea = document.getElementById('post-content');
    const content = textarea.value.trim();
    if (!content) return;

    const scopeSelect = document.getElementById('post-scope');
    const scope = scopeSelect ? scopeSelect.value : 'global';

    const data = await api('/social/api/posts', {
        method: 'POST',
        body: JSON.stringify({ content, scope })
    });

    if (data) {
        textarea.value = '';
        const container = document.getElementById('feed-container');
        container.insertAdjacentHTML('afterbegin', renderPost(data));
        showToast('Post published!', 'success');
    }
}

async function toggleLike(postId, btn) {
    const data = await api(`/social/api/posts/${postId}/like`, { method: 'POST' });
    if (data) {
        const icon = btn.querySelector('.action-icon');
        const count = btn.querySelector('.action-count');
        icon.textContent = data.liked ? '❤️' : '🤍';
        count.textContent = data.count;
        btn.classList.toggle('liked', data.liked);
    }
}

async function toggleComments(postId) {
    const section = document.getElementById(`comments-${postId}`);
    if (section.style.display === 'none') {
        section.style.display = 'block';
        loadComments(postId);
    } else {
        section.style.display = 'none';
    }
}

async function loadComments(postId) {
    const data = await api(`/social/api/posts/${postId}/comments`);
    const list = document.getElementById(`comments-list-${postId}`);
    if (data) {
        list.innerHTML = data.map(c => `
            <div class="comment-item">
                <div class="user-avatar">${c.avatar}</div>
                <div class="comment-body">
                    <div class="comment-author">${c.author}</div>
                    <div class="comment-text">${c.content}</div>
                    <div class="comment-time">${timeAgoIST(c.created_at)}</div>
                </div>
            </div>
        `).join('');
    }
}

async function addComment(postId) {
    const input = document.getElementById(`comment-input-${postId}`);
    const content = input.value.trim();
    if (!content) return;

    const data = await api(`/social/api/posts/${postId}/comment`, {
        method: 'POST',
        body: JSON.stringify({ content })
    });

    if (data) {
        input.value = '';
        loadComments(postId);
    }
}
