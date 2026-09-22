/** Estado de autenticação baseado em sessão HttpOnly do backend. */
const ChurrasPlanAuth = (() => {
    let usuarioCache;
    let promessaUsuario;

    async function usuarioAtual(forcar = false) {
        if (!forcar && usuarioCache !== undefined) return usuarioCache;
        if (!forcar && promessaUsuario) return promessaUsuario;
        promessaUsuario = ChurrasPlanAPI.usuarioAtual()
            .then((usuario) => { usuarioCache = usuario; return usuario; })
            .catch((erro) => {
                if (erro.status === 401) { usuarioCache = null; return null; }
                throw erro;
            })
            .finally(() => { promessaUsuario = null; });
        return promessaUsuario;
    }

    function limparCache() { usuarioCache = undefined; }

    function destinoSeguro(valor, fallback = "minha-conta.html") {
        if (!valor) return fallback;
        try {
            const url = new URL(valor, window.location.href);
            if (url.origin !== window.location.origin || !url.pathname.endsWith(".html")) return fallback;
            return `${url.pathname.split("/").pop()}${url.search}${url.hash}`;
        } catch { return fallback; }
    }

    function urlLogin(next = window.location.pathname.split("/").pop() || "index.html") {
        return `login.html?next=${encodeURIComponent(destinoSeguro(next, "index.html"))}`;
    }

    async function vincularPlanejamentoAtual() {
        const usuario = await usuarioAtual();
        if (!usuario || typeof EstadoChurrasco === "undefined") return null;
        const estado = EstadoChurrasco.obter();
        if (!estado.churrasco_id || !estado.planejamento_id) return null;
        try {
            return await ChurrasPlanAPI.vincularChurrasco(estado.churrasco_id, estado.planejamento_id);
        } catch (erro) {
            if (![404, 409].includes(erro.status)) throw erro;
            return null;
        }
    }

    async function renderizarNavegacao() {
        let usuario = null;
        try { usuario = await usuarioAtual(); } catch { /* API fora do ar não deve quebrar o site */ }
        const slots = [...document.querySelectorAll("#auth-nav-slot, [data-auth-nav]")];
        if (!slots.length) return;
        slots.forEach((slot) => {
            if (usuario) {
                const inicial = escaparHTML((usuario.nome || "U").trim().charAt(0).toUpperCase());
                slot.innerHTML = `<a class="account-chip" href="minha-conta.html" title="Minha conta"><span class="account-chip__avatar">${inicial}</span><span>${escaparHTML(usuario.nome.split(" ")[0])}</span></a>`;
            } else {
                slot.innerHTML = `<a class="account-chip account-chip--guest" href="${urlLogin()}">Entrar</a>`;
            }
        });
    }

    return { usuarioAtual, limparCache, destinoSeguro, urlLogin, vincularPlanejamentoAtual, renderizarNavegacao };
})();

document.addEventListener("DOMContentLoaded", () => ChurrasPlanAuth.renderizarNavegacao());
