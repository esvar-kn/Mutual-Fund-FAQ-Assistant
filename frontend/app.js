document.addEventListener("DOMContentLoaded", () => {
    // Select DOM elements
    const queryForm = document.getElementById("chat-query-form");
    const userInput = document.getElementById("user-input");
    const chatContainer = document.getElementById("chat-container");
    const chatHistory = document.getElementById("chat-history");
    const welcomeState = document.getElementById("welcome-state");
    const apiInput = document.getElementById("api-url-input");
    const statusDot = document.querySelector(".status-indicator-dot");
    const statusText = document.querySelector(".status-indicator-text");
    const sendBtn = document.getElementById("send-btn");
    const themeIcon = document.getElementById("theme-icon");

    // Initialize Theme preferred state
    const currentTheme = localStorage.getItem("theme") || "light";
    if (currentTheme === "dark") {
        document.documentElement.classList.add("dark");
        document.documentElement.classList.remove("light");
        if (themeIcon) themeIcon.textContent = "dark_mode";
    } else {
        document.documentElement.classList.add("light");
        document.documentElement.classList.remove("dark");
        if (themeIcon) themeIcon.textContent = "light_mode";
    }

    // Theme toggler function exposed globally for HTML onclick
    window.toggleTheme = function() {
        const html = document.documentElement;
        if (html.classList.contains("dark")) {
            html.classList.remove("dark");
            html.classList.add("light");
            themeIcon.textContent = "light_mode";
            localStorage.setItem("theme", "light");
        } else {
            html.classList.remove("light");
            html.classList.add("dark");
            themeIcon.textContent = "dark_mode";
            localStorage.setItem("theme", "dark");
        }
    };

    // Connection configuration settings
    let backendUrl = localStorage.getItem("mf_rag_backend_url");
    if (!backendUrl) {
        backendUrl = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
            ? "http://localhost:8080"
            : "";
    }
    apiInput.value = backendUrl;

    // Listen connection configuration changes
    apiInput.addEventListener("input", (e) => {
        backendUrl = e.target.value.trim().replace(/\/$/, "");
        localStorage.setItem("mf_rag_backend_url", backendUrl);
        verifyBackendStatus();
    });

    // Check backend connection health
    async function verifyBackendStatus() {
        if (!backendUrl) {
            statusDot.className = "w-2 h-2 rounded-full bg-error-container status-indicator-dot";
            statusText.textContent = "Offline (Configure URL)";
            return;
        }

        statusText.textContent = "Connecting...";
        try {
            const res = await fetch(`${backendUrl}/health`, { method: "GET", mode: "cors" });
            if (res.ok) {
                statusDot.className = "w-2 h-2 rounded-full bg-primary-container status-indicator-dot pulse-badge";
                statusText.textContent = "System Online";
            } else {
                statusDot.className = "w-2 h-2 rounded-full bg-error-container status-indicator-dot";
                statusText.textContent = "Offline (API Error)";
            }
        } catch (e) {
            statusDot.className = "w-2 h-2 rounded-full bg-error-container status-indicator-dot";
            statusText.textContent = "Offline (Unreachable)";
        }
    }

    verifyBackendStatus();

    // Toggle Connection Settings Popover
    const settingsToggleBtn = document.getElementById("settings-toggle-btn");
    const settingsPopover = document.getElementById("settings-popover");

    if (settingsToggleBtn && settingsPopover) {
        settingsToggleBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            settingsPopover.classList.toggle("hidden");
        });

        // Hide settings popover when clicking outside of it
        document.addEventListener("click", (e) => {
            if (!settingsPopover.contains(e.target) && !settingsToggleBtn.contains(e.target)) {
                settingsPopover.classList.add("hidden");
            }
        });
    }

    // Scheme Filtering is disabled for now (passive tracking list only)
    let activeSchemeFilter = null;

    // Binds suggestions button click prompt
    const suggestionBtns = document.querySelectorAll(".quick-prompt-btn");
    suggestionBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const promptText = btn.getAttribute("data-prompt");
            userInput.value = promptText;
            handleSend();
        });
    });

    // Form query submit handler
    queryForm.addEventListener("submit", (e) => {
        e.preventDefault();
        handleSend();
    });

    // Create custom bubble element based on message type
    function createMessageBubble(content, isUser = false, type = 'normal', sourceUrl = 'N/A') {
        const wrapper = document.createElement('div');
        wrapper.className = `flex ${isUser ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-4 duration-300`;
        
        if (isUser) {
            wrapper.innerHTML = `
                <div class="max-w-[80%] bg-[#1C2541] dark:bg-primary-container text-white dark:text-on-primary-container p-4 rounded-2xl rounded-tr-none shadow-md">
                    <p class="text-body-md">${content}</p>
                </div>
            `;
        } else {
            if (type === 'refusal') {
                wrapper.innerHTML = `
                    <div class="max-w-[85%] bg-error-container/20 border border-error/20 p-5 rounded-2xl rounded-tl-none shadow-sm flex gap-4">
                        <span class="material-symbols-outlined text-error" style="font-variation-settings: 'FILL' 1;">warning</span>
                        <div class="flex flex-col gap-2">
                            <p class="text-on-error-container font-label-bold">Access Restricted</p>
                            <p class="text-on-error-container/80 text-body-md">${content}</p>
                        </div>
                    </div>
                `;
            } else if (type === 'security') {
                wrapper.innerHTML = `
                    <div class="max-w-[85%] bg-error-container/40 border border-error p-5 rounded-2xl rounded-tl-none shadow-md flex gap-4">
                        <span class="material-symbols-outlined text-error" style="font-variation-settings: 'FILL' 1;">security</span>
                        <div class="flex flex-col gap-2">
                            <p class="text-on-error-container font-label-bold">Security Alert</p>
                            <p class="text-on-error-container/80 text-body-md">${content}</p>
                        </div>
                    </div>
                `;
            } else {
                // Normal factual RAG response layout with metadata & citation source
                const today = new Date().toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
                const citationPill = sourceUrl && sourceUrl !== 'N/A' 
                    ? `
                    <div class="flex items-center gap-2 px-3 py-1 bg-surface-container-high dark:bg-slate-700 rounded-full max-w-[280px] sm:max-w-md overflow-hidden">
                        <span class="material-symbols-outlined text-[14px] text-on-surface-variant dark:text-gray-300">link</span>
                        <a href="${sourceUrl}" target="_blank" class="text-[11px] font-label-bold uppercase tracking-wider text-on-surface-variant dark:text-gray-300 hover:text-primary dark:hover:text-primary-container truncate">Source: ${sourceUrl}</a>
                    </div>
                    `
                    : `
                    <div class="flex items-center gap-2 px-3 py-1 bg-surface-container-high dark:bg-slate-700 rounded-full">
                        <span class="material-symbols-outlined text-[14px] text-on-surface-variant dark:text-gray-300">link</span>
                        <span class="text-[11px] font-label-bold uppercase tracking-wider text-on-surface-variant dark:text-gray-300">Source: Verified PDF</span>
                    </div>
                    `;

                wrapper.innerHTML = `
                    <div class="max-w-[85%] bg-surface-container dark:bg-slate-800 border border-outline-variant dark:border-white/10 p-6 rounded-3xl rounded-tl-none shadow-sm flex flex-col gap-4">
                        <p class="text-on-surface dark:text-gray-100 text-body-md leading-relaxed">${content}</p>
                        <div class="pt-4 border-t border-outline-variant dark:border-white/10 flex flex-wrap justify-between items-center gap-3">
                            ${citationPill}
                            <span class="text-[11px] text-on-surface-variant/60 dark:text-gray-400 font-label-sm italic">Last updated: ${today}</span>
                        </div>
                    </div>
                `;
            }
        }
        return wrapper;
    }

    // Create typing bubble loader
    function appendLoader() {
        const loaderId = "loader_" + Date.now();
        const wrapper = document.createElement('div');
        wrapper.className = "flex justify-start animate-in fade-in duration-300";
        wrapper.setAttribute("id", loaderId);
        
        wrapper.innerHTML = `
            <div class="max-w-[85%] bg-surface-container dark:bg-slate-800 border border-outline-variant dark:border-white/10 p-4 rounded-3xl rounded-tl-none shadow-sm flex items-center gap-1.5">
                <span class="w-2 h-2 bg-on-surface-variant/40 dark:bg-white/40 rounded-full animate-bounce"></span>
                <span class="w-2 h-2 bg-on-surface-variant/40 dark:bg-white/40 rounded-full animate-bounce [animation-delay:0.2s]"></span>
                <span class="w-2 h-2 bg-on-surface-variant/40 dark:bg-white/40 rounded-full animate-bounce [animation-delay:0.4s]"></span>
            </div>
        `;
        
        chatHistory.appendChild(wrapper);
        scrollToBottom();
        return loaderId;
    }

    // Scroll chat area to bottom
    function scrollToBottom() {
        chatContainer.scrollTo({
            top: chatContainer.scrollHeight,
            behavior: "smooth"
        });
    }

    // Handles query dispatching
    async function handleSend() {
        const queryText = userInput.value.trim();
        if (!queryText) return;

        // Reset user query input
        userInput.value = "";

        // Hide welcome block
        if (welcomeState && !welcomeState.classList.contains("hidden")) {
            welcomeState.classList.add("hidden");
        }

        // 1. Render User Message
        chatHistory.appendChild(createMessageBubble(queryText, true));
        scrollToBottom();

        // 2. Render Loading dots
        const loaderId = appendLoader();

        // Disable input during transaction
        userInput.disabled = true;
        sendBtn.disabled = true;

        // 3. Dispatch RAG request
        try {
            if (!backendUrl) {
                throw new Error("RAG API connection URL is not configured. Please locate sidebar and enter target URL.");
            }

            const res = await fetch(`${backendUrl}/api/query`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                mode: "cors",
                body: JSON.stringify({
                    query: queryText,
                    scheme_filter: activeSchemeFilter
                })
            });

            // Dismiss loader
            const loader = document.getElementById(loaderId);
            if (loader) loader.remove();

            userInput.disabled = false;
            sendBtn.disabled = false;
            userInput.focus();

            if (res.ok) {
                const data = await res.json();
                
                // Switch output bubble formatting based on status triggers
                if (data.status === "blocked_pii") {
                    chatHistory.appendChild(createMessageBubble(data.answer, false, "security"));
                } else if (data.status === "blocked_advisory" || data.status === "failed_validation" || data.status === "no_context") {
                    chatHistory.appendChild(createMessageBubble(data.answer, false, "refusal"));
                } else {
                    chatHistory.appendChild(createMessageBubble(data.answer, false, "normal", data.source));
                }
            } else {
                chatHistory.appendChild(createMessageBubble("Our RAG services are currently busy. Please consult the official website: https://www.hdfcfund.com", false, "refusal", "https://www.hdfcfund.com"));
            }
        } catch (error) {
            // Dismiss loader
            const loader = document.getElementById(loaderId);
            if (loader) loader.remove();

            userInput.disabled = false;
            sendBtn.disabled = false;
            userInput.focus();

            chatHistory.appendChild(createMessageBubble(`Connection Error: ${error.message || "Failed to contact RAG backend API server."}`, false, "refusal"));
        }
        
        scrollToBottom();
    }
});
