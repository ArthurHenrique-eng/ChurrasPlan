(() => {
    let deferredPrompt = null;

    function ensureStatus() {
        let el = document.getElementById("connection-status");
        if (!el) {
            el = document.createElement("div");
            el.id = "connection-status";
            el.className = "connection-status";
            el.setAttribute("role", "status");
            el.setAttribute("aria-live", "polite");
            document.body.appendChild(el);
        }
        return el;
    }

    function renderNetwork() {
        const el = ensureStatus();
        if (navigator.onLine) {
            el.classList.remove("is-visible");
            el.textContent = "";
        } else {
            el.textContent = "Sem internet. Dados locais continuam disponíveis; ações online aguardam conexão.";
            el.classList.add("is-visible");
        }
    }

    function addInstallButton() {
        if (!deferredPrompt || document.getElementById("pwa-install")) return;
        const button = document.createElement("button");
        button.id = "pwa-install";
        button.className = "pwa-install";
        button.type = "button";
        button.textContent = "Instalar ChurrasPlan";
        button.addEventListener("click", async () => {
            const prompt = deferredPrompt;
            deferredPrompt = null;
            button.remove();
            await prompt.prompt();
        });
        document.body.appendChild(button);
    }

    if ("serviceWorker" in navigator && location.protocol !== "file:") {
        window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
    }
    window.addEventListener("beforeinstallprompt", (event) => { event.preventDefault(); deferredPrompt = event; addInstallButton(); });
    window.addEventListener("appinstalled", () => { deferredPrompt = null; document.getElementById("pwa-install")?.remove(); });
    window.addEventListener("online", renderNetwork);
    window.addEventListener("offline", renderNetwork);
    document.addEventListener("DOMContentLoaded", renderNetwork);
})();
