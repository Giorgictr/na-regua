"""INPE — desmatamento (PRODES) e focos de queimadas, por UF e Brasil, anual.

PRODES: arquivos JSON que alimentam o painel TerraBrasilis
(https://terrabrasilis.dpi.inpe.br/app/dashboard/deforestation/biomes/legal_amazon/rates).
  - Amazônia Legal: taxas anuais oficiais por UF (files/ratesAAAA.json; o nome muda
    a cada ano de divulgação, então procuramos o mais recente).
  - Cerrado: incrementos anuais mapeados por UF (files/data/prodes_cerrado.json),
    que no Cerrado coincidem com a taxa oficial divulgada.
  Ano PRODES = agosto a julho: '2024' = 01/08/2023 a 31/07/2024 (periodo = ano em que
  o ciclo TERMINA; inicio/fim vêm das datas do próprio arquivo).
  Taxa estimada x consolidada: o painel marca o ano cuja taxa ainda é a estimativa
  (divulgada em nov.) na constante BARCHART_PRELIMINARY_DATA_YEAR do seu JavaScript
  (app.<hash>.js, guardado como bruto). Esse ano sai com status 'preliminar'. O painel
  só aplica a marca à Amazônia; no Cerrado o arquivo de incrementos já é o mapeamento,
  sem taxa estimada à parte. Em out/2026 a constante é null: 2025 já está consolidado
  (5.731 km², contra 5.796 km² da estimativa de nov/2025).

Queimadas: CSVs anuais do satélite de referência, Brasil inteiro, um zip por ano
(dataserver-coids.inpe.br, ~5–10 MB cada); contamos focos por UF.
"""
import csv
import datetime as dt
import io
import json
import re
import unicodedata
import urllib.request
import zipfile

from etl.comum import NOME_UF, baixar

PRODES = "https://terrabrasilis.dpi.inpe.br/app/prodes/dashboard/deforestation/files"
QUEIMADAS = ("https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/anual/"
             "Brasil_sat_ref/")
ANO_MIN = 2012

_CAVEAT_PRODES = (
    "O ano PRODES vai de agosto a julho (o valor de '2024' cobre ago/2023–jul/2024). "
    "O dado do ano mais recente costuma sair primeiro como taxa estimada (preliminar) e é "
    "revisado quando o mapeamento é consolidado. ")

CATALOGO = {
    "desmatamento_amazonia": dict(
        nome="Desmatamento na Amazônia Legal (PRODES)", unidade="km²",
        origem="INPE — PRODES",
        link="https://terrabrasilis.dpi.inpe.br/app/dashboard/deforestation/biomes/"
             "legal_amazon/rates",
        descricao="Taxa anual de corte raso da floresta primária na Amazônia Legal, em km². "
                  + _CAVEAT_PRODES +
                  "Enquanto o painel do INPE trata o último ano como estimativa, ele aparece "
                  "marcado como preliminar. Só os 9 estados da Amazônia Legal (AC, AM, AP, MA, MT, PA, RO, RR, TO) têm "
                  "dado; 'Brasil' é o total da Amazônia Legal."),
    "desmatamento_cerrado": dict(
        nome="Desmatamento no Cerrado (PRODES)", unidade="km²",
        origem="INPE — PRODES",
        link="https://terrabrasilis.dpi.inpe.br/app/dashboard/deforestation/biomes/"
             "cerrado/increments",
        descricao="Área de vegetação nativa do Cerrado suprimida no ano, em km² (série anual "
                  "desde 2013; antes era bienal). " + _CAVEAT_PRODES +
                  "No Cerrado o painel do INPE não separa estimativa de dado consolidado, "
                  "então nenhum ano é marcado preliminar, mas o mais recente ainda pode ser "
                  "revisado. Só os estados com área de Cerrado têm dado; 'Brasil' é o total do bioma."),
    "focos_queimadas": dict(
        nome="Focos de queimadas (satélite de referência)", unidade="focos",
        origem="INPE — Programa Queimadas",
        link="https://terrabrasilis.dpi.inpe.br/queimadas/situacao-atual/estatisticas/"
             "estatisticas_estados/",
        descricao="Número de focos de calor detectados no ano civil pelo satélite de "
                  "referência do INPE (AQUA, passagem da tarde), que mantém a série comparável "
                  "ao longo do tempo. Foco não é área queimada: um incêndio grande pode gerar "
                  "vários focos, e nuvens ou fumaça escondem outros. O ano corrente só entra "
                  "quando o INPE publica o arquivo anual fechado."),
}


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn").upper().strip()


SIGLA_POR_NOME = {_sem_acento(nome): sig for sig, nome in NOME_UF.items() if sig != "BR"}


def _existe(url: str) -> bool:
    """Só para descobrir qual arquivo anual existe; o download em si passa por baixar()."""
    try:
        req = urllib.request.Request(url, method="HEAD", headers={
            "User-Agent": "portal-indicadores-sociais (+github)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200
    except Exception:
        return False


def _linha(ind, uf, ano_fim, ini, fim, valor, sha, url, status=""):
    return dict(indicador=ind, uf=uf, periodo=str(ano_fim), inicio=ini, fim=fim,
                valor=float(valor), sha256=sha, url=url, status=status)


PAINEL = "https://terrabrasilis.dpi.inpe.br/app/dashboard/deforestation/"


def _ano_estimado() -> int | None:
    """Ano PRODES cuja taxa ainda é estimada, segundo o próprio painel TerraBrasilis
    (BARCHART_PRELIMINARY_DATA_YEAR; null = nenhum). Falha de rede -> erro: sem saber,
    não dá para afirmar que o último ano é consolidado."""
    pagina, _ = baixar("ambiente", PAINEL + "biomes/legal_amazon/rates", ext="html")
    js = re.search(r'src="(/app/dashboard/deforestation/app\.[0-9a-f]+\.js)"',
                   pagina.decode("utf-8", "replace"))
    if not js:
        raise RuntimeError("ambiente: não achei o app.js do painel PRODES")
    corpo, _ = baixar("ambiente", "https://terrabrasilis.dpi.inpe.br" + js.group(1), ext="js")
    m = re.search(r'"BARCHART_PRELIMINARY_DATA_YEAR",\{get:function\(\)\{return\s*([^}]+?)\}',
                  corpo.decode("utf-8", "replace"))
    if not m:
        raise RuntimeError("ambiente: painel PRODES sem BARCHART_PRELIMINARY_DATA_YEAR")
    ano = re.search(r"\d{4}", m.group(1))
    return int(ano.group()) if ano else None


def _prodes(ind: str, url_dados: str, url_nomes: str, estimado: int | None = None) -> list[dict]:
    """Lê o formato do painel PRODES (periods -> features com loi=1 = UF)."""
    corpo_n, _ = baixar("ambiente", url_nomes)
    ufs = next(l for l in json.loads(corpo_n)["lois"] if l["gid"] == 1)["loinames"]
    gid_sigla = {u["gid"]: SIGLA_POR_NOME[_sem_acento(u["loiname"])] for u in ufs}

    corpo, sha = baixar("ambiente", url_dados)
    linhas = []
    for p in json.loads(corpo)["periods"]:
        a, b = p["startDate"], p["endDate"]
        if b["year"] - a["year"] != 1 or b["year"] < ANO_MIN:  # pula acumulado e bienais
            continue
        ini = f"{a['year']}-{a['month']:02d}-{a['day']:02d}"
        fim = f"{b['year']}-{b['month']:02d}-{b['day']:02d}"
        por_uf = {s: 0.0 for s in gid_sigla.values()}  # UF do bioma sem feição = 0
        for f in p["features"]:
            if f["loi"] != 1:
                continue
            area = sum(x["area"] for x in f["areas"] if x["type"] == 1)
            por_uf[gid_sigla[f["loiname"]]] += area
        st = "preliminar" if b["year"] == estimado else ""
        for uf, v in por_uf.items():
            linhas.append(_linha(ind, uf, b["year"], ini, fim, round(v, 2), sha, url_dados, st))
        linhas.append(_linha(ind, "BR", b["year"], ini, fim, round(sum(por_uf.values()), 2),
                             sha, url_dados, st))
    return linhas


def _amazonia() -> list[dict]:
    ano = dt.date.today().year
    for a in range(ano + 1, 2023, -1):
        url = f"{PRODES}/rates{a}.json"
        if _existe(url):
            break
    else:
        raise RuntimeError("ambiente: não achei o arquivo de taxas PRODES Amazônia Legal")
    return _prodes("desmatamento_amazonia", url,
                   f"{PRODES}/config/loinames/prodes_legal_amazon.json", _ano_estimado())


def _cerrado() -> list[dict]:
    return _prodes("desmatamento_cerrado", f"{PRODES}/data/prodes_cerrado.json",
                   f"{PRODES}/config/loinames/prodes_cerrado.json")


def _queimadas() -> list[dict]:
    indice, _ = baixar("ambiente", QUEIMADAS, ext="html")
    anos = sorted({int(a) for a in re.findall(r'href="focos_br_ref_(\d{4})\.zip"',
                                               indice.decode("utf-8", "replace"))})
    linhas = []
    for ano in (a for a in anos if a >= ANO_MIN):
        url = f"{QUEIMADAS}focos_br_ref_{ano}.zip"
        corpo, sha = baixar("ambiente", url, ext="zip")
        z = zipfile.ZipFile(io.BytesIO(corpo))
        nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        cont = {s: 0 for s in SIGLA_POR_NOME.values()}
        with z.open(nome) as f:
            leitor = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
            col = next(c for c in leitor.fieldnames if c.strip().lower() == "estado")
            colpais = next((c for c in leitor.fieldnames if c.strip().lower() == "pais"), None)
            for r in leitor:
                if colpais and _sem_acento(r[colpais]) != "BRASIL":
                    continue
                uf = SIGLA_POR_NOME.get(_sem_acento(r[col]))
                if uf:
                    cont[uf] += 1
        ini, fim = f"{ano}-01-01", f"{ano}-12-31"
        for uf, n in cont.items():
            linhas.append(_linha("focos_queimadas", uf, ano, ini, fim, n, sha, url))
        linhas.append(_linha("focos_queimadas", "BR", ano, ini, fim, sum(cont.values()),
                             sha, url))
    return linhas


def coletar() -> list[dict]:
    return _amazonia() + _cerrado() + _queimadas()


def catalogo() -> dict:
    return {k: dict(nome=m["nome"], unidade=m["unidade"], melhor="menor",
                    area="Meio ambiente", freq="anual", descricao=m["descricao"],
                    origem=m["origem"], link=m["link"], variacao="pct", escopo="uf")
            for k, m in CATALOGO.items()}
