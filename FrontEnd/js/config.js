const API_BASE_URL = (() => {
    const override = window.CHURRASPLAN_CONFIG?.apiBaseUrl
        || document.querySelector('meta[name="churrasplan-api-url"]')?.content?.trim();
    if (override) return override.replace(/\/$/, "");

    const { protocol, hostname, port } = window.location;
    if (protocol === "file:") return "http://127.0.0.1:8000";

    // Desenvolvimento local: frontend costuma ser servido em 5500/5501 e a
    // API em 8000. Em produção, usa caminho relativo /api no mesmo domínio,
    // permitindo reverse proxy sem editar o JavaScript.
    const hostLocal = hostname === "localhost" || hostname === "127.0.0.1";
    if (hostLocal || ["5500", "5501"].includes(port)) {
        return `${protocol}//${hostname || "127.0.0.1"}:8000`;
    }
    return "";
})();

const CATALOGO_CARNES = [
    ["picanha", "Picanha"], ["picanha-suina", "Picanha suína"], ["contra-file", "Contra-filé"],
    ["alcatra", "Alcatra"], ["fraldinha", "Fraldinha"], ["maminha", "Maminha"], ["acem", "Acém"],
    ["costela", "Costela"], ["costelinha-porco", "Costelinha de porco"], ["cupim", "Cupim"],
    ["linguica", "Linguiça"], ["lombo", "Lombo"], ["bisteca", "Bisteca"], ["frango", "Frango"],
    ["asinha-frango", "Asinha de frango"], ["coracao", "Coração"],
    ["queijo-coalho-churrasco", "Queijo coalho"], ["pao-alho-churrasco", "Pão de alho"],
    ["bife-ancho", "Bife Ancho"], ["bife-chorizo", "Bife de Chorizo"], ["prime-rib", "Prime Rib"],
    ["short-rib", "Short Rib"], ["file-mignon", "Filé Mignon"],
].map(([slug, nome]) => ({ slug, nome }));

const CATALOGO_BEBIDAS_NAO_ALCOOLICAS = [
    { chave: "agua", nome: "Água" },
    { chave: "refrigerante", nome: "Refrigerante" },
    { chave: "suco", nome: "Suco" },
];

const CATALOGO_EXTRAS = [
    { chave: "sal_grosso", nome: "Sal grosso" }, { chave: "acendedor", nome: "Acendedor" },
    { chave: "fosforo_isqueiro", nome: "Fósforo / isqueiro" }, { chave: "copos", nome: "Copos" },
    { chave: "pratos", nome: "Pratos" }, { chave: "talheres", nome: "Talheres" },
    { chave: "guardanapos", nome: "Guardanapos" }, { chave: "sacos_lixo", nome: "Sacos de lixo" },
    { chave: "papel_toalha", nome: "Papel toalha" }, { chave: "papel_aluminio", nome: "Papel alumínio" },
    { chave: "palitos", nome: "Palitos" },
];

const CATALOGO_ACOMPANHAMENTOS = [
    { chave: "pao_de_alho", nome: "Pão de alho" }, { chave: "farofa", nome: "Farofa" },
    { chave: "vinagrete", nome: "Vinagrete" }, { chave: "queijo_coalho", nome: "Queijo coalho" },
    { chave: "maionese", nome: "Maionese" }, { chave: "salada", nome: "Salada" },
    { chave: "arroz", nome: "Arroz" }, { chave: "molhos", nome: "Molhos" }, { chave: "pao", nome: "Pão" },
];

const TIPOS_EVENTO = [
    { chave: "almoco", nome: "Almoço", descricao: "Referência padrão de consumo" },
    { chave: "jantar", nome: "Jantar", descricao: "Ajuste moderado para refeição noturna" },
    { chave: "aniversario", nome: "Aniversário", descricao: "Considera a presença de outros alimentos" },
    { chave: "confraternizacao_empresa", nome: "Confraternização de empresa", descricao: "Planejamento mais conservador para grupos grandes" },
    { chave: "evento_prolongado", nome: "Evento prolongado", descricao: "Pequeno acréscimo além do fator de duração" },
    { chave: "outro", nome: "Outro", descricao: "Usa o fator neutro de evento" },
];

const PERFIS_CONSUMO = [
    { chave: "leve", nome: "Consumo leve", descricao: "Porções mais enxutas" },
    { chave: "normal", nome: "Consumo normal", descricao: "Referência equilibrada" },
    { chave: "alto", nome: "Consumo alto", descricao: "Margem maior de consumo" },
    { chave: "personalizado", nome: "Personalizado", descricao: "Você define os coeficientes" },
];
