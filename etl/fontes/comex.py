"""MDIC — Comex Stat: exportações e importações anuais por UF (US$ FOB).

API pública: https://api-comexstat.mdic.gov.br/ (documentação em /docs).
Duas chamadas POST /general (export e import), série anual desde 2012, detalhada
por UF. O total Brasil é a soma de todas as linhas devolvidas, incluindo
"Não Declarada" e "Exterior" (operações sem UF atribuída), que não aparecem em UF
nenhuma. Só anos completos entram: o ano corrente fica de fora até fechar.
"""
import datetime as dt
import json
import time

from etl.comum import NOME_UF, baixar

API = "https://api-comexstat.mdic.gov.br/general"
ORIGEM = "MDIC — Comex Stat"
LINK = "https://comexstat.mdic.gov.br/pt/geral"
SIGLA_POR_NOME = {v: k for k, v in NOME_UF.items() if k != "BR"}

INDICADORES = {
    "exportacoes": dict(
        nome="Exportações (US$ FOB)", melhor="neutro", variacao="pct",
        descricao="Valor anual das exportações em US$ FOB, em milhões, pela UF de origem da "
                  "mercadoria (onde foi produzida), não pela UF do exportador. Dólares "
                  "correntes, sem correção pela inflação americana: parte do crescimento é só "
                  "inflação do dólar e preço de commodities (minério, petróleo, soja), que o "
                  "governo não controla — por isso o portal não trata alta como melhora. O "
                  "total Brasil inclui operações sem UF declarada."),
    "importacoes": dict(
        nome="Importações (US$ FOB)", melhor="neutro", variacao="pct",
        descricao="Valor anual das importações em US$ FOB, em milhões, pela UF do domicílio "
                  "fiscal do importador — que pode não ser onde a mercadoria é consumida. "
                  "Dólares correntes, sem correção pela inflação americana. Importar mais não é "
                  "bom nem ruim em si (pode ser investimento em máquinas ou fraqueza da "
                  "indústria local). O total Brasil inclui operações sem UF declarada."),
    "saldo_comercial": dict(
        nome="Saldo comercial (US$ FOB)", melhor="neutro", variacao="abs",
        descricao="Exportações menos importações no ano, em US$ milhões FOB correntes. Por UF "
                  "o saldo mistura critérios diferentes (origem da mercadoria x domicílio do "
                  "importador), então compare com cautela entre estados. Saldo maior não é "
                  "necessariamente melhor: pode vir de importações em queda numa recessão; e "
                  "os valores não são corrigidos pela inflação americana."),
}


def _baixar_fluxo(fluxo: str, ate: int) -> tuple[dict, str, str]:
    corpo_post = json.dumps({
        "flow": fluxo, "monthDetail": False,
        "period": {"from": "2012-01", "to": f"{ate}-12"},
        "details": ["state"], "metrics": ["metricFOB"],
    }).encode()
    url = API
    corpo, sha = baixar("comex", url, dados=corpo_post,
                        cabecalhos={"Content-Type": "application/json"})
    valores: dict[tuple[str, str], float] = {}
    for r in json.loads(corpo)["data"]["list"]:
        ano, fob = r["year"], float(r["metricFOB"])
        valores[("BR", ano)] = valores.get(("BR", ano), 0.0) + fob
        uf = SIGLA_POR_NOME.get(r["state"])
        if uf:
            valores[(uf, ano)] = valores.get((uf, ano), 0.0) + fob
    return valores, sha, f"{url} (POST flow={fluxo})"


def coletar() -> list[dict]:
    ate = dt.date.today().year - 1  # só anos completos
    exp, sha_e, url_e = _baixar_fluxo("export", ate)
    time.sleep(11)  # a API limita a ~1 requisição a cada 10 s
    imp, sha_i, url_i = _baixar_fluxo("import", ate)

    linhas = []

    def add(ind, chave, valor, sha, url):
        uf, ano = chave
        linhas.append(dict(indicador=ind, uf=uf, periodo=ano, inicio=f"{ano}-01-01",
                           fim=f"{ano}-12-31", valor=round(valor / 1e6, 3), sha256=sha, url=url))

    for k, v in exp.items():
        add("exportacoes", k, v, sha_e, url_e)
    for k, v in imp.items():
        add("importacoes", k, v, sha_i, url_i)
    for k in exp.keys() & imp.keys():
        add("saldo_comercial", k, exp[k] - imp[k], f"{sha_e},{sha_i}", f"{url_e} ; {url_i}")
    return linhas


def catalogo() -> dict:
    return {k: dict(nome=m["nome"], unidade="US$ milhões", melhor=m["melhor"], area="Economia",
                    freq="anual", descricao=m["descricao"], origem=ORIGEM, link=LINK,
                    variacao=m["variacao"], escopo="uf")
            for k, m in INDICADORES.items()}
