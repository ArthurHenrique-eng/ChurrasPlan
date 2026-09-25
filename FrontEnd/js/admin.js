function adminMensagem(texto, tipo = "aviso") {
    const el = document.getElementById("admin-mensagem");
    if (!el) return;
    if (!texto) { el.hidden = true; el.textContent = ""; return; }
    el.hidden = false;
    mostrarMensagem(el, texto, tipo);
}

function fmtAdminData(valor) {
    if (!valor) return "—";
    const d = new Date(valor);
    return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function coordenadaAdmin(id, limite) {
    const campo = document.getElementById(id);
    const bruto = campo.value.trim();
    if (!bruto) return null;
    let valor = Number(bruto.replace(",", "."));
    if (!Number.isFinite(valor)) throw new Error("Informe uma coordenada válida.");
    if (Math.abs(valor) >= 1000000 && Math.abs(valor) <= limite * 1000000 && Number.isInteger(valor)) {
        valor /= 1000000;
    }
    if (Math.abs(valor) > limite) {
        throw new Error(`Coordenada fora do intervalo permitido (-${limite} a ${limite}).`);
    }
    campo.value = String(valor);
    return valor;
}

async function localizarEnderecoAdmin() {
    const ids = ["admin-est-endereco", "admin-est-cidade", "admin-est-estado", "admin-est-cep"];
    const partes = ids.map((id) => document.getElementById(id).value.trim()).filter(Boolean);
    if (!partes.length) throw new Error("Informe pelo menos o endereço ou a cidade para localizar.");

    const resultados = await ChurrasPlanAPI.autocompleteEndereco(partes.join(", "), null, null, 1);
    if (!resultados.length) throw new Error("Não foi possível localizar esse endereço.");

    const item = resultados[0];
    document.getElementById("admin-est-endereco").value = item.label;
    document.getElementById("admin-est-lat").value = item.latitude;
    document.getElementById("admin-est-lng").value = item.longitude;
    return item;
}

async function carregarDashboardAdmin() {
    const dados = await ChurrasPlanAPI.adminDashboard();
    const itens = [
        ["Usuários", dados.usuarios],
        ["Ativos", dados.usuarios_ativos],
        ["Parceiros", dados.parceiros],
        ["Pendentes", dados.estabelecimentos_pendentes],
        ["Churrascos", dados.churrascos],
        ["Ofertas", dados.ofertas_disponiveis],
    ];
    document.getElementById("admin-metrics").innerHTML = itens.map(([rotulo, valor]) => `<article><span>${escaparHTML(rotulo)}</span><strong>${Number(valor || 0).toLocaleString("pt-BR")}</strong></article>`).join("");
}

async function carregarUsuariosAdmin() {
    const busca = document.getElementById("admin-busca").value.trim();
    const dados = await ChurrasPlanAPI.adminUsuarios({ busca, pagina: 1, por_pagina: 100 });
    const tbody = document.getElementById("admin-usuarios");
    tbody.innerHTML = dados.itens.map((u) => `
        <tr>
            <td data-label="Usuário"><strong>${escaparHTML(u.nome)}</strong><small>${escaparHTML(u.email)}</small></td>
            <td data-label="Papel"><select data-role="${u.id}" aria-label="Papel de ${escaparHTML(u.nome)}"><option value="usuario" ${u.papel === "usuario" ? "selected" : ""}>Usuário</option><option value="parceiro" ${u.papel === "parceiro" ? "selected" : ""}>Parceiro</option><option value="admin" ${u.papel === "admin" ? "selected" : ""}>Admin</option></select></td>
            <td data-label="Status"><span class="status-pill ${u.ativo ? "is-ok" : "is-off"}">${u.ativo ? "ativo" : "inativo"}</span></td>
            <td data-label="Cadastro">${fmtAdminData(u.criado_em)}</td>
            <td data-label="Ações"><button class="botao botao--secundario" data-toggle-user="${u.id}" data-ativo="${u.ativo ? "1" : "0"}" type="button">${u.ativo ? "Desativar" : "Ativar"}</button></td>
        </tr>`).join("") || `<tr><td colspan="5">Nenhum usuário encontrado.</td></tr>`;

    tbody.querySelectorAll("[data-role]").forEach((select) => {
        select.addEventListener("change", async () => {
            const anterior = select.dataset.previous || "";
            try { await ChurrasPlanAPI.adminAtualizarUsuario(select.dataset.role, { papel: select.value }); adminMensagem("Papel atualizado.", "sucesso"); await carregarDashboardAdmin(); }
            catch (e) { adminMensagem(e.message, "erro"); if (anterior) select.value = anterior; }
        });
        select.dataset.previous = select.value;
    });
    tbody.querySelectorAll("[data-toggle-user]").forEach((botao) => botao.addEventListener("click", async () => {
        botao.disabled = true;
        try { await ChurrasPlanAPI.adminAtualizarUsuario(botao.dataset.toggleUser, { ativo: botao.dataset.ativo !== "1" }); await carregarUsuariosAdmin(); await carregarDashboardAdmin(); }
        catch (e) { adminMensagem(e.message, "erro"); botao.disabled = false; }
    }));
}

async function carregarEstabelecimentosAdmin() {
    const somente = document.getElementById("admin-somente-pendentes").checked;
    const itens = await ChurrasPlanAPI.adminEstabelecimentos({ somente_pendentes: somente });
    const tbody = document.getElementById("admin-estabelecimentos");
    tbody.innerHTML = itens.map((e) => `
        <tr>
            <td data-label="Estabelecimento"><strong>${escaparHTML(e.nome)}</strong><small>${escaparHTML(e.tipo)}</small></td>
            <td data-label="Local">${escaparHTML([e.cidade, e.estado].filter(Boolean).join(" / ") || "—")}</td>
            <td data-label="Verificado"><span class="status-pill ${e.parceiro_verificado ? "is-ok" : "is-warn"}">${e.parceiro_verificado ? "sim" : "pendente"}</span></td>
            <td data-label="Ativo"><span class="status-pill ${e.ativo ? "is-ok" : "is-off"}">${e.ativo ? "sim" : "não"}</span></td>
            <td data-label="Ações"><div class="admin-actions"><button class="botao botao--secundario" data-verify="${e.id}" data-value="${e.parceiro_verificado ? "0" : "1"}" type="button">${e.parceiro_verificado ? "Retirar verificação" : "Verificar"}</button><button class="botao botao--secundario" data-active="${e.id}" data-value="${e.ativo ? "0" : "1"}" type="button">${e.ativo ? "Desativar" : "Ativar"}</button></div></td>
        </tr>`).join("") || `<tr><td colspan="5">Nenhum estabelecimento nesta visualização.</td></tr>`;
    tbody.querySelectorAll("[data-verify]").forEach((b) => b.addEventListener("click", async () => { b.disabled = true; try { await ChurrasPlanAPI.adminAtualizarEstabelecimento(b.dataset.verify, { parceiro_verificado: b.dataset.value === "1" }); await carregarEstabelecimentosAdmin(); await carregarDashboardAdmin(); } catch (e) { adminMensagem(e.message, "erro"); b.disabled = false; } }));
    tbody.querySelectorAll("[data-active]").forEach((b) => b.addEventListener("click", async () => { b.disabled = true; try { await ChurrasPlanAPI.adminAtualizarEstabelecimento(b.dataset.active, { ativo: b.dataset.value === "1" }); await carregarEstabelecimentosAdmin(); await carregarDashboardAdmin(); } catch (e) { adminMensagem(e.message, "erro"); b.disabled = false; } }));
}

async function carregarAuditoriaAdmin() {
    const itens = await ChurrasPlanAPI.adminAuditoria(50);
    document.getElementById("admin-auditoria").innerHTML = itens.map((r) => `<article><div><strong>${escaparHTML(r.acao)}</strong><span>${escaparHTML(r.entidade)}${r.entidade_id ? ` #${escaparHTML(r.entidade_id)}` : ""}</span></div><time>${fmtAdminData(r.criado_em)}</time></article>`).join("") || `<p class="texto-suave">Ainda não há ações administrativas registradas.</p>`;
}

document.addEventListener("DOMContentLoaded", async () => {
    const usuario = await ChurrasPlanAuth.usuarioAtual().catch(() => null);
    if (!usuario) { irPara(ChurrasPlanAuth.urlLogin("admin.html")); return; }
    if (usuario.papel !== "admin") { irPara("minha-conta.html"); return; }
    try { await Promise.all([carregarDashboardAdmin(), carregarUsuariosAdmin(), carregarEstabelecimentosAdmin(), carregarAuditoriaAdmin()]); }
    catch (e) { adminMensagem(e.message, "erro"); }

    document.getElementById("admin-est-localizar").addEventListener("click", async (event) => {
        const botao = event.currentTarget;
        botao.disabled = true;
        try {
            await localizarEnderecoAdmin();
            adminMensagem("Endereço localizado e coordenadas preenchidas.", "sucesso");
        } catch (e) {
            adminMensagem(e.message, "erro");
        } finally {
            botao.disabled = false;
        }
    });

    document.getElementById("admin-form-estabelecimento").addEventListener("submit", async (event) => {
        event.preventDefault();
        const botao = event.currentTarget.querySelector('button[type="submit"]');
        botao.disabled = true;
        try {
            let latitude = coordenadaAdmin("admin-est-lat", 90);
            let longitude = coordenadaAdmin("admin-est-lng", 180);

            if (
                (latitude === null || longitude === null)
                && document.getElementById("admin-est-endereco").value.trim()
            ) {
                await localizarEnderecoAdmin();
                latitude = coordenadaAdmin("admin-est-lat", 90);
                longitude = coordenadaAdmin("admin-est-lng", 180);
            }

            await ChurrasPlanAPI.criarEstabelecimento({
                nome: document.getElementById("admin-est-nome").value.trim(),
                tipo: document.getElementById("admin-est-tipo").value,
                endereco: document.getElementById("admin-est-endereco").value.trim() || null,
                cidade: document.getElementById("admin-est-cidade").value.trim() || null,
                estado: document.getElementById("admin-est-estado").value.trim().toUpperCase() || null,
                cep: document.getElementById("admin-est-cep").value.trim() || null,
                latitude,
                longitude,
                logradouro: null,
                numero: null,
                bairro: null,
                telefone: null,
                site: null,
                horario_funcionamento: null,
            });

            event.currentTarget.reset();
            await Promise.all([carregarEstabelecimentosAdmin(), carregarDashboardAdmin()]);
            adminMensagem("Estabelecimento cadastrado e verificado.", "sucesso");
        } catch (e) {
            adminMensagem(e.message, "erro");
        } finally {
            botao.disabled = false;
        }
    });

    let timer;
    document.getElementById("admin-busca").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => carregarUsuariosAdmin().catch((e) => adminMensagem(e.message, "erro")), 250); });
    document.getElementById("admin-somente-pendentes").addEventListener("change", () => carregarEstabelecimentosAdmin().catch((e) => adminMensagem(e.message, "erro")));
});
