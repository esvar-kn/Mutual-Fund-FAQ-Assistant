/* ==========================================================================
   FundFacts — UI controller
   --------------------------------------------------------------------------
   Two rules hold throughout this file:

   1. Message content is NEVER assigned via innerHTML. Answer text derives from
      third-party scraped HTML, so interpolating it into markup would turn a
      poisoned source page into stored XSS. Everything goes through textContent.

   2. Each in-flight question owns its own placeholder element, and the reply
      REPLACES that placeholder. Appending replies to the end of the list made
      answers attach to the wrong question whenever two requests overlapped.
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {

    /* ------------------------------------------------------------ Config */

    // Mirrors config/schemes.json. Ideally the backend would expose these via a
    // /api/schemes endpoint so there is a single source of truth; until then,
    // update this list when you add a scheme to config/schemes.json.
    const SCHEMES = [
        {
            amc: 'HDFC Mutual Fund',
            funds: [
                'HDFC Mid-Cap Opportunities Fund',
                'HDFC Small Cap Fund',
                'HDFC Gold ETF Fund of Fund',
                'HDFC Multi Cap Fund',
                'HDFC Large Cap Fund'
            ]
        },
        {
            amc: 'SBI Mutual Fund',
            funds: [
                'SBI Magnum Multiplier Fund',
                'SBI Small & Midcap Fund',
                'SBI Pharma Fund',
                'SBI Gold Fund'
            ]
        }
    ];

    const QUICK_PROMPTS = [
        { icon: 'payments',    title: 'Exit load',     hint: 'HDFC Mid-Cap Opportunities',
          prompt: 'What is the exit load for HDFC Mid-Cap Opportunities Fund?' },
        { icon: 'percent',     title: 'Expense ratio', hint: 'HDFC Small Cap Fund',
          prompt: 'Tell me the expense ratio of HDFC Small Cap Fund.' },
        { icon: 'query_stats', title: 'Benchmark',     hint: 'HDFC Gold ETF FoF',
          prompt: 'What is the benchmark for the HDFC Gold ETF Fund of Fund?' }
    ];

    // Maps every status the API can return to its colour role, icon and label.
    // Adding a backend status means adding one row here — nothing else.
    const STATES = {
        success:           { kind: 'verified', icon: 'verified',       label: 'Verified answer' },
        blocked_advisory:  { kind: 'advisory', icon: 'balance',        label: 'Advice not permitted' },
        blocked_pii:       { kind: 'security', icon: 'shield_lock',    label: 'Personal data blocked' },
        no_context:        { kind: 'scope',    icon: 'travel_explore', label: 'Outside indexed documents' },
        failed_validation: { kind: 'scope',    icon: 'rule',           label: 'Could not verify source' },
        rate_limited:      { kind: 'system',   icon: 'hourglass_top',  label: 'Too many requests' },
        retrieval_error:   { kind: 'system',   icon: 'cloud_off',      label: 'Service unavailable' },
        llm_error:         { kind: 'system',   icon: 'cloud_off',      label: 'Service unavailable' },
        client_error:      { kind: 'system',   icon: 'wifi_off',       label: 'Connection problem' }
    };
    const FALLBACK_STATE = STATES.client_error;

    /* --------------------------------------------------------- Elements */

    const app          = document.getElementById('app');
    const sidebar      = document.getElementById('sidebar');
    const scrim        = document.getElementById('scrim');
    const sidebarBtn   = document.getElementById('sidebar-toggle');
    const form         = document.getElementById('chat-query-form');
    const input        = document.getElementById('user-input');
    const sendBtn      = document.getElementById('send-btn');
    const chatScroll   = document.getElementById('chat-container');
    const chatHistory  = document.getElementById('chat-history');
    const welcome      = document.getElementById('welcome-state');
    const apiInput     = document.getElementById('api-url-input');
    const statusEl     = document.getElementById('status');
    const statusText   = document.getElementById('status-text');
    const themeToggle  = document.getElementById('theme-toggle');
    const themeIcon    = document.getElementById('theme-icon');
    const settingsBtn  = document.getElementById('settings-toggle-btn');
    const settingsPop  = document.getElementById('settings-popover');
    const promptGrid   = document.getElementById('prompt-grid');
    const schemeGroups = document.getElementById('scheme-groups');

    /* ---------------------------------------------------- DOM utilities */

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined && text !== null) node.textContent = text;
        return node;
    }

    function icon(name, className, filled) {
        const node = el('span', 'material-symbols-outlined' + (className ? ' ' + className : ''), name);
        if (filled) node.classList.add('icon-filled');
        return node;
    }

    // Only http(s) links become anchors, so a "javascript:" or "data:" URL
    // smuggled into the source field cannot become a clickable payload.
    function safeHttpUrl(value) {
        if (!value || value === 'N/A') return null;
        try {
            const parsed = new URL(value, window.location.href);
            return (parsed.protocol === 'http:' || parsed.protocol === 'https:') ? parsed.href : null;
        } catch (e) {
            return null;
        }
    }

    /* ------------------------------------------------------ Theme toggle */

    function applyTheme(theme) {
        document.documentElement.className = theme;
        localStorage.setItem('theme', theme);
        // Icon shows the action, not the current state.
        themeIcon.textContent = theme === 'dark' ? 'light_mode' : 'dark_mode';
        themeToggle.setAttribute('aria-label',
            theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
    }
    applyTheme(document.documentElement.className === 'dark' ? 'dark' : 'light');

    themeToggle.addEventListener('click', () => {
        applyTheme(document.documentElement.className === 'dark' ? 'light' : 'dark');
    });

    /* ----------------------------------------------------- Mobile drawer */

    function setNav(open) {
        app.classList.toggle('nav-open', open);
        sidebarBtn.setAttribute('aria-expanded', String(open));
    }
    sidebarBtn.addEventListener('click', () => setNav(!app.classList.contains('nav-open')));
    scrim.addEventListener('click', () => setNav(false));
    sidebar.addEventListener('click', (e) => {
        if (e.target.closest('a')) setNav(false);
    });

    /* -------------------------------------------------- Sidebar schemes */

    SCHEMES.forEach((group, index) => {
        const details = el('details', 'amc');
        if (index === 0) details.open = true;

        const summary = el('summary');
        summary.appendChild(el('span', null, group.amc));
        summary.appendChild(el('span', 'amc-count', String(group.funds.length)));
        summary.appendChild(icon('expand_more'));
        details.appendChild(summary);

        const list = el('ul', 'scheme-list');
        group.funds.forEach(name => list.appendChild(el('li', 'scheme', name)));
        details.appendChild(list);

        schemeGroups.appendChild(details);
    });

    /* --------------------------------------------------- Quick prompts */

    const promptButtons = QUICK_PROMPTS.map(item => {
        const btn = el('button', 'prompt-card');
        btn.type = 'button';
        btn.appendChild(icon(item.icon));
        btn.appendChild(el('span', 'prompt-title', item.title));
        btn.appendChild(el('span', 'prompt-hint', item.hint));
        btn.addEventListener('click', () => {
            input.value = item.prompt;
            handleSend();
        });
        promptGrid.appendChild(btn);
        return btn;
    });

    /* --------------------------------------------------- Backend status */

    let backendUrl = localStorage.getItem('mf_rag_backend_url');
    if (backendUrl === null) {
        const local = ['localhost', '127.0.0.1'].includes(window.location.hostname);
        backendUrl = local ? 'http://localhost:8080' : '';
    }
    apiInput.value = backendUrl;

    function setStatus(state, text) {
        statusEl.setAttribute('data-state', state);
        statusText.textContent = text;
    }

    async function verifyBackendStatus() {
        if (!backendUrl) {
            setStatus('offline', 'Not configured');
            return;
        }
        setStatus('pending', 'Connecting…');
        try {
            const res = await fetch(`${backendUrl}/health`, { method: 'GET', mode: 'cors' });
            setStatus(res.ok ? 'online' : 'offline', res.ok ? 'Online' : 'Backend error');
        } catch (e) {
            setStatus('offline', 'Unreachable');
        }
    }

    let statusDebounce;
    apiInput.addEventListener('input', (e) => {
        backendUrl = e.target.value.trim().replace(/\/+$/, '');
        localStorage.setItem('mf_rag_backend_url', backendUrl);
        clearTimeout(statusDebounce);
        statusDebounce = setTimeout(verifyBackendStatus, 400);
    });

    verifyBackendStatus();

    /* ------------------------------------------------ Settings popover */

    function setSettings(open) {
        settingsPop.hidden = !open;
        settingsBtn.setAttribute('aria-expanded', String(open));
    }
    settingsBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        setSettings(settingsPop.hidden);
    });
    document.addEventListener('click', (e) => {
        if (!settingsPop.hidden && !settingsPop.contains(e.target) && !settingsBtn.contains(e.target)) {
            setSettings(false);
        }
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') { setSettings(false); setNav(false); }
    });

    /* ----------------------------------------------------- Message bits */

    function userBubble(text) {
        const row = el('div', 'msg msg--user fade-in');
        row.appendChild(el('div', 'bubble-user', text));
        return row;
    }

    function citation(sourceUrl) {
        const href = safeHttpUrl(sourceUrl);
        if (!href) {
            const span = el('span', 'cite');
            span.appendChild(icon('description'));
            span.appendChild(el('span', 'cite-url', 'No source document'));
            return span;
        }
        const link = el('a', 'cite');
        link.href = href;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';   // deny the opened tab access to window.opener
        link.appendChild(icon('link'));
        link.appendChild(el('span', 'cite-url', href.replace(/^https?:\/\/(www\.)?/, '')));
        return link;
    }

    // One card shape for every response; only the colour role and label change.
    function botCard(text, status, sourceUrl) {
        const state = STATES[status] || FALLBACK_STATE;
        const row = el('div', `msg msg--${state.kind} fade-in`);
        const card = el('div', 'card-bot');

        const head = el('div', 'card-head');
        head.appendChild(icon(state.icon, null, true));
        head.appendChild(el('span', 'card-label', state.label));
        card.appendChild(head);

        card.appendChild(el('div', 'card-body', text));

        // A citation footer only makes sense for an answer drawn from a document.
        if (state.kind === 'verified') {
            const foot = el('div', 'card-foot');
            foot.appendChild(citation(sourceUrl));
            foot.appendChild(el('span', 'timestamp',
                new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })));
            card.appendChild(foot);
        }

        row.appendChild(card);
        return row;
    }

    function loadingCard() {
        const row = el('div', 'msg fade-in');
        const card = el('div', 'card-bot');
        const dots = el('div', 'typing');
        dots.appendChild(el('span'));
        dots.appendChild(el('span'));
        dots.appendChild(el('span'));
        card.appendChild(dots);
        row.appendChild(card);
        return row;
    }

    function scrollToBottom() {
        chatScroll.scrollTo({ top: chatScroll.scrollHeight, behavior: 'smooth' });
    }

    /* ------------------------------------------------------ Send flow */

    let inFlight = 0;

    function setBusy(busy) {
        input.disabled = busy;
        sendBtn.disabled = busy;
        // The quick-prompt buttons used to stay live while a request was in
        // flight, which let a second question start and land out of order.
        promptButtons.forEach(b => { b.disabled = busy; });
        if (!busy) input.focus();
    }

    async function handleSend() {
        const query = input.value.trim();
        if (!query || inFlight > 0) return;

        input.value = '';
        welcome.hidden = true;

        chatHistory.appendChild(userBubble(query));

        // This question's reserved slot. The answer replaces THIS node, so it
        // can never be rendered underneath somebody else's question.
        const slot = loadingCard();
        chatHistory.appendChild(slot);
        scrollToBottom();

        inFlight += 1;
        setBusy(true);

        const settle = (node) => {
            slot.replaceWith(node);
            scrollToBottom();
        };

        try {
            if (!backendUrl) {
                throw new Error('No backend URL configured. Open settings (gear icon) and enter one.');
            }

            const res = await fetch(`${backendUrl}/api/query`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                mode: 'cors',
                body: JSON.stringify({ query })
            });

            if (res.ok) {
                const data = await res.json();
                settle(botCard(data.answer, data.status, data.source));
            } else if (res.status === 429) {
                const data = await res.json().catch(() => null);
                settle(botCard(
                    (data && data.answer) || 'Too many requests. Please wait a moment and try again.',
                    'rate_limited'));
            } else if (res.status === 422) {
                settle(botCard(
                    'That question could not be processed. Please keep it under 500 characters.',
                    'client_error'));
            } else {
                settle(botCard(
                    'The service is unavailable right now. Please consult the official AMC website.',
                    'retrieval_error'));
            }
        } catch (error) {
            settle(botCard(
                error.message || 'Could not reach the backend API.',
                'client_error'));
        } finally {
            inFlight -= 1;
            setBusy(false);
        }
    }

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        handleSend();
    });
});
