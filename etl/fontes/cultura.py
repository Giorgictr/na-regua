"""Cultura — Lei Rouanet (SALIC/MinC) e salas de cinema (ANCINE).

* Lei Rouanet: a API do SALIC (https://api.salic.cultura.gov.br/docs), consultada em
  /api/v1/projetos?ano_captacao=AAAA, devolve o agregado nacional do ano — valor total
  captado (pela data do recibo) e a lista de PRONACs que captaram. Esse agregado ignora
  o filtro de UF, e a lista de projetos da API só cobre os cadastrados recentemente, então
  não há corte por UF confiável: a série é só Brasil. Valores deflacionados pelo IPCA
  (SIDRA tabela 1737, média anual do número-índice) a preços do último ano completo.
* Salas de cinema: CSV "Salas de exibição — evolução anual" da ANCINE, uma linha por sala
  e ano com a situação (ABERTA, FECHADA, FECHADA TEMPORARIAMENTE). Série desde 2014.

Só anos completos entram.
"""
import csv
import datetime as dt
import io
import json

from etl.comum import NOME_UF, baixar

SALIC = "https://api.salic.cultura.gov.br/api/v1/projetos"
SIDRA_IPCA = "https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/2266/p/{ini}01-{fim}12"
SALAS = "https://dados.ancine.gov.br/dados-abertos/salas-de-exibicao-evolucao-anual.csv"
UFS_VALIDAS = {k for k in NOME_UF if k != "BR"}


def _ano_final() -> int:
    return dt.date.today().year - 1


def _ipca_medio(ate: int) -> tuple[dict[int, float], str, str]:
    url = SIDRA_IPCA.format(ini=2012, fim=ate)
    corpo, sha = baixar("cultura", url)
    soma: dict[int, list[float]] = {}
    for r in json.loads(corpo)[1:]:
        soma.setdefault(int(r["D3C"][:4]), []).append(float(r["V"]))
    return {a: sum(v) / len(v) for a, v in soma.items() if len(v) == 12}, sha, url


def _rouanet(ate: int) -> list[dict]:
    ipca, sha_i, url_i = _ipca_medio(ate)
    ate = max(ipca)  # IPCA de dezembro sai só em janeiro: deflaciona até o último ano fechado
    base = ipca[ate]
    linhas = []
    for ano in range(2012, ate + 1):
        url = f"{SALIC}?format=json&ano_captacao={ano}"
        corpo, sha = baixar("cultura", url, cabecalhos={"Accept": "application/json"})
        d = json.loads(corpo)
        if int(d["ano_captacao"]) != ano:
            raise RuntimeError(f"SALIC devolveu ano {d['ano_captacao']} para {ano}")
        comum = dict(uf="BR", periodo=str(ano), inicio=f"{ano}-01-01", fim=f"{ano}-12-31")
        real = float(d["valor_total_captado"]) * base / ipca[ano] / 1e6
        linhas.append(dict(indicador="rouanet_captacao", valor=round(real, 3),
                           sha256=f"{sha},{sha_i}", url=f"{url} ; {url_i}", **comum))
        projetos = len({p.strip() for p in d["pronac"]})
        linhas.append(dict(indicador="rouanet_projetos", valor=float(projetos),
                           sha256=sha, url=url, **comum))
    return linhas


def _salas(ate: int) -> list[dict]:
    corpo, sha = baixar("cultura", SALAS, ext="csv")
    cont: dict[tuple[str, str], int] = {}
    for r in csv.DictReader(io.StringIO(corpo.decode("utf-8-sig")), delimiter=";"):
        ano, uf = r["ANO"].strip(), r["UF"].strip().upper()
        if r["STATUS"].strip().upper() != "ABERTA" or not ano.isdigit() or int(ano) > ate:
            continue
        if uf not in UFS_VALIDAS:
            continue
        for chave in ((uf, ano), ("BR", ano)):
            cont[chave] = cont.get(chave, 0) + 1
    anos = sorted({a for _, a in cont})  # UF sem sala aberta no ano vale 0, não "sem dado"
    return [dict(indicador="salas_cinema", uf=uf, periodo=ano, inicio=f"{ano}-01-01",
                 fim=f"{ano}-12-31", valor=float(cont.get((uf, ano), 0)), sha256=sha, url=SALAS)
            for uf in sorted(UFS_VALIDAS | {"BR"}) for ano in anos]


def coletar() -> list[dict]:
    ate = _ano_final()
    return _salas(ate) + _rouanet(ate)


def catalogo() -> dict:
    ano = _ano_final()
    rouanet = dict(area="Cultura", freq="anual", origem="Ministério da Cultura — SALIC (Lei Rouanet)",
                   link="https://versalic.cultura.gov.br/", escopo="br")
    return {
        "salas_cinema": dict(
            nome="Salas de cinema em funcionamento", unidade="salas", melhor="maior",
            area="Cultura", freq="anual", variacao="pct", escopo="uf",
            origem="ANCINE — Observatório do Cinema e do Audiovisual (OCA)",
            link="https://www.gov.br/ancine/pt-br/oca/dados-abertos",
            descricao="Salas de exibição registradas na ANCINE com situação \"aberta\" no ano. "
                      "Série começa em 2014. Em 2020 a queda reflete sobretudo fechamentos "
                      "temporários da pandemia, não salas extintas."),
        "rouanet_captacao": dict(
            nome="Captação via Lei Rouanet", unidade=f"R$ milhões de {ano}", melhor="neutro",
            variacao="pct",
            descricao="Valor captado por projetos culturais via incentivo fiscal federal "
                      "(mecenato, Lei 8.313/91), pela data do recibo, corrigido pelo IPCA "
                      f"(média anual) para preços de {ano}. É renúncia fiscal decidida pelas "
                      "empresas e pessoas incentivadoras, não gasto direto do governo: cada "
                      "real captado é imposto que deixa de ser arrecadado. Mais captação "
                      "significa mais dinheiro para cultura, mas também mais renúncia, e o "
                      "governo não decide quanto se capta — por isso o portal não trata "
                      "alta como melhora nem como piora. Só há série nacional.", **rouanet),
        "rouanet_projetos": dict(
            nome="Projetos que captaram via Lei Rouanet", unidade="projetos", melhor="neutro",
            variacao="pct",
            descricao="Número de projetos culturais distintos (PRONAC) com ao menos uma "
                      "captação registrada no ano pelo mecanismo de incentivo fiscal da Lei "
                      "Rouanet. Como a captação é renúncia fiscal decidida pelos incentivadores, "
                      "o portal não trata mais projetos como melhora nem como piora. Só há "
                      "série nacional.", **rouanet),
    }
