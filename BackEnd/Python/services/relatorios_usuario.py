"""Relatórios do planejamento Premium; sem preços inventados nem dados de cartão."""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def _dinheiro(valor):
    if valor is None:
        return None
    return float(Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def detalhar_custos(churrasco, itens) -> dict:
    categorias = defaultdict(lambda: {"total_conhecido": Decimal("0"), "itens_com_preco": 0, "itens_sem_preco": 0})
    conhecidos = []
    detalhados = []
    for i in itens:
        subtotal = _dinheiro(i.subtotal_estimado)
        categoria = i.categoria or "outros"
        c = categorias[categoria]
        if subtotal is None:
            c["itens_sem_preco"] += 1
        else:
            c["total_conhecido"] += Decimal(str(subtotal))
            c["itens_com_preco"] += 1
            conhecidos.append(Decimal(str(subtotal)))
        detalhados.append({
            "nome": i.nome, "categoria": categoria,
            "quantidade_compra": i.quantidade_compra, "unidade_compra": i.unidade_compra,
            "preco_estimado": i.preco_estimado, "preco_fonte": i.preco_fonte,
            "subtotal_estimado": subtotal,
        })
    total = sum(conhecidos, Decimal("0"))
    completo = bool(itens) and len(conhecidos) == len(itens)
    agregado = _dinheiro(total) if conhecidos else None
    por_categoria = [
        {"categoria": k, "total_conhecido": _dinheiro(v["total_conhecido"]),
         "percentual_do_conhecido": round(float(v["total_conhecido"] / total * 100), 1) if total else None,
         "itens_com_preco": v["itens_com_preco"], "itens_sem_preco": v["itens_sem_preco"]}
        for k, v in sorted(categorias.items())
    ]
    orcamento = _dinheiro(churrasco.orcamento_maximo)
    return {
        "churrasco_id": churrasco.id, "nome": churrasco.nome or "Churrasco",
        "pessoas": churrasco.total_pessoas,
        "total_estimado_conhecido": agregado, "estimativa_completa": completo,
        "itens_com_preco": len(conhecidos), "itens_sem_preco": len(itens) - len(conhecidos),
        "custo_conhecido_por_pessoa": round(agregado / churrasco.total_pessoas, 2)
        if agregado is not None and churrasco.total_pessoas else None,
        "orcamento_maximo": orcamento,
        "saldo_orcamento": round(orcamento - agregado, 2)
        if orcamento is not None and completo and agregado is not None else None,
        "categorias": por_categoria, "itens": detalhados,
        "aviso": "Valores estimados, não ofertas garantidas. Totais parciais não indicam o custo final."
        if not completo else "Estimativas para planejamento; disponibilidade e valores podem variar.",
    }


def exportar_csv(relatorio: dict) -> bytes:
    stream = io.StringIO(newline="")
    out = csv.writer(stream, delimiter=";")
    out.writerow(["ChurrasPlan - Planejamento Premium", relatorio["nome"]])
    out.writerow(["Pessoas", relatorio["pessoas"]])
    out.writerow(["Estimativa completa", "sim" if relatorio["estimativa_completa"] else "nao"])
    out.writerow(["Item", "Categoria", "Quantidade de compra", "Unidade", "Preco unitario estimado (BRL)",
                  "Subtotal estimado (BRL)", "Fonte"])
    for item in relatorio["itens"]:
        # Prefixo protege planilhas contra execução de fórmulas injetadas nos nomes.
        safe = lambda x: ("'" + x if isinstance(x, str) and x.startswith(("=", "+", "-", "@", "\t", "\r")) else x)
        out.writerow([safe(item["nome"]), safe(item["categoria"]), item["quantidade_compra"],
                      safe(item["unidade_compra"]), item["preco_estimado"],
                      item["subtotal_estimado"], safe(item["preco_fonte"] or "sem preco")])
    out.writerow(["Total conhecido (BRL)", relatorio["total_estimado_conhecido"]])
    out.writerow(["Aviso", relatorio["aviso"]])
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def exportar_pdf(relatorio: dict) -> bytes:
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    largura, altura = A4
    y = altura - 48

    def linha(texto, *, tamanho=10, passo=17):
        nonlocal y
        if y < 54:
            pdf.showPage()
            y = altura - 48
        pdf.setFont("Helvetica", tamanho)
        # A4 e Helvetica: transliterar caracteres fora do Latin-1.
        texto = str(texto).encode("latin-1", "replace").decode("latin-1")
        pdf.drawString(44, y, texto[:102])
        y -= passo

    linha("ChurrasPlan | Planejamento Premium", tamanho=15, passo=30)
    linha("Evento: " + relatorio["nome"][:80])
    linha("Convidados: " + str(relatorio["pessoas"]))
    linha("Custo conhecido: R$ " + str(relatorio["total_estimado_conhecido"] or "indisponivel"))
    linha("Estimativa completa: " + ("sim" if relatorio["estimativa_completa"] else "nao"), passo=26)
    for item in relatorio["itens"]:
        nome = item["nome"][:53]
        linha(f'{nome} | {item["quantidade_compra"]} {item["unidade_compra"]} | R$ {item["subtotal_estimado"] if item["subtotal_estimado"] is not None else "sem preco"}')
    y -= 12
    linha(relatorio["aviso"], tamanho=8)
    pdf.save()
    return buf.getvalue()
