"""
Coleta de dados reais para o projeto GS 2026-2 - Data Science and Analytics
"Monitoramento e previsao de riscos hidricos na RMSP".

Fontes:
  1) Portal dos Mananciais - Sabesp (https://mananciais.sabesp.com.br/base-dados)
     API publica usada pelo proprio portal:
       GET /api/v4/elementos/{idElemento}/dados/{idParametro}/diario/{inicio}/{fim}
  2) SIBH - Sistema Integrado de Bacias Hidrograficas / SP Aguas
     (https://apps.spaguas.sp.gov.br/sibh/)
     API publica usada pelo proprio portal:
       GET /sibh/api/v1/measurements/grouped?format=json&station_prefix_ids[]=ID
           &start_date=AAAA-MM-DD&end_date=AAAA-MM-DD&group_type=day|month

Todos os downloads sao guardados em data/raw/ (cache). Se o arquivo ja
existir, ele e reutilizado - isso garante reprodutibilidade mesmo que as APIs
fiquem indisponiveis. Para forcar nova coleta use force=True.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import requests

try:
    # O servidor da Sabesp nao envia o certificado intermediario; o truststore
    # usa o repositorio de certificados do sistema operacional (que completa a
    # cadeia), mantendo a verificacao TLS ativa.
    import truststore
    truststore.inject_into_ssl()
except ImportError:  # pragma: no cover
    pass

SABESP_API = "https://mananciais.sabesp.com.br/api/v4"
SIBH_API = "https://apps.spaguas.sp.gov.br/sibh/api/v1"
HEADERS = {"User-Agent": "GS-DSA-FIAP-academic-project/1.0"}

# Elementos espaciais do tipo "Sistema" no Portal dos Mananciais
SISTEMAS = {
    64: "Cantareira",
    65: "Alto Tietê",
    66: "Guarapiranga",
    67: "Cotia",
    68: "Rio Grande",
    69: "Rio Claro",
    72: "São Lourenço",
    75: "SIM (Integrado)",
}

# Parametros diarios publicados pela Sabesp (ids da API /api/v4/parametros)
PARAMETROS = {
    684: "volume_pct",            # Volume util armazenado (%)
    685: "volume_hm3",            # Volume util armazenado (hm3)
    1: "chuva_mm",                # Chuva diaria (mm)
    694: "chuva_media_hist_mm",   # Chuva media historica do mes (mm)
    690: "vazao_natural_m3s",     # Vazao natural (m3/s)
    698: "vazao_natural_mlt_m3s", # Vazao natural media historica do mes (m3/s)
    691: "vazao_afluente_m3s",    # Vazao afluente (m3/s)
    687: "vazao_captada_m3s",     # Vazao captada (m3/s)
    689: "vazao_jusante_m3s",     # Vazao liberada a jusante (m3/s)
}


def _get_json(url: str, params=None, tries: int = 4, timeout: int = 180):
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # rede instavel: tenta novamente
            last = exc
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"Falha ao acessar {url}: {last}")


def baixar_sabesp(raw_dir: Path, inicio: str = "2000-01-01", fim: str | None = None,
                  force: bool = False) -> pd.DataFrame:
    """Baixa as series diarias de todos os sistemas x parametros (formato longo)."""
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    destino = raw_dir / "sabesp_mananciais_diario.csv.gz"
    if destino.exists() and not force:
        return pd.read_csv(destino, parse_dates=["data"])

    if fim is None:
        fim = _get_json(f"{SABESP_API}/dados/ultima-data")["data"]

    linhas = []
    for id_sis, nome in SISTEMAS.items():
        for id_par, var in PARAMETROS.items():
            url = f"{SABESP_API}/elementos/{id_sis}/dados/{id_par}/diario/{inicio}/{fim}"
            js = _get_json(url)
            dados = (js or {}).get("data") or []
            for d in dados:
                linhas.append({
                    "id_sistema": id_sis, "sistema": nome, "id_parametro": id_par,
                    "variavel": var, "data": d["date"][:10], "valor": d["value"],
                    "is_valid": d.get("isValid"),
                })
            time.sleep(0.3)  # gentileza com o servidor
    df = pd.DataFrame(linhas)
    df["data"] = pd.to_datetime(df["data"])
    df.to_csv(destino, index=False)
    meta = {"fonte": "Portal dos Mananciais - Sabesp (API v4)", "url": SABESP_API,
            "inicio": inicio, "fim": fim, "coletado_em": pd.Timestamp.now().isoformat(),
            "sistemas": SISTEMAS, "parametros": PARAMETROS}
    (raw_dir / "sabesp_mananciais_diario.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return df


def baixar_sibh(raw_dir: Path, estacoes: dict[int, str], inicio: str = "2000-01-01",
                fim: str = "2026-11-04", group_type: str = "month",
                force: bool = False) -> pd.DataFrame:
    """Baixa chuva agregada (mensal por padrao) de postos pluviometricos do SIBH."""
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    destino = raw_dir / f"sibh_chuva_{group_type}.csv.gz"
    if destino.exists() and not force:
        return pd.read_csv(destino, parse_dates=["data"])

    linhas = []
    for id_prefixo, rotulo in estacoes.items():
        # consulta ano a ano: o servidor e lento para periodos longos
        anos = range(int(inicio[:4]), int(fim[:4]) + 1)
        for ano in anos:
            ini = max(f"{ano}-01-01", inicio)
            fi = min(f"{ano}-12-31", fim)
            params = {"format": "json", "station_prefix_ids[]": id_prefixo,
                      "start_date": ini, "end_date": fi, "group_type": group_type}
            js = _get_json(f"{SIBH_API}/measurements/grouped", params=params)
            for d in (js or {}).get("json", []):
                linhas.append({
                    "id_prefixo": id_prefixo, "posto": rotulo,
                    "prefixo": d.get("prefix"), "nome": d.get("station_name"),
                    "municipio": d.get("city"), "lat": d.get("latitude"),
                    "lon": d.get("longitude"), "data": d["date"][:10],
                    "chuva_mm": d.get("value"),
                })
            time.sleep(0.3)
    df = pd.DataFrame(linhas)
    if not df.empty:
        df["data"] = pd.to_datetime(df["data"])
    df.to_csv(destino, index=False)
    meta = {"fonte": "SIBH - SP Aguas (api v1 measurements/grouped)", "url": SIBH_API,
            "estacoes": estacoes, "inicio": inicio, "fim": fim, "group_type": group_type,
            "coletado_em": pd.Timestamp.now().isoformat()}
    (raw_dir / f"sibh_chuva_{group_type}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return df
