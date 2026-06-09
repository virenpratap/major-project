/* ════════ AUTOCOMPLETE / TYPEAHEAD ════════ */

class Autocomplete {
    constructor(inputElement, options = {}) {
        this.input = inputElement;
        this.type = options.type || 'skill';
        this.onSelect = options.onSelect || (() => {});
        this.cache = {};
        this.dropdown = null;

        this.init();
    }

    init() {
        // Create dropdown
        this.dropdown = document.createElement('div');
        this.dropdown.className = 'dropdown-menu';
        this.dropdown.style.cssText = 'position:absolute;top:100%;left:0;width:100%;z-index:100;';
        this.input.parentElement.style.position = 'relative';
        this.input.parentElement.appendChild(this.dropdown);

        // Debounced input handler
        this.input.addEventListener('input', debounce((e) => {
            this.search(e.target.value.trim());
        }, 300));

        // Close on outside click
        document.addEventListener('click', (e) => {
            if (!this.input.parentElement.contains(e.target)) {
                this.dropdown.style.display = 'none';
            }
        });
    }

    async search(query) {
        if (query.length < 1) {
            this.dropdown.style.display = 'none';
            return;
        }

        // Check cache
        const cacheKey = `${this.type}:${query}`;
        if (this.cache[cacheKey]) {
            this.render(this.cache[cacheKey]);
            return;
        }

        const data = await api(`/api/suggest?q=${encodeURIComponent(query)}&type=${this.type}`);
        if (data) {
            this.cache[cacheKey] = data;
            this.render(data);
        }
    }

    render(suggestions) {
        if (!suggestions.length) {
            this.dropdown.style.display = 'none';
            return;
        }

        this.dropdown.innerHTML = suggestions.map(s => `
            <div class="dropdown-item" style="cursor:pointer" data-name="${s.name}">
                ${s.name} <span style="font-size:11px;color:var(--text-muted);">(${s.usage_count})</span>
            </div>
        `).join('');

        this.dropdown.querySelectorAll('.dropdown-item').forEach(item => {
            item.addEventListener('click', () => {
                const name = item.dataset.name;
                this.input.value = name;
                this.dropdown.style.display = 'none';
                this.onSelect(name);
            });
        });

        this.dropdown.style.display = 'block';
    }
}

// Auto-init autocomplete on elements with data-autocomplete
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-autocomplete]').forEach(input => {
        new Autocomplete(input, { type: input.dataset.autocomplete });
    });
});
