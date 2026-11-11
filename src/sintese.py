"""
Gera a Sintese Executiva (1 pagina, PDF) a partir de outputs/resultados.json
e da figura do painel atual. Executado na ultima celula do notebook.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

INTEGRANTES = "Pedro Luis Tofoli (RM 564441) · Raphael Talarico Nascimento Silva (RM 565219) · Nelson Troccoli Santos Neto (RM 562815)"


def _fontes():
    ttf = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    pdfmetrics.registerFont(TTFont("DV", str(ttf / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DVB", str(ttf / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFontFamily("DV", normal="DV", bold="DVB", italic="DV", boldItalic="DVB")


def _fmt(v, nd=1):
    return f"{v:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar(raiz: Path, destino: Path | None = None) -> Path:
    raiz = Path(raiz)
    r = json.loads((raiz / "outputs" / "resultados.json").read_text(encoding="utf-8"))
    destino = destino or raiz / "Sintese_Executiva_GS2026-2.pdf"
    _fontes()

    base = ParagraphStyle("b", fontName="DV", fontSize=7.6, leading=9.6, alignment=TA_JUSTIFY)
    h = ParagraphStyle("h", parent=base, fontName="DVB", fontSize=8.6, leading=10.5,
                       textColor=colors.HexColor("#0b3d6b"), spaceBefore=3, spaceAfter=1)
    tit = ParagraphStyle("t", parent=base, fontName="DVB", fontSize=11.5, leading=14, alignment=0,
                         textColor=colors.HexColor("#0b3d6b"))
    peq = ParagraphStyle("p", parent=base, fontSize=6.6, leading=8.2, textColor=colors.HexColor("#444444"))

    reg = {(d["horizonte"], d["modelo"]): d for d in r["reg"]}
    clf = {(d["amostras"], d["modelo"]): d for d in r["clf"]}
    prev = {int(d["horizonte"]): d for d in r["previsao_cantareira"]}
    painel = {d["sistema"]: d for d in r["painel"]}
    val_te = {d["regra"]: d for d in r["aval_regras_teste"]}
    regra = r["regra_alerta"]
    rf60, pe60, cl60 = reg[(60, "RandomForest")], reg[(60, "Persistência (Δ=0)")], reg[(60, "Climatologia sazonal")]
    rfc, rft = clf[("todos", "RandomForest")], clf[("V(t) ≥ 40%", "RandomForest")]
    ant = [v for d in r["antecipacao"] for k, v in d.items() if k.startswith("RandomForest")]
    ant_txt = ", ".join(a.split(" (")[0] for a in ant)
    c = painel["Cantareira"]
    ah = r["ano_hidro"]

    E = []
    E.append(Paragraph("Síntese Executiva — Monitoramento e previsão de riscos hídricos na RMSP", tit))
    E.append(Paragraph(f"GS 2026-2 · Data Science and Analytics · Integrantes: {INTEGRANTES} · "
                       f"Dados até {r['data_referencia'][8:10]}/{r['data_referencia'][5:7]}/{r['data_referencia'][:4]}", peq))
    E.append(Spacer(1, 3))

    E.append(Paragraph("Problema e pergunta de pesquisa", h))
    E.append(Paragraph(
        "A RMSP depende de sete sistemas produtores integrados. O <b>Cantareira</b> concentra cerca de metade do volume útil "
        "e chegou a 19,3 % em jan/2026, depois da estiagem de 2025 (em 2014–15 operou com a reserva técnica). "
        "<b>Pergunta:</b> com dados públicos de armazenamento, chuva e vazões, é possível antecipar com <b>60 dias</b> se o Cantareira "
        "estará abaixo de <b>40 %</b> (faixas de Alerta, Restrição e Especial da Res. ANA/DAEE 925/2017)? E qual é o risco atual de cada sistema?", base))

    E.append(Paragraph("Dados", h))
    E.append(Paragraph(
        "<b>Sabesp – Portal dos Mananciais (API v4):</b> séries diárias de 01/2000 a 11/2026 para 7 sistemas e o SIM (volume útil, chuva, "
        "vazões natural, afluente, captada e de jusante, médias históricas), com 596 mil registros. <b>SP Águas – SIBH:</b> chuva de 2 postos telemétricos "
        "na bacia do Cantareira (2015–2026), usada como validação independente (correlação mensal r = 0,92). Tratamentos: calendário diário completo, "
        "detecção de quebras metodológicas (ex.: redefinição do volume útil em 01/09/2004), manutenção da reserva técnica e de "
        "vazões negativas do balanço. Limitação: todos os dados são operacionais, não consistidos.", base))

    E.append(Paragraph("Principais evidências e indicadores", h))
    E.append(Paragraph(
        f"• A captação (~28 m³/s) supera a afluência de maio a outubro; o volume só sobe de dezembro a março. "
        f"• A chuva anual explica a variação do volume (ρ = {_fmt(ah['spearman'], 2)}): +{_fmt(ah['inclinacao_pp_100mm'])} p.p. a cada 100 mm. "
        f"A <b>chuva de equilíbrio (~{_fmt(ah['chuva_equilibrio'], 0)} mm/ano)</b> está acima da média de 2000–2025. "
        "• A anomalia de chuva aparece no volume com cerca de 1 mês de defasagem. "
        "• Indicadores diários por sistema: <b>IVU</b> (volume útil, %), <b>ITV30</b> (tendência, p.p./30 d), <b>IAP90</b> (chuva de 90 d, % da média), "
        "<b>IAF90</b> (afluência, % da MLT), <b>BH30</b> (balanço, hm³), <b>AUT</b> (autonomia, dias) e <b>IRH</b> (índice integrado 0–100).", base))

    E.append(Paragraph("Resultados dos modelos (Cantareira; teste fora da amostra 2021–2026)", h))
    dados = [
        ["Tarefa", "Modelo", "Resultado no teste", "Referência (baseline)"],
        ["Regressão: volume em 60 d", "Random Forest", f"MAE {_fmt(rf60['MAE'])} p.p. (regime < 40 %: {_fmt(rf60['MAE quando V(t+h)<40'])})",
         f"Persistência {_fmt(pe60['MAE'])} · Climatologia {_fmt(cl60['MAE'])} · Ridge {_fmt(reg[(60, 'Ridge')]['MAE'])}"],
        ["Classificação: V(t+60) < 40 %", "Random Forest", f"Recall {_fmt(rfc['recall'], 2)} · Precisão {_fmt(rfc['precisão'], 2)} · F2 {_fmt(rfc['F2'], 2)}",
         f"Transições (V ≥ 40 % hoje): recall {_fmt(rft['recall'], 2)}, precisão {_fmt(rft['precisão'], 2)}; persistência: recall 0"],
        ["Antecedência", "Random Forest", f"Alertou as 4 entradas abaixo de 40 %: {ant_txt} dias antes", "Regressão logística: 14–44 dias"],
        ["Regra de alerta (" + regra[:1] + ")", "faixa + modelos",
         f"Sub-alerta {_fmt(100 * val_te[regra]['sub-alerta (emitido < real em t+60)'])} % dos dias",
         f"Só volume atual: {_fmt(100 * val_te['A: só volume atual']['sub-alerta (emitido < real em t+60)'])} %"],
    ]
    cel = ParagraphStyle("c", parent=base, fontSize=6.9, leading=8.2, alignment=0)
    celh = ParagraphStyle("ch", parent=cel, fontName="DVB", textColor=colors.white)
    dados = [[Paragraph(x, celh if i == 0 else cel) for x in linha] for i, linha in enumerate(dados)]
    t = Table(dados, colWidths=[3.4 * cm, 2.2 * cm, 6.2 * cm, 6.4 * cm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "DV", 6.9), ("FONT", (0, 0), (-1, 0), "DVB", 6.9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b3d6b")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef3f8")]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#b0bec5")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
    E.append(t)
    E.append(Paragraph("Erros mais frequentes: subestimar recuperações causadas por chuvas extremas (um erro conservador). "
                       "Acima de 60 d a incerteza é da ordem de uma faixa de alerta.", peq))

    E.append(Paragraph(f"Avaliação de risco em {r['data_referencia'][8:10]}/{r['data_referencia'][5:7]}/{r['data_referencia'][:4]}", h))
    img = raiz / "outputs" / "figuras" / "12_painel_atual.png"
    E.append(Image(str(img), width=18 * cm, height=18 * cm * 758 / 2080))
    E.append(Paragraph(
        f"<b>Cantareira: {c['NÍVEL DE ALERTA'].upper()}</b> ({_fmt(c['IVU (%)'])} %, em recuperação: +{_fmt(c['ITV30 (p.p.)'])} p.p. em 30 d). "
        f"Previsão: {_fmt(float(prev[60]['previsto_%']), 0)} % em 60 d (P10 {_fmt(float(prev[60]['P10_%']), 0)} %); "
        f"P(< 40 % em 60 d) = {_fmt(100 * r['prob_evento_60d'])} %. "
        f"<b>Alto Tietê ({_fmt(painel['Alto Tietê']['IVU (%)'])} %) e Rio Claro ({_fmt(painel['Rio Claro']['IVU (%)'])} %)</b> estão em Normal, no limite da faixa de Atenção, "
        f"e tiveram mínimos abaixo de 20 % há menos de um ano. SIM: {_fmt(painel['SIM (Integrado)']['IVU (%)'])} % (Normal).", base))

    E.append(Paragraph("Recomendações para a gestão (sujeitas à avaliação dos gestores)", h))
    E.append(Paragraph(
        "1) Manter o Cantareira em <b>acompanhamento intensificado</b> até o fim da estação chuvosa, com meta de referência acima de 60 % em março/2027; "
        "reavaliar se o IAP90 ficar abaixo de 80 % entre dezembro e fevereiro. 2) Monitorar de perto o Alto Tietê e o Rio Claro. "
        "3) Acompanhar semanalmente o IAP90, o IAF90 e o BH30, que mudam semanas antes do volume. "
        "4) Como a captação atual exige chuva acima da média, avaliar medidas estruturais (perdas, reúso, novos mananciais). "
        "5) Recalibrar anualmente os limiares dos modelos e auditar os alertas emitidos.", base))
    E.append(Spacer(1, 2))
    E.append(Paragraph(
        "<b>Supervisão humana:</b> os níveis de alerta são recomendações para avaliação dos gestores competentes. "
        "Não confirmam uma crise e não autorizam restrições ou racionamento, que exigem análise e validação humana. "
        "Os dados são públicos e agregados, sem dados pessoais. Limitações: poucos eventos de crise (~5 em 26 anos), dados não consistidos, "
        "não estacionariedade climática e operacional.", peq))

    doc = SimpleDocTemplate(str(destino), pagesize=A4, leftMargin=1.4 * cm, rightMargin=1.4 * cm,
                            topMargin=1.1 * cm, bottomMargin=0.9 * cm,
                            title="Síntese Executiva – GS2026-2 DSA", author="Equipe GS2026-2")
    doc.build(E)
    return destino


if __name__ == "__main__":
    print(gerar(Path(__file__).resolve().parents[1]))
