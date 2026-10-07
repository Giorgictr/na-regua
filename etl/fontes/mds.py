"""MDS — Bolsa Família / Auxílio Brasil e Cadastro Único, mensal por UF.

Fonte: base MI Social da SAGI/MDS (a mesma por trás do VIS DATA 3), servida por um
Solr público em https://aplicacoes.mds.gov.br/sagi/servicos/misocial/ com uma linha por
município e mês. Uma única consulta com facetas JSON soma os municípios por mês e por UF;
o total Brasil é a soma de todos os municípios do mês.

Nomes do programa: Bolsa Família até out/2021; Auxílio Brasil de nov/2021 a fev/2023
(campos pab_*, somando o Benefício Extraordinário que completava R$ 400 e, a partir de
ago/2022, R$ 600); novo Bolsa Família desde mar/2023.
"""
import json
import urllib.parse

from etl.comum import NOME_UF, baixar

SOLR = "https://aplicacoes.mds.gov.br/sagi/servicos/misocial/"
SIDRA_IPCA = "https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/2266/p/201201-209912"
ORIGEM = "MDS — SAGI, MI Social / VIS DATA"
LINK = "https://aplicacoes.mds.gov.br/sagi/vis/data3/"
UFS_VALIDAS = {k for k in NOME_UF if k != "BR"}

CAMPOS = {
    "fam": "qtd_familias_beneficiarias_bolsa_familia_i",
    "vpbf": "valor_repassado_bolsa_familia_f",
    "pfam": "pab_qtd_fam_benef_i",
    "pval": "pab_valor_pago_d",
    "pext": "pab_extraordinario_valor_pago_d",
    "cadpob": "cadun_qtd_familias_cadastradas_pobreza_pbf_i",
}


def _url() -> str:
    somas = ",".join(f'{k}:"sum({c})"' for k, c in CAMPOS.items())
    faceta = ('{m:{type:terms,field:anomes_s,limit:2000,sort:"index asc",facet:{%s,'
              'u:{type:terms,field:sigla_uf,limit:40,facet:{%s}}}}}' % (somas, somas))
    return SOLR + "?" + urllib.parse.urlencode({
        "q": "*:*", "rows": 0, "wt": "json", "fq": "anomes_s:[201201 TO 209912]",
        "json.facet": faceta})


def _ipca() -> tuple[dict[str, float], str]:
    corpo, sha = baixar("mds", SIDRA_IPCA)
    return {r["D3C"]: float(r["V"]) for r in json.loads(corpo)[1:]}, sha


def _valores(b: dict) -> dict[str, float]:
    """Indicadores de um balde (UF ou Brasil) de um mês; 0 = sem dado."""
    g = lambda k: float(b.get(k) or 0)  # noqa: E731
    return {
        "bf_familias": g("fam") + g("pfam"),        # só um dos dois programas existe por mês
        "bf_valor": g("vpbf") + g("pval") + g("pext"),
        "cadunico_pobreza": g("cadpob"),
    }


def coletar() -> list[dict]:
    url = _url()
    corpo, sha = baixar("mds", url)
    ipca, sha_i = _ipca()
    ult = max(ipca)
    base = ipca[ult]

    linhas = []
    for mes in json.loads(corpo)["facets"]["m"]["buckets"]:
        am = mes["val"]
        ano, m = int(am[:4]), int(am[4:])
        fim_dia = [31, 29 if ano % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
        comum = dict(periodo=f"{ano}-{m:02d}", inicio=f"{ano}-{m:02d}-01",
                     fim=f"{ano}-{m:02d}-{fim_dia}")
        fator = base / ipca[am] if am in ipca else None  # mês sem IPCA: valor fica de fora
        baldes = [("BR", mes)] + [(u["val"], u) for u in mes["u"]["buckets"]]
        for uf, b in baldes:
            if uf not in UFS_VALIDAS and uf != "BR":
                continue
            for ind, v in _valores(b).items():
                if v <= 0:
                    continue
                if ind == "bf_valor":
                    if fator is None:
                        continue  # não dá para pôr a preços do último IPCA sem o IPCA do mês
                    linhas.append(dict(indicador=ind, uf=uf, valor=round(v * fator / 1e6, 3),
                                       sha256=f"{sha},{sha_i}", url=f"{url} ; {SIDRA_IPCA}",
                                       **comum))
                else:
                    linhas.append(dict(indicador=ind, uf=uf, valor=v, sha256=sha, url=url,
                                       **comum))
    return linhas


def catalogo() -> dict:
    comum = dict(area="Proteção social", freq="mensal", origem=ORIGEM, link=LINK,
                 melhor="neutro", variacao="pct", escopo="uf")
    nomes = ("Bolsa Família até out/2021, Auxílio Brasil de nov/2021 a fev/2023 e novo "
             "Bolsa Família desde mar/2023")
    return {
        "bf_familias": dict(
            nome="Famílias no Bolsa Família / Auxílio Brasil", unidade="famílias",
            agregacao="media", **comum,
            descricao=f"Famílias beneficiárias no mês ({nomes}). Entre abr/2020 e out/2021 "
                      "boa parte delas recebeu o Auxílio Emergencial no lugar do benefício "
                      "regular, mas segue contada aqui como beneficiária."),
        "bf_valor": dict(
            nome="Valor pago pelo Bolsa Família / Auxílio Brasil", unidade="R$ milhões",
            agregacao="soma", **comum,
            descricao=f"Valor repassado às famílias no mês ({nomes}; inclui o Benefício "
                      "Extraordinário do Auxílio Brasil), corrigido pelo IPCA a preços do "
                      "último mês com IPCA divulgado (meses mais recentes que o último IPCA "
                      "ficam de fora até o IBGE divulgá-lo). De abr/2020 a out/2021 o valor despenca "
                      "porque o Auxílio Emergencial, pago à parte e fora desta série, "
                      "substituiu o benefício."),
        "cadunico_pobreza": dict(
            nome="Famílias em situação de pobreza no CadÚnico", unidade="famílias",
            agregacao="media", **comum,
            descricao="Famílias inscritas no Cadastro Único com renda per capita abaixo da "
                      "linha de pobreza do programa vigente no mês. A linha mudou várias "
                      "vezes (em valores nominais) e revisões cadastrais em massa geram "
                      "saltos; série a partir de ago/2012."),
    }
