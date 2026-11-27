/**
 * ui.js — comportamentos visuais compartilhados (design system "Brasa").
 *
 * Somente melhorias progressivas de interface: menu móvel, cabeçalho ao rolar,
 * índice de seções, destaque de valores que mudam e preenchimento de sliders.
 * Não altera dados, regras de negócio nem chamadas de API.
 */
(function () {
    "use strict";

    const root = document.documentElement;
    root.classList.add("js");

    const reduzirMovimento = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function iniciarCabecalho() {
        const header = document.querySelector(".site-header");
        if (!header) return;
        const atualizar = () => header.classList.toggle("is-scrolled", window.scrollY > 8);
        atualizar();
        window.addEventListener("scroll", atualizar, { passive: true });
    }

    function iniciarMenuMovel() {
        document.querySelectorAll("[data-nav-toggle]").forEach((botao) => {
            const alvo = document.getElementById(botao.getAttribute("aria-controls"));
            if (!alvo) return;
            const fechar = () => {
                botao.setAttribute("aria-expanded", "false");
                alvo.classList.remove("is-open");
            };
            botao.addEventListener("click", () => {
                const aberto = botao.getAttribute("aria-expanded") === "true";
                botao.setAttribute("aria-expanded", String(!aberto));
                alvo.classList.toggle("is-open", !aberto);
                if (!aberto) alvo.querySelector("a, button")?.focus({ preventScroll: true });
            });
            alvo.addEventListener("click", (evento) => {
                if (evento.target.closest("a")) fechar();
            });
            document.addEventListener("keydown", (evento) => {
                if (evento.key === "Escape" && botao.getAttribute("aria-expanded") === "true") {
                    fechar();
                    botao.focus();
                }
            });
            document.addEventListener("click", (evento) => {
                if (!alvo.contains(evento.target) && !botao.contains(evento.target)) fechar();
            });
            window.matchMedia("(min-width: 901px)").addEventListener?.("change", fechar);
        });
    }

    function marcarPaginaAtual() {
        const atual = location.pathname.split("/").pop() || "index.html";
        document.querySelectorAll(".site-nav > a, .app-nav > a").forEach((link) => {
            if (link.hasAttribute("aria-current")) return;
            const destino = (link.getAttribute("href") || "").split("#")[0].split("?")[0];
            if (destino && destino === atual) link.setAttribute("aria-current", "page");
        });
    }

    function iniciarIndiceSecoes() {
        const indice = document.querySelector("[data-section-index]");
        if (!indice || !("IntersectionObserver" in window)) return;
        const links = [...indice.querySelectorAll('a[href^="#"]')];
        const alvos = links
            .map((link) => document.getElementById(decodeURIComponent(link.hash.slice(1))))
            .filter(Boolean);
        if (!alvos.length) return;
        const visiveis = new Map();
        const ativar = (id) => {
            links.forEach((link) => {
                const ativo = link.hash.slice(1) === id;
                if (ativo) {
                    link.setAttribute("aria-current", "true");
                    if (indice.scrollWidth > indice.clientWidth) {
                        indice.scrollTo({
                            left: link.offsetLeft - indice.clientWidth / 2 + link.clientWidth / 2,
                            behavior: reduzirMovimento() ? "auto" : "smooth",
                        });
                    }
                } else {
                    link.removeAttribute("aria-current");
                }
            });
        };
        const observador = new IntersectionObserver((entradas) => {
            entradas.forEach((entrada) => visiveis.set(entrada.target.id, entrada.isIntersecting ? entrada.intersectionRatio : 0));
            const primeiro = alvos.find((alvo) => (visiveis.get(alvo.id) || 0) > 0 && !alvo.hidden && alvo.offsetParent !== null);
            if (primeiro) ativar(primeiro.id);
        }, { rootMargin: "-120px 0px -55% 0px", threshold: [0, 0.01, 0.5] });
        alvos.forEach((alvo) => observador.observe(alvo));

        // Seções ocultas por permissão não aparecem no índice.
        const sincronizarVisibilidade = () => {
            links.forEach((link) => {
                const alvo = document.getElementById(decodeURIComponent(link.hash.slice(1)));
                const oculto = !alvo || alvo.hidden || alvo.closest("[hidden]") !== null || getComputedStyle(alvo).display === "none";
                // Só grava quando muda: reescrever o mesmo atributo gera outra
                // mutação e prenderia o observador em um laço infinito.
                if (link.hidden !== oculto) link.hidden = oculto;
            });
        };
        sincronizarVisibilidade();
        new MutationObserver(sincronizarVisibilidade).observe(document.body, {
            subtree: true,
            attributes: true,
            attributeFilter: ["hidden", "style"],
        });
    }

    function iniciarValoresVivos() {
        const elementos = document.querySelectorAll("[data-live]");
        if (!elementos.length || !("MutationObserver" in window)) return;
        elementos.forEach((elemento) => {
            let anterior = elemento.textContent;
            const observador = new MutationObserver(() => {
                const atual = elemento.textContent;
                if (atual === anterior) return;
                anterior = atual;
                if (reduzirMovimento()) return;
                elemento.classList.remove("is-updated");
                void elemento.offsetWidth;
                elemento.classList.add("is-updated");
            });
            observador.observe(elemento, { childList: true, characterData: true, subtree: true });
            elemento.addEventListener("animationend", () => elemento.classList.remove("is-updated"));
        });
    }

    function preencherSlider(input) {
        const min = Number(input.min || 0);
        const max = Number(input.max || 100);
        const valor = Number(input.value);
        const pct = max > min ? ((valor - min) / (max - min)) * 100 : 0;
        input.style.setProperty("--range-progress", `${Math.min(100, Math.max(0, pct))}%`);
    }

    function iniciarSliders() {
        document.querySelectorAll('input[type="range"]').forEach((input) => {
            preencherSlider(input);
            input.addEventListener("input", () => preencherSlider(input));
            new MutationObserver(() => preencherSlider(input)).observe(input, { attributes: true, attributeFilter: ["value"] });
        });
    }

    // Avisos flutuantes ([data-toast]): aparecem quando o texto muda e se
    // recolhem depois de alguns segundos. O texto continua no elemento, então
    // leitores de tela e testes seguem encontrando a mensagem.
    function iniciarAvisosFlutuantes() {
        const avisos = document.querySelectorAll("[data-toast]");
        if (!avisos.length || !("MutationObserver" in window)) return;
        avisos.forEach((aviso) => {
            let timer = 0;
            const recolher = () => aviso.classList.add("is-dismissed");
            const agendar = () => {
                window.clearTimeout(timer);
                aviso.classList.remove("is-dismissed");
                const texto = aviso.textContent.trim();
                if (!texto) return;
                timer = window.setTimeout(recolher, Math.min(15000, Math.max(6000, texto.length * 70)));
            };
            new MutationObserver(agendar).observe(aviso, { childList: true, characterData: true, subtree: true });
            aviso.addEventListener("mouseenter", () => window.clearTimeout(timer));
            aviso.addEventListener("mouseleave", () => {
                if (!aviso.classList.contains("is-dismissed")) timer = window.setTimeout(recolher, 3000);
            });
            aviso.addEventListener("click", recolher);
        });
    }

    function iniciar() {
        try { iniciarCabecalho(); } catch { /* interface opcional */ }
        try { iniciarMenuMovel(); } catch { /* interface opcional */ }
        try { marcarPaginaAtual(); } catch { /* interface opcional */ }
        try { iniciarIndiceSecoes(); } catch { /* interface opcional */ }
        try { iniciarValoresVivos(); } catch { /* interface opcional */ }
        try { iniciarSliders(); } catch { /* interface opcional */ }
        try { iniciarAvisosFlutuantes(); } catch { /* interface opcional */ }
    }

    window.ChurrasPlanUI = { preencherSlider };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", iniciar);
    } else {
        iniciar();
    }
})();
