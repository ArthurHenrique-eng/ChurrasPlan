let posicaoAtual = null;
let modoAtual = "equilibrio";
let churrascoMapaId = null;
let mapa = null;
let mapaDisponivel = false;
let timerAutocomplete = null;
let timerViewport = null;
let marcadoresMapa = [];
let reencaixarMapa = true;
let ignorarProximoMoveend = false;
let sequenciaViewport = 0;
let erroMapaMostrado = false;
const visualizacoesRegistradas = new Set();

function estrelas(e) {
    return e.avaliacao == null
        ? "sem avaliação"
        : `${Number(e.avaliacao).toFixed(1)} ★${e.quantidade_avaliacoes ? ` (${e.quantidade_avaliacoes})` : ""}`;
}

function tipoLoja(tipo) {
    return String(tipo || "estabelecimento")
        .replace(/^commercial\./, "")
        .replace(/\./g, " ")
        .replace(/_/g, " ");
}

function distanciaKmLocal(lat1, lon1, lat2, lon2) {
    const rad = (graus) => graus * Math.PI / 180;
    const r = 6371;
    const dLat = rad(lat2 - lat1);
    const dLon = rad(lon2 - lon1);
    const a = (
        Math.sin(dLat / 2) ** 2
        + Math.cos(rad(lat1))
        * Math.cos(rad(lat2))
        * Math.sin(dLon / 2) ** 2
    );
    return 2 * r * Math.asin(Math.sqrt(a));
}

function raioViewportKm() {
    if (!mapa) return 15;
    const centro = mapa.getCenter();
    const nordeste = mapa.getBounds().getNorthEast();
    const raio = distanciaKmLocal(
        centro.lat,
        centro.lng,
        nordeste.lat,
        nordeste.lng,
    );
    return Math.min(50, Math.max(2, raio * 1.15));
}

function limparMarcadoresMapa() {
    marcadoresMapa.forEach((marcador) => marcador.remove());
    marcadoresMapa = [];
}

function criarPopupMapa(html) {
    return new maplibregl.Popup({
        offset: 18,
        closeButton: false,
        maxWidth: "280px",
    }).setHTML(html);
}

function renderMarcadoresMapa(estabelecimentos) {
    if (!mapa || !posicaoAtual) return;

    limparMarcadoresMapa();

    const voce = new maplibregl.Marker({
        color: "#2f80ed",
        scale: 0.82,
    })
        .setLngLat([posicaoAtual.lng, posicaoAtual.lat])
        .setPopup(
            criarPopupMapa("<strong>Sua localização aproximada</strong>"),
        )
        .addTo(mapa);
    marcadoresMapa.push(voce);

    estabelecimentos.forEach((e) => {
        const fonte = e.fonte === "geoapify"
            ? "<br><small>Dados: Geoapify / OpenStreetMap</small>"
            : "";

        const popup = criarPopupMapa(
            `<strong>${escaparHTML(e.nome)}</strong><br><small>${escaparHTML(e.endereco || "")}</small><br><small>${escaparHTML(estrelas(e))}</small>${fonte}`,
        );

        const marcador = new maplibregl.Marker({
            color: e.fonte === "geoapify" ? "#647050" : "#a84027",
            scale: 0.72,
        })
            .setLngLat([e.longitude, e.latitude])
            .setPopup(popup)
            .addTo(mapa);

        marcadoresMapa.push(marcador);
    });
}

async function atualizarPontosDoViewport() {
    if (!mapa || !posicaoAtual) return;

    const centro = mapa.getCenter();
    const raioKm = raioViewportKm();
    const sequencia = ++sequenciaViewport;

    try {
        const proximos = await ChurrasPlanAPI.estabelecimentosProximos(
            centro.lat,
            centro.lng,
            raioKm,
        );

        if (sequencia !== sequenciaViewport) return;
        renderMarcadoresMapa(proximos);
    } catch {
        // Mover o mapa nunca deve bloquear o restante da página.
    }
}

function agendarAtualizacaoViewport() {
    if (!mapa) return;
    window.clearTimeout(timerViewport);
    timerViewport = window.setTimeout(atualizarPontosDoViewport, 350);
}

function inicializarMapa() {
    const alvo = document.getElementById("mapa");

    if (!window.maplibregl) {
        alvo.innerHTML =
            "<span>Não foi possível carregar a biblioteca do mapa (MapLibre). Recarregue a página com Ctrl+F5.</span>";
        return false;
    }
    if (!posicaoAtual || !mapaDisponivel) return false;
    if (mapa) return true;

    alvo.innerHTML = "";

    const baseApi = API_BASE_URL || window.location.origin;
    const tilesUrl =
        `${baseApi}/api/onde-comprar/mapa/tiles/{z}/{x}/{y}.png?estilo=osm-carto`;

    mapa = new maplibregl.Map({
        container: alvo,
        style: {
            version: 8,
            sources: {
                geoapify: {
                    type: "raster",
                    tiles: [tilesUrl],
                    tileSize: 256,
                    maxzoom: 20,
                    attribution:
                        'Powered by <a href="https://www.geoapify.com/" target="_blank" rel="noopener">Geoapify</a> | <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap contributors</a>',
                },
            },
            layers: [
                {
                    id: "geoapify-base",
                    type: "raster",
                    source: "geoapify",
                },
            ],
        },
        center: [posicaoAtual.lng, posicaoAtual.lat],
        zoom: 13,
        minZoom: 2,
        maxZoom: 20,
        attributionControl: true,
        transformRequest: (url) => {
            if (url.includes("/api/onde-comprar/mapa/tiles/")) {
                return {
                    url,
                    credentials: "include",
                };
            }
            return { url };
        },
    });

    mapa.addControl(
        new maplibregl.NavigationControl({
            showCompass: false,
            visualizePitch: false,
        }),
        "top-left",
    );

    mapa.on("load", () => {
        mapa.resize();
    });

    mapa.on("moveend", () => {
        if (ignorarProximoMoveend) {
            ignorarProximoMoveend = false;
            return;
        }
        agendarAtualizacaoViewport();
    });

    mapa.on("error", (evento) => {
        const mensagem = String(evento?.error?.message || "");
        if (
            erroMapaMostrado
            || !/(401|403|502|tile|image|network|fetch)/i.test(mensagem)
        ) {
            return;
        }
        erroMapaMostrado = true;
        mostrarMensagem(
            document.getElementById("mapa-mensagem"),
            "O mapa base não pôde ser carregado pela API do ChurrasPlan. Verifique se a API está ligada e se a GEOAPIFY_SERVER_API_KEY está válida.",
            "erro",
        );
    });

    return true;
}

function renderMapa(estabelecimentos) {
    if (!inicializarMapa()) return;

    renderMarcadoresMapa(estabelecimentos);

    if (reencaixarMapa) {
        const bounds = new maplibregl.LngLatBounds();
        bounds.extend([posicaoAtual.lng, posicaoAtual.lat]);

        estabelecimentos.forEach((e) => {
            bounds.extend([e.longitude, e.latitude]);
        });

        if (!bounds.isEmpty()) {
            ignorarProximoMoveend = true;
            mapa.fitBounds(bounds, {
                padding: {
                    top: 55,
                    right: 55,
                    bottom: 55,
                    left: 55,
                },
                maxZoom: 15,
                duration: 0,
            });
        }

        reencaixarMapa = false;
    }

    window.setTimeout(() => mapa?.resize(), 0);
}

function urlRota(e) {
    if (!posicaoAtual || e.latitude == null || e.longitude == null) return null;
    const route = `${posicaoAtual.lat},${posicaoAtual.lng};${e.latitude},${e.longitude}`;
    return `https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route=${encodeURIComponent(route)}`;
}

async function registrarVisualizacoes(lista) {
    const ids = lista
        .filter((e) => e.estabelecimento_id && !visualizacoesRegistradas.has(e.estabelecimento_id))
        .map((e) => e.estabelecimento_id);
    if (!ids.length) return;

    ids.forEach((id) => visualizacoesRegistradas.add(id));

    try {
        await ChurrasPlanAPI.registrarInteracoesEstabelecimentos(
            "visualizacao",
            ids,
            churrascoMapaId,
            "onde_comprar",
        );
    } catch {
        // Métricas nunca bloqueiam a experiência.
    }
}

function renderProximos(lista) {
    const el = document.getElementById("mercados-proximos");
    el.innerHTML = lista.length
        ? lista.map((e) => {
            const rota = urlRota(e);
            const id = e.estabelecimento_id
                ? ` data-estabelecimento-id="${e.estabelecimento_id}"`
                : "";
            const externo = e.fonte === "geoapify";
            const classeFonte = externo ? " market-card--external" : "";
            const atribuicao = externo
                ? '<span class="market-card__source">Geoapify</span>'
                : "";

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

    el.querySelectorAll(".js-rota[data-estabelecimento-id]").forEach((link) => {
        link.addEventListener("click", () => {
            const id = Number(link.dataset.estabelecimentoId);
            if (id) {
                ChurrasPlanAPI.registrarInteracoesEstabelecimentos(
                    "clique",
                    [id],
                    churrascoMapaId,
                    "rota",
                ).catch(() => {});
            }
        });
    });

    registrarVisualizacoes(lista);
}

function renderOtimizacao(dados) {
    const el = document.getElementById("otimizacao-conteudo");
    const cestas = dados.cestas || [];
    const otimizada = dados.compra_otimizada || {};
    let html = dados.aviso
        ? `<p class="mensagem mensagem--aviso">${escaparHTML(dados.aviso)}</p>`
        : "";

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
            ChurrasPlanAPI.estabelecimentosProximos(
                posicaoAtual.lat,
                posicaoAtual.lng,
                15,
            ),
            ChurrasPlanAPI.otimizarCompra(
                churrascoMapaId,
                modoAtual,
                posicaoAtual.lat,
                posicaoAtual.lng,
            ),
        ]);

        renderProximos(proximos);

        if (!mapa || reencaixarMapa) {
            renderMapa(proximos);
        }

        renderOtimizacao(otim);
        mostrarMensagem(msg, null);
    } catch (erro) {
        mostrarMensagem(msg, erro.message, "erro");
    }
}

function usarPosicao(latitude, longitude, rotulo = null) {
    posicaoAtual = {
        lat: Number(latitude),
        lng: Number(longitude),
    };
    reencaixarMapa = true;
    sequenciaViewport += 1;

    if (rotulo) {
        document.getElementById("endereco-busca").value = rotulo;
    }

    document.getElementById("endereco-sugestoes").innerHTML = "";
    return atualizarTudo();
}

async function buscarAutocomplete() {
    const input = document.getElementById("endereco-busca");
    const lista = document.getElementById("endereco-sugestoes");
    const texto = input.value.trim();

    if (texto.length < 3) {
        lista.innerHTML = "";
        return;
    }

    try {
        const resultados = await ChurrasPlanAPI.autocompleteEndereco(
            texto,
            posicaoAtual?.lat ?? null,
            posicaoAtual?.lng ?? null,
            6,
        );

        lista.innerHTML = resultados.length
            ? resultados.map(
                (item, indice) =>
                    `<button type="button" data-endereco-indice="${indice}">${escaparHTML(item.label)}</button>`,
            ).join("")
            : '<span class="location-search__empty">Nenhum endereço encontrado.</span>';

        lista.querySelectorAll("[data-endereco-indice]").forEach((botao) => {
            botao.addEventListener("click", () => {
                const item = resultados[Number(botao.dataset.enderecoIndice)];
                usarPosicao(item.latitude, item.longitude, item.label);
            });
        });
    } catch (erro) {
        lista.innerHTML =
            `<span class="location-search__empty">${escaparHTML(erro.message)}</span>`;
    }
}

function solicitarLocalizacao() {
    if (!navigator.geolocation) {
        mostrarMensagem(
            document.getElementById("mapa-mensagem"),
            "Seu navegador não oferece geolocalização. Digite um endereço.",
            "erro",
        );
        return;
    }

    navigator.geolocation.getCurrentPosition(
        (p) => usarPosicao(p.coords.latitude, p.coords.longitude),
        (erro) => mostrarMensagem(
            document.getElementById("mapa-mensagem"),
            erro.code === 1
                ? "A localização foi negada. Digite um endereço ou habilite a permissão do navegador."
                : "Não foi possível obter sua localização. Digite um endereço.",
            "aviso",
        ),
        {
            enableHighAccuracy: false,
            timeout: 10000,
            maximumAge: 120000,
        },
    );
}

document.addEventListener("DOMContentLoaded", async () => {
    const usuario = await ChurrasPlanAuth.usuarioAtual().catch(() => null);
    if (!usuario) {
        irPara(
            ChurrasPlanAuth.urlLogin(
                location.pathname.split("/").pop() + location.search,
            ),
        );
        return;
    }

    const queryId = Number(
        new URLSearchParams(location.search).get("churrasco"),
    );
    const estado = EstadoChurrasco.obter();
    churrascoMapaId = queryId || Number(estado.churrasco_id);

    if (!churrascoMapaId) {
        mostrarMensagem(
            document.getElementById("mapa-mensagem"),
            "Abra a Central de um churrasco antes de consultar onde comprar.",
            "erro",
        );
        document.getElementById("localizar").disabled = true;
        document.getElementById("endereco-busca").disabled = true;
        return;
    }

    try {
        await ChurrasPlanAuth.vincularPlanejamentoAtual();
        const cfg = await ChurrasPlanAPI.configOndeComprar();
        mapaDisponivel = Boolean(cfg.geoapify_map_disponivel);

        if (!mapaDisponivel) {
            document.getElementById("mapa").innerHTML =
                "<span>Geoapify ainda não foi configurado. A lista e a otimização continuam disponíveis.</span>";
        } else if (!cfg.geoapify_places_disponivel) {
            mostrarMensagem(
                document.getElementById("mapa-mensagem"),
                "O mapa está ativo, mas a busca externa de estabelecimentos Geoapify ainda não foi habilitada.",
                "aviso",
            );
        }
    } catch (erro) {
        mostrarMensagem(
            document.getElementById("mapa-mensagem"),
            erro.message,
            "erro",
        );
    }

    document.getElementById("localizar").onclick = solicitarLocalizacao;

    document.getElementById("endereco-busca").addEventListener("input", () => {
        window.clearTimeout(timerAutocomplete);
        timerAutocomplete = window.setTimeout(buscarAutocomplete, 280);
    });

    document.querySelectorAll("#ranking-modos [data-modo]").forEach((b) => {
        b.onclick = async () => {
            document
                .querySelectorAll("#ranking-modos [data-modo]")
                .forEach((x) => x.classList.remove("active"));

            b.classList.add("active");
            modoAtual = b.dataset.modo;

            await atualizarTudo();
        };
    });
});
