"""
Funcoes de preparacao, indicadores, modelagem e alertas usadas no notebook
GS2026-2 - Monitoramento e previsao de riscos hidricos na RMSP.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# Niveis de alerta
# --------------------------------------------------------------------------
# Faixas de operacao do Sistema Cantareira definidas pela Resolucao Conjunta
# ANA/DAEE n. 925/2017 (volume util acumulado, %):
#   Faixa 1 Normal   >= 60 | Faixa 2 Atencao 40-60 | Faixa 3 Alerta 30-40
#   Faixa 4 Restricao 20-30 | Faixa 5 Especial < 20
# Aqui as faixas 4 e 5 sao agrupadas em "Critico". Para os demais sistemas os
# mesmos limiares sao usados como referencia (nao sao regra regulatoria).
NIVEIS = ["Normal", "Atenção", "Alerta", "Crítico"]
CORES_NIVEIS = {"Normal": "#2e7d32", "Atenção": "#f9a825",
                "Alerta": "#ef6c00", "Crítico": "#c62828"}
LIMIARES = [(60, "Normal"), (40, "Atenção"), (30, "Alerta"), (-np.inf, "Crítico")]


def nivel_por_volume(v: float) -> str | float:
    if pd.isna(v):
        return np.nan
    for lim, nome in LIMIARES:
        if v >= lim:
            return nome
    return "Crítico"


def nivel_idx(nome) -> int:
    return NIVEIS.index(nome)


# --------------------------------------------------------------------------
# Preparacao
# --------------------------------------------------------------------------
def formato_largo(bruto: pd.DataFrame) -> pd.DataFrame:
    """Formato longo (sistema, variavel, data, valor) -> uma linha por sistema/dia,
    com calendario diario completo (dias ausentes viram NaN explicitamente)."""
    w = bruto.pivot_table(index=["sistema", "data"], columns="variavel",
                          values="valor", aggfunc="first")
    partes = []
    for sis, g in w.groupby(level=0):
        g = g.droplevel(0).sort_index()
        g = g.reindex(pd.date_range(g.index.min(), g.index.max(), freq="D"))
        g.index.name = "data"
        g.insert(0, "sistema", sis)
        partes.append(g)
    return pd.concat(partes).reset_index()


def detectar_quebras(d: pd.DataFrame, tol: float = 0.01) -> pd.DatetimeIndex:
    """Detecta mudancas da capacidade util implicita (hm3 / %) - indicam
    redefinicao metodologica do volume util (ex.: inclusao de reservatorios)."""
    cap = (d["volume_hm3"] / (d["volume_pct"] / 100)).where(d["volume_pct"].abs() > 5)
    cap = cap.rolling(5, center=True, min_periods=3).median().ffill()
    var = cap.pct_change(fill_method=None).abs()
    datas = var[var > tol].index
    # agrupa dias consecutivos (uma quebra por evento)
    if len(datas) == 0:
        return datas
    eventos = [datas[0]]
    for dt in datas[1:]:
        if (dt - eventos[-1]).days > 10:
            eventos.append(dt)
    return pd.DatetimeIndex(eventos)


def _clim_mensal(serie: pd.Series) -> pd.Series:
    """Preenche lacunas de uma climatologia mensal (constante no mes) com a
    mediana do mesmo mes do ano em outros anos."""
    return serie.groupby(serie.index.month).transform(lambda s: s.fillna(s.median()))


# --------------------------------------------------------------------------
# Indicadores
# --------------------------------------------------------------------------
HM3_POR_M3S_DIA = 86400 / 1e6  # 1 m3/s durante 1 dia = 0,0864 hm3


def calcular_indicadores(d: pd.DataFrame) -> pd.DataFrame:
    """d: serie diaria de UM sistema, indexada por data."""
    d = d.sort_index()
    o = pd.DataFrame(index=d.index)
    o["IVU"] = d["volume_pct"]                           # %
    o["volume_hm3"] = d["volume_hm3"]
    for k in (7, 30, 90):
        o[f"ITV{k}"] = d["volume_pct"].diff(k)           # p.p. em k dias

    # ---- chuva -----------------------------------------------------------
    if "chuva_mm" in d and d["chuva_mm"].notna().any():
        clim = _clim_mensal(d["chuva_media_hist_mm"]) / d.index.days_in_month
        for k in (30, 90, 180, 365):
            o[f"chuva{k}"] = d["chuva_mm"].rolling(k, min_periods=int(k * 0.9)).sum()
        for k in (90, 180):
            esperado = clim.rolling(k, min_periods=int(k * 0.9)).sum()
            o[f"IAP{k}"] = 100 * o[f"chuva{k}"] / esperado   # % da media historica
    else:
        for c in ["chuva30", "chuva90", "chuva180", "chuva365", "IAP90", "IAP180"]:
            o[c] = np.nan

    # ---- vazoes ----------------------------------------------------------
    mlt = _clim_mensal(d["vazao_natural_mlt_m3s"])
    for k in (30, 90):
        obs = d["vazao_natural_m3s"].rolling(k, min_periods=int(k * 0.9)).mean()
        ref = mlt.rolling(k, min_periods=int(k * 0.9)).mean()
        o[f"IAF{k}"] = 100 * obs / ref                     # % da MLT
    jus = d["vazao_jusante_m3s"].fillna(0) if "vazao_jusante_m3s" in d else 0
    saldo = (d["vazao_afluente_m3s"] - d["vazao_captada_m3s"] - jus) * HM3_POR_M3S_DIA
    o["BH30"] = saldo.rolling(30, min_periods=27).sum()   # hm3 em 30 dias
    o["BH90"] = saldo.rolling(90, min_periods=81).sum()
    o["captada30"] = d["vazao_captada_m3s"].rolling(30, min_periods=27).mean()

    # ---- autonomia ------------------------------------------------------
    deficit_dia = (-o["BH30"] / 30).where(o["BH30"] < 0)
    aut = d["volume_hm3"].clip(lower=0) / deficit_dia
    o["AUT"] = aut.clip(upper=730)                         # dias (NaN = sem deficit)

    doy = d.index.dayofyear
    o["sin_doy"] = np.sin(2 * np.pi * doy / 365.25)
    o["cos_doy"] = np.cos(2 * np.pi * doy / 365.25)
    return o


def ecdf_rank(ref: pd.Series, x: pd.Series) -> pd.Series:
    r = np.sort(ref.dropna().values)
    if len(r) == 0:
        return pd.Series(np.nan, index=x.index)
    v = np.searchsorted(r, x.values, side="right") / len(r)
    return pd.Series(np.where(x.isna(), np.nan, v), index=x.index)


PESOS_IRH = {"IVU": 0.45, "IAP90": 0.20, "IAF90": 0.20, "ITV30": 0.15}


def calcular_irh(ind: pd.DataFrame, ref_ini="2001-01-01", ref_fim="2020-12-31") -> pd.Series:
    """Indice integrado de Risco Hidrico (0-100). Cada componente vira um
    escore de risco = 100 x (1 - percentil empirico) no periodo de referencia
    do proprio sistema; valores baixos de volume, chuva, afluencia e tendencia
    representam risco alto. Componentes ausentes tem o peso redistribuido."""
    ref = ind.loc[ref_ini:ref_fim]
    num = pd.Series(0.0, index=ind.index)
    den = pd.Series(0.0, index=ind.index)
    for comp, p in PESOS_IRH.items():
        if comp not in ind or ind[comp].isna().all():
            continue
        esc = 100 * (1 - ecdf_rank(ref[comp], ind[comp]))
        ok = esc.notna()
        num[ok] += p * esc[ok]
        den[ok] += p
    return (num / den).where(den > 0)


# --------------------------------------------------------------------------
# Dataset de modelagem
# --------------------------------------------------------------------------
FEATURES = ["IVU", "ITV7", "ITV30", "ITV90", "chuva30", "chuva90", "chuva180",
            "chuva365", "IAP90", "IAP180", "IAF30", "IAF90", "BH30", "BH90",
            "captada30", "sin_doy", "cos_doy"]


def montar_dataset(ind: pd.DataFrame, horizonte: int, quebras=(), limiar=40.0,
                   janela_hist: int = 365) -> pd.DataFrame:
    """Alvos: volume em t+h, variacao (t+h - t) e evento binario V(t+h) < limiar.
    Remove amostras cuja janela [t-365, t+h] cruza uma quebra metodologica."""
    ds = ind[FEATURES].copy()
    futuro = ind["IVU"].shift(-horizonte)
    ds["y_vol"] = futuro
    ds["y_delta"] = futuro - ind["IVU"]
    ds["y_evento"] = (futuro < limiar).astype(float).where(futuro.notna())
    ds["data_alvo"] = ds.index + pd.Timedelta(days=horizonte)
    ok = pd.Series(True, index=ds.index)
    for q in quebras:
        ok &= ~((ds.index >= q - pd.Timedelta(days=horizonte)) &
                (ds.index < q + pd.Timedelta(days=janela_hist)))
    return ds[ok]


def dividir_temporal(ds: pd.DataFrame, horizonte: int,
                     fim_treino="2016-12-31", fim_val="2020-12-31"):
    """Divisao cronologica com embargo: o alvo (t+h) nunca invade o bloco seguinte."""
    ft, fv = pd.Timestamp(fim_treino), pd.Timestamp(fim_val)
    h = pd.Timedelta(days=horizonte)
    tr = ds[(ds.index + h) <= ft]
    va = ds[(ds.index > ft) & ((ds.index + h) <= fv)]
    te = ds[ds.index > fv]
    return tr, va, te
