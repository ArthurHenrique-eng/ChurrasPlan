"""Métricas agregadas, com denominadores e limites explícitos, sem IDs na resposta."""
from datetime import timedelta
from sqlalchemy import func
from models import Churrasco, EventoProduto, Usuario
from services.auth import agora

FUNIS = {
    "planejamento_b2c": ("sessao_dia", ["landing_visualizada", "planejamento_iniciado", "planejamento_concluido", "resultado_visualizado"]),
    "descoberta_b2c": ("sessao_dia", ["onde_comprar_acessado", "parceiro_visualizado", "parceiro_clicado"]),
    "ativacao_b2b": ("organizacao", ["organizacao_criada", "estabelecimento_enviado", "estabelecimento_aprovado", "primeiro_produto", "primeira_oferta"]),
    "valor_b2b": ("organizacao", ["primeira_oferta", "primeira_impressao", "primeiro_clique"]),
}


def funis_produto(db, desde):
    resultados = {}
    ate = agora()
    for nome, (tipo, eventos) in FUNIS.items():
        etapas, anterior, total_anterior, base = [], None, None, None
        for evento in eventos:
            query = db.query(EventoProduto.contexto_hash.label("contexto"), func.min(EventoProduto.criado_em).label("momento")).filter(
                EventoProduto.contexto_tipo == tipo, EventoProduto.contexto_hash.is_not(None),
                EventoProduto.evento == evento, EventoProduto.criado_em >= desde, EventoProduto.criado_em <= ate)
            if anterior is not None:
                query = query.join(anterior, EventoProduto.contexto_hash == anterior.c.contexto).filter(EventoProduto.criado_em >= anterior.c.momento)
            anterior = query.group_by(EventoProduto.contexto_hash).subquery()
            quantidade = db.query(func.count()).select_from(anterior).scalar()
            if base is None:
                base = quantidade
            etapas.append({"evento": evento, "quantidade": quantidade,
                "conversao_inicio_pct": round(100 * quantidade / base, 2) if base else None,
                "conversao_anterior_pct": round(100 * quantidade / total_anterior, 2) if total_anterior else None,
                "abandonos_observados": total_anterior - quantidade if total_anterior is not None else None})
            total_anterior = quantidade
        resultados[nome] = {"unidade": "sessões consentidas por dia" if tipo == "sessao_dia" else "organizações",
            "etapas": etapas, "desde_utc": desde, "ate_utc": ate}
    return {"resultados": resultados, "limitacoes": [
        "Etapas exigem o mesmo contexto e ordem observada dentro do período; entrada direta e etapas anteriores ao período não entram no denominador.",
        "B2C conta sessões consentidas por dia, não pessoas; eventos são deduplicados por etapa/dia e não distinguem vários planejamentos na mesma sessão.",
        "Eventos legados sem contexto não são vinculados retroativamente. Cadastros/leads e billing são contagens operacionais separadas, sem inferir vínculo com sessão anônima.",
        "Abandono observado é a diferença entre duas etapas; não prova desistência definitiva, venda ou causa do abandono."]}


def retencao_planejamentos(db, dias):
    ate = agora(); desde = ate - timedelta(days=dias); anterior_desde = desde - timedelta(days=dias)
    def ativos(inicio, fim):
        return db.query(Churrasco.usuario_id.label("usuario")).join(Usuario, Usuario.id == Churrasco.usuario_id).filter(
            Usuario.ativo.is_(True), Churrasco.criado_em >= inicio, Churrasco.criado_em < fim).distinct()
    anteriores = ativos(anterior_desde, desde).subquery()
    atuais = ativos(desde, ate).subquery()
    base = db.query(func.count()).select_from(anteriores).scalar()
    corrente = db.query(func.count()).select_from(atuais).scalar()
    retornaram = db.query(func.count()).select_from(anteriores.join(atuais, anteriores.c.usuario == atuais.c.usuario)).scalar()
    eventos = db.query(func.count(Churrasco.id)).join(Usuario, Usuario.id == Churrasco.usuario_id).filter(
        Usuario.ativo.is_(True), Churrasco.criado_em >= desde, Churrasco.criado_em < ate).scalar()
    return {"janela_dias": dias, "base_periodo_anterior": base, "ativos_periodo_atual": corrente,
        "retornaram": retornaram, "retencao_pct": round(100 * retornaram / base, 2) if base else None,
        "planejamentos_salvos_periodo": eventos, "planejamentos_por_usuario_ativo": round(eventos / corrente, 2) if corrente else None,
        "formula": "Contas atualmente ativas com planejamento salvo em ambas as janelas consecutivas / contas atualmente ativas com planejamento na janela anterior.",
        "limitacao": "Mede recorrência de criação de planejamentos salvos, não visitas, RSVP, alterações, satisfação ou retenção financeira. Contas excluídas não são identificadas."}
