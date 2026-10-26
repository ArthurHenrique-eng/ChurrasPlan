(function () {
    "use strict";

    if (window.va) return;

    window.va = function () {
        (window.vaq = window.vaq || []).push(arguments);
    };

    const script = document.createElement("script");
    script.defer = true;
    script.src = "/_vercel/insights/script.js";

    script.onerror = function () {
        console.warn("Vercel Analytics não foi carregado.");
    };

    document.head.appendChild(script);
})();