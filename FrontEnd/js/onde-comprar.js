let posicaoAtual = null;
let modoAtual = "equilibrio";
let churrascoMapaId = null;
let mapaGoogle = null;
let googleMapId = null;
let marcadores = [];
const visualizacoesRegistradas = new Set();

function estrelas(e) {
    return e.avaliacao == null
        ? "sem avaliação"
        : `${Number(e.avaliacao).toFixed(1)} ★${e.quantidade_avaliacoes ? ` (${e.quantidade_avaliacoes})` : ""}`;
}

function tipoLoja(tipo) {
    return String(tipo || "estabelecimento").replace(/_/g, " ");
}

function carregarGoogleMaps(chave, mapId = null) {
    if (!chave || window.google?.maps) {
        return Promise.resolve(Boolean(window.google?.maps));
    }

    return new Promise((resolve) => {
        const cb = `churrasMapReady_${Date.now()}`;
        let finalizado = false;
        const concluir = (ok) => {
            if (finalizado) return;
            finalizado = true;
            delete window[cb];
            resolve(ok);
        };

        window[cb] = () => concluir(true);
        const s = document.createElement("script");
        const params = new URLSearchParams({
            key: chave,
            callback: cb,
            v: "weekly",
            libraries: "marker",
            language: "pt-BR",
            region: "BR",
            loading: "async",
            auth_referrer_policy: "origin",
        });
        if (mapId) params.set("map_ids", mapId);
        s.src = `https://maps.googleapis.com/maps/api/js?${params.toString()}`;
        s.async = true;
        s.defer = true;
        s.onerror = () => concluir(false);
        document.head.appendChild(s);
    });
}

function removerMarcadores() {
    marcadores.forEach((marcador) => {
        if ("map" in marcador) marcador.map = null;
        else if (marcador.setMap) marcador.setMap(null);
    });
    marcadores = [];
}

function criarMarcador(position, title) {
    if (googleMapId && google.maps.marker?.AdvancedMarkerElement) {
        const marcador = new google.maps.marker.AdvancedMarkerElement({
            map: mapaGoogle,
            position,
            title,
        });
        marcadores.push(marcador);
        return marcador;
    }

    const marcador = new google.maps.Marker({
        map: mapaGoogle,
        position,
        title,
    });
    marcadores.push(marcador);
    return marcador;
}

function renderMapa(estabelecimentos) {
    if (!window.google?.maps || !posicaoAtual) return;

    const alvo = document.getElementById("mapa");
    alvo.innerHTML = "";

    const opcoes = {
        center: posicaoAtual,
        zoom: 13,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: true,
        clickableIcons: true,
    };
    if (googleMapId) opcoes.mapId = googleMapId;

    mapaGoogle = new google.maps.Map(alvo, opcoes);
    removerMarcadores();

    criarMarcador(posicaoAtual, "Sua localização aproximada");
    const bounds = new google.maps.LatLngBounds();
    bounds.extend(posicaoAtual);

    estabelecimentos.forEach((e) => {
        const position = { lat: e.latitude, lng: e.longitude };
        bounds.extend(position);
        const marcador = criarMarcador(position, e.nome);
        const fonte = e.fonte === "google" ? "<br><small>Dados: Google Maps</small>" : "";
        const info = new google.maps.InfoWindow({
            content: `<strong>${escaparHTML(e.nome)}</strong><br><small>${escaparHTML(e.endereco || "")}</small><br><small>${escaparHTML(estrelas(e))}</small>${fonte}`,
        });
        marcador.addListener("click", () => info.open({ map: mapaGoogle, anchor: marcador }));
    });

    if (estabelecimentos.length) {
        mapaGoogle.fitBounds(bounds, 60);
        google.maps.event.addListenerOnce(mapaGoogle, "idle", () => {
            if (mapaGoogle.getZoom() > 16) mapaGoogle.setZoom(16);
        });
    }
}

function urlRota(e) {
    if (e.google_maps_uri) return e.google_maps_uri;
    if (e.latitude == null || e.longitude == null) return null;
    return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(`${e.latitude},${e.longitude}`)}`;
}

async function registrarVisualizacoes(lista) {
    const ids = lista
        .filter((e) => e.estabelecimento_id && !visualizacoesRegistradas.has(e.estabelecimento_id))
        .map((e) => e.estabelecimento_id);
    if (!ids.length) return;
    ids.forEach((id) => visualizacoesRegistradas.add(id));
    try {
        await ChurrasPlanAPI.registrarInteracoesEstabelecimentos("visualizacao", ids, churrascoMapaId, "onde_comprar");
    } catch {
        // Métricas nunca bloqueiam a experiência.
    }
}

function renderProximos(lista) {
    const el = document.getElementById("mercados-proximos");
    el.innerHTML = lista.length
        ? lista.map((e) => {
            const rota = urlRota(e);
            const id = e.estabelecimento_id ? ` data-estabelecimento-id="${e.estabelecimento_id}"` : "";
            const google = e.fonte === "google";
            const classeFonte = google ? " market-card--google" : "";
            const atribuicao = google ? '<span class="market-card__source">Google Maps</span>' : "";
            return `<article class="market-card${classeFonte}"${id}>
                <div class="market-card__heading"><h3>${escaparHTML(e.nome)}</h3>${atribuicao}</div>
                <p>${escaparHTML(e.endereco || tipoLoja(e.tipo))}</p>
                <div class="market-card__meta">
                    ${e.distancia_km != null ? `<span>${formatarNumero(e.distancia_km, 1)} km</span>` : ""}
                    <span>${escaparHTML(estrelas(e))}</span>
                    ${e.parceiro_verificado ? "<span>Parceiro verificado</span>" : ""}
                </div>
                ${rota ? `<p><a class="inline-link js-rota" target="_blank" rel="noopener" href="${escaparHTML(rota)}"${e.estabelecimento_id ? ` data-estabelecimento-id="${e.estabelecimento_id}"` : ""}>Abrir rota</a></p>` : ""}
            </article>`;
        }).join("")
        : '<div class="empty-state">Nenhum estabelecimento encontrado nesse raio.</div>';

    el.querySelectorAll(".js-rota[data-estabelecimento-id]").forEach((link) => link.addEventListener("click", () => {
        const id = Number(link.dataset.estabelecimentoId);
        if (id) ChurrasPlanAPI.registrarInteracoesEstabelecimentos("clique", [id], churrascoMapaId, "rota").catch(() => {});
    }));
    registrarVisualizacoes(lista);
}

function renderOtimizacao(dados) {
    const el = document.getElementById("otimizacao-conteudo");
    const cestas = dados.cestas || [];
    const otimizada = dados.compra_otimizada || {};
    let html = dados.aviso ? `<p class="mensagem mensagem--aviso">${escaparHTML(dados.aviso)}</p>` : "";

    if (otimizada.total != null) {
        html += `<div class="optimized-box">
            <span class="eyebrow"><span></span>COMPRA OTIMIZADA</span>
            <strong>${formatarMoeda(otimizada.total)}</strong>
            <p class="texto-suave">${otimizada.estabelecimentos_usados} estabelecimento(s)${otimizada.economia_vs_melhor_loja != null ? ` · economia de ${formatarMoeda(otimizada.economia_vs_melhor_loja)} contra a melhor loja única completa` : ""}</p>
            <div class="basket-items">${(otimizada.itens || []).map((i) => `${escaparHTML(i.descricao)} → ${escaparHTML(i.estabelecimento_nome)} · ${formatarMoeda(i.subtotal)}`).join("<br>")}</div>
        </div>`;
    }

    html += `<div class="basket-table">${cestas.length
        ? cestas.map((c) => `<article class="basket-row">
            <div class="basket-row__top">
                <div><strong>${escaparHTML(c.estabelecimento_nome)}</strong><br><small>${c.itens_encontrados}/${c.itens_total} itens · ${formatarNumero(c.cobertura_percentual, 0)}% cobertura${c.distancia_km != null ? ` · ${formatarNumero(c.distancia_km, 1)} km` : ""}${c.avaliacao != null ? ` · ${formatarNumero(c.avaliacao, 1)} ★` : ""}</small></div>
                <strong>${formatarMoeda(c.total)}</strong>
            </div>
            <div class="basket-items">${(c.itens || []).slice(0, 8).map((i) => `${escaparHTML(i.descricao)} · ${formatarMoeda(i.subtotal)}`).join("<br>")}</div>
        </article>`).join("")
        : '<div class="empty-state">Ainda não existem ofertas verificadas suficientes para comparar esta lista.</div>'}</div>`;
    el.innerHTML = html;
}

async function atualizarTudo() {
    if (!posicaoAtual || !churrascoMapaId) return;
    const msg = document.getElementById("mapa-mensagem");
    mostrarMensagem(msg, "Atualizando estabelecimentos e preços...", "aviso");
    try {
        const [proximos, otim] = await Promise.all([
            ChurrasPlanAPI.estabelecimentosProximos(posicaoAtual.lat, posicaoAtual.lng, 15),
            ChurrasPlanAPI.otimizarCompra(churrascoMapaId, modoAtual, posicaoAtual.lat, posicaoAtual.lng),
        ]);
        renderProximos(proximos);
        renderMapa(proximos);
        renderOtimizacao(otim);
        mostrarMensagem(msg, null);
    } catch (erro) {
        mostrarMensagem(msg, erro.message, "erro");
    }
}

async function solicitarLocalizacao() {
    if (!navigator.geolocation) {
        mostrarMensagem(document.getElementById("mapa-mensagem"), "Seu navegador não oferece geolocalização.", "erro");
        return;
    }
    navigator.geolocation.getCurrentPosition(
        async (p) => {
            posicaoAtual = { lat: p.coords.latitude, lng: p.coords.longitude };
            await atualizarTudo();
        },
        (erro) => mostrarMensagem(
            document.getElementById("mapa-mensagem"),
            erro.code === 1
                ? "A localização foi negada. Você pode habilitá-la nas permissões do navegador."
                : "Não foi possível obter sua localização.",
            "erro",
        ),
        { enableHighAccuracy: false, timeout: 10000, maximumAge: 120000 },
    );
}

document.addEventListener("DOMContentLoaded", async () => {
    const usuario = await ChurrasPlanAuth.usuarioAtual().catch(() => null);
    if (!usuario) {
        irPara(ChurrasPlanAuth.urlLogin(location.pathname.split("/").pop() + location.search));
        return;
    }

    const queryId = Number(new URLSearchParams(location.search).get("churrasco"));
    const estado = EstadoChurrasco.obter();
    churrascoMapaId = queryId || Number(estado.churrasco_id);
    if (!churrascoMapaId) {
        mostrarMensagem(document.getElementById("mapa-mensagem"), "Abra a Central de um churrasco antes de consultar onde comprar.", "erro");
        document.getElementById("localizar").disabled = true;
        return;
    }

    try {
        await ChurrasPlanAuth.vincularPlanejamentoAtual();
        const cfg = await ChurrasPlanAPI.configOndeComprar();
        googleMapId = cfg.google_map_id || null;
        if (cfg.google_maps_disponivel) {
            const ok = await carregarGoogleMaps(cfg.google_maps_js_api_key, googleMapId);
            if (!ok) {
                mostrarMensagem(document.getElementById("mapa-mensagem"), "O mapa visual não carregou, mas a comparação por lista continua disponível.", "aviso");
            } else if (!cfg.google_places_disponivel) {
                mostrarMensagem(document.getElementById("mapa-mensagem"), "Google Maps está ativo. A busca externa de mercados pelo Places ainda não foi habilitada; serão usados os estabelecimentos do ChurrasPlan.", "aviso");
            }
        } else {
            document.getElementById("mapa").innerHTML = "<span>Google Maps ainda não foi configurado. A lista e a otimização continuam disponíveis com os estabelecimentos cadastrados.</span>";
        }
    } catch (erro) {
        mostrarMensagem(document.getElementById("mapa-mensagem"), erro.message, "erro");
    }

    document.getElementById("localizar").onclick = solicitarLocalizacao;
    document.querySelectorAll("#ranking-modos [data-modo]").forEach((b) => {
        b.onclick = async () => {
            document.querySelectorAll("#ranking-modos [data-modo]").forEach((x) => x.classList.remove("active"));
            b.classList.add("active");
            modoAtual = b.dataset.modo;
            await atualizarTudo();
        };
    });
});
