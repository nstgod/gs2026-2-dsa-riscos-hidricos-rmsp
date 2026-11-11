# GS 2026-2 — Data Science and Analytics
## Monitoramento e previsão de riscos hídricos na RMSP

**Integrantes:** Pedro Luis Tofoli (RM 564441) · Raphael Talarico Nascimento Silva (RM 565219) · Nelson Troccoli Santos Neto (RM 562815)

Entrega na **Opção 1**: Jupyter Notebook reprodutível e já executado, acompanhado da síntese executiva de 1 página.

| Entregável | Arquivo |
|---|---|
| Notebook executado (código, resultados, gráficos e interpretações) | `GS2026-2_DSA_Riscos_Hidricos_RMSP.ipynb` |
| Síntese executiva (1 página) | `Sintese_Executiva_GS2026-2.pdf` |

### Estrutura
```
src/coleta.py      coleta das APIs públicas (Sabesp Portal dos Mananciais e SP Águas/SIBH), com cache
src/analise.py     preparação, indicadores (IVU, ITV, IAP, IAF, BH, AUT, IRH), dataset e níveis de alerta
src/sintese.py     gera a síntese executiva em PDF a partir de outputs/resultados.json
data/raw/          dados brutos baixados (csv.gz + metadados da coleta)
data/processed/    série diária tratada e indicadores diários por sistema
outputs/           figuras, painel de alertas atual (csv) e resultados (json)
```

### Como reproduzir
```bash
pip install -r requirements.txt
```
```bash
jupyter nbconvert --to notebook --execute GS2026-2_DSA_Riscos_Hidricos_RMSP.ipynb --inplace
```
Os dados em `data/raw/` (coletados em 05/11/2026, com dados até 04/11/2026) garantem os mesmos resultados. Para baixar dados novos das APIs, use `ATUALIZAR_DADOS = True` na primeira célula de código.

### Fontes de dados
- Sabesp — Portal dos Mananciais: https://mananciais.sabesp.com.br/base-dados (API `/api/v4/elementos/{id}/dados/{param}/diario/{ini}/{fim}`)
- SP Águas — SIBH: https://apps.spaguas.sp.gov.br/sibh/ (API `/sibh/api/v1/measurements/grouped`)
