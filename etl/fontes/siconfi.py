"""Tesouro Nacional / SICONFI — contas públicas dos 27 governos estaduais.

API pública: https://apidatalake.tesouro.gov.br/ords/siconfi/tt/
(documentação em https://apidatalake.tesouro.gov.br/docs/siconfi/).

Fontes usadas, sempre do Poder Executivo estadual (esfera E, id_ente = código IBGE da UF):
- DCA (Declaração de Contas Anuais), Anexo I-E (despesa por função) e I-D (por natureza):
  despesa LIQUIDADA no ano, 2014 em diante. Os percentuais por função usam como
  denominador a "Despesa exceto intraorçamentária" — o mesmo total do RREO Anexo 2.
  A população dos valores por habitante é a Projeção da População do IBGE revisão 2024
  (TabNet do DATASUS, ibge/cnv/projpop2024uf.def — a mesma de etl/fontes/ibge_extra.py e
  datasus.py, pedida pela mesma função), e não a que o SICONFI anexa à declaração (estimativa
  defasada, que repete anos e salta: RJ −4,9% em 2024). Os valores por habitante são
  corrigidos pela média anual do IPCA (SIDRA 1737) para reais do último ano completo; essas
  linhas levam hash e URL dos três arquivos (DCA, população e IPCA).
  Campo "status" não é preenchido: estados podem retificar qualquer exercício, não só o último.
- RREO do 6º bimestre, Anexo 14 (demonstrativo simplificado): % da receita de impostos
  aplicado em saúde (ASPS) e em educação (MDE), 2015 em diante. Os anexos completos 8 e 12
  do RREO não estão na API; o Anexo 14 não traz a base de cálculo, então vale o percentual
  declarado (com correção de escala e descarte de valores impossíveis — ver _rreo).
- RGF do 3º quadrimestre do Poder Executivo, Anexo 6 (simplificado; se faltar, Anexos 2 e 1):
  Dívida Consolidada Líquida / RCL e despesa com pessoal do Executivo / RCL, 2015 em diante,
  recalculados a partir dos valores em R$ do próprio demonstrativo (ver _rgf).

A União fica de fora de propósito: a despesa total federal inclui o refinanciamento da
dívida (o que encolhe qualquer participação por função), os pisos de saúde e educação e
os limites de pessoal e de dívida da União seguem regras diferentes. Pôr um número
federal ao lado dos estaduais induziria comparação falsa.
"""
import datetime as dt
import json
import re
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from etl.comum import UFS, baixar
from etl.fontes.ibge_extra import _populacao

API = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"
ORIGEM = "Tesouro Nacional — SICONFI"
LINK = "https://siconfi.tesouro.gov.br/"
ANO_DCA, ANO_RREO_RGF = 2014, 2015
PAUSA = 0.3  # segundos entre chamadas de cada linha de execução (3 em paralelo)

FUNCOES = {  # código da função (Portaria 42/1999) -> (sufixo do id, nome)
    "10": ("saude", "Saúde"),
    "12": ("educacao", "Educação"),
    "06": ("seguranca", "Segurança Pública"),
    "13": ("cultura", "Cultura"),
    "08": ("assistencia", "Assistência Social"),
    "17": ("saneamento", "Saneamento"),
    "19": ("ciencia", "Ciência e Tecnologia"),
}

_LIQ = ("despesa liquidada no ano (DCA, Anexo I-E), sem as operações intraorçamentárias "
        "(repasses entre órgãos do próprio governo, que contariam o gasto duas vezes)")


def _meta_funcoes():
    m = {}
    for cod, (suf, nome) in FUNCOES.items():
        m[f"desp_{suf}_pct"] = dict(
            nome=f"Despesa com {nome} (% da despesa)", unidade="% da despesa",
            melhor="neutro", variacao="pp",
            descricao=f"Parcela da despesa do governo estadual classificada na função {cod} "
                      f"– {nome}: {_LIQ}, dividida pelo total da despesa nas mesmas bases. "
                      "Mais não é necessariamente melhor: a parcela cai quando outras despesas "
                      "(previdência, dívida) crescem.")
        m[f"desp_{suf}_pc"] = dict(
            nome=f"Despesa com {nome} por habitante",
            unidade="R$ por habitante, a preços do último ano", melhor="neutro", variacao="pct",
            descricao=f"Despesa liquidada na função {cod} – {nome} (DCA, Anexo I-E) dividida "
                      "pela população da Projeção da População do IBGE revisão 2024 (obtida no "
                      "TabNet do DATASUS; a mesma série usada no PIB per capita e nas taxas de "
                      "saúde), corrigida pela média anual do IPCA (IBGE, tabela 1737) para "
                      "reais do último ano completo do IPCA. Não usa a população que o SICONFI "
                      "anexa à declaração, que é uma estimativa defasada (repete anos e tem "
                      "saltos artificiais).")
    return m


INDICADORES = {
    **_meta_funcoes(),
    "desp_investimentos_pct": dict(
        nome="Investimentos (% da despesa)", unidade="% da despesa", melhor="neutro",
        variacao="pp",
        descricao="Despesa liquidada no grupo 4 – Investimentos (obras, equipamentos) dividida "
                  "pela despesa total liquidada, incluindo intraorçamentárias (DCA, Anexo I-D)."),
    "aplic_saude_pct": dict(
        meta=12,
        nome="Aplicação em saúde (% da receita de impostos)",
        unidade="% da receita de impostos", melhor="neutro", variacao="pp",
        descricao="Despesa em ações e serviços públicos de saúde paga com recursos de impostos e "
                  "transferências, em % dessa receita, como declarado pelo próprio estado no RREO "
                  "do 6º bimestre (Anexo 14). Mínimo constitucional dos estados: 12% (LC 141/2012)."),
    "aplic_mde_pct": dict(
        meta=25,
        nome="Aplicação em educação – MDE (% da receita de impostos)",
        unidade="% da receita de impostos", melhor="neutro", variacao="pp",
        descricao="Despesa com manutenção e desenvolvimento do ensino em % da receita de impostos "
                  "e transferências, como declarado no RREO do 6º bimestre (Anexo 14). Mínimo "
                  "constitucional: 25% (art. 212 da Constituição); algumas constituições "
                  "estaduais exigem mais (SP, 30%)."),
    "dcl_rcl": dict(
        limite=200,
        nome="Dívida consolidada líquida (% da RCL)", unidade="% da RCL", melhor="menor",
        variacao="pp",
        descricao="Dívida consolidada líquida (dívida menos caixa e haveres) em 31/12, em % da "
                  "receita corrente líquida (RGF do 3º quadrimestre, Anexo 6). Limite para os "
                  "estados: 200% da RCL (Resolução 40/2001 do Senado). Valor negativo = haveres "
                  "maiores que a dívida."),
    "pessoal_rcl": dict(
        limite=49,
        nome="Despesa com pessoal do Executivo (% da RCL)", unidade="% da RCL", melhor="menor",
        variacao="pp",
        descricao="Despesa total com pessoal do Poder Executivo estadual nos 12 meses, em % da "
                  "receita corrente líquida (RGF do 3º quadrimestre, Anexo 6). Limite da LRF para "
                  "o Executivo estadual: 49% (prudencial 46,55%); somando todos os poderes, o "
                  "limite do estado é 60%. Os critérios de cálculo de cada estado variaram e "
                  "foram uniformizados pelo Tesouro a partir de 2020–2021."),
}


def _url(recurso: str, params: dict) -> str:
    return f"{API}/{recurso}?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


def _consulta(recurso: str, params: dict) -> list[tuple[dict, str, str]]:
    """Todas as páginas de uma consulta -> [(item, sha256, url_da_página)]."""
    saida, offset = [], 0
    while True:
        p = dict(params, **({"offset": offset} if offset else {}))
        url = _url(recurso, p)
        for tentativa in range(4):  # a API devolve 429 quando apertada: espera e tenta de novo
            try:
                corpo, sha = baixar("siconfi", url, ext="json")
                break
            except RuntimeError as e:
                if "429" not in str(e) or tentativa == 3:
                    raise
                time.sleep(60 * (tentativa + 1))
        time.sleep(PAUSA)
        dados = json.loads(corpo)
        itens = dados.get("items", [])
        saida += [(i, sha, url) for i in itens]
        if not dados.get("hasMore") or not itens:
            return saida
        offset += len(itens)


def _linha(ind, sigla, ano, valor, sha, url):
    return dict(indicador=ind, uf=sigla, periodo=str(ano), inicio=f"{ano}-01-01",
                fim=f"{ano}-12-31", valor=round(float(valor), 4), sha256=sha, url=url)


def _dca(cod: int, sigla: str, ano: int) -> list[dict]:
    linhas = []
    base = {"an_exercicio": ano, "id_ente": cod}
    # Anexo I-E: despesa por função
    itens = [x for x in _consulta("dca", {**base, "no_anexo": "DCA-Anexo I-E"})
             if x[0].get("coluna") == "Despesas Liquidadas"]
    total, funcoes = None, {}
    for i, sha, url in itens:
        conta = (i.get("conta") or "").strip()
        if re.match(r"^Despesas \(?Exceto Intra", conta, re.I):
            total = (i["valor"], sha, url)
        m = re.match(r"^(\d{2}) - ", conta)
        if m:
            funcoes.setdefault(m.group(1), []).append((i["valor"], sha, url))
    if total and total[0] > 0:
        dup = [k for k, v in funcoes.items() if len(v) > 1]
        soma = sum(v[0][0] for v in funcoes.values())
        if dup or abs(soma - total[0]) > 0.005 * total[0]:
            print(f"[siconfi] {sigla} {ano} DCA I-E inconsistente (duplicadas={dup}, "
                  f"soma funções/total={soma / total[0]:.4f}); ignorado", file=sys.stderr)
        else:
            for f, (suf, _) in FUNCOES.items():
                v, sha, url = funcoes[f][0] if f in funcoes else (0.0, total[1], total[2])
                linhas.append(_linha(f"desp_{suf}_pct", sigla, ano, 100 * v / total[0], sha, url))
                # R$ totais por ora; _por_habitante divide pela população do IBGE
                linhas.append(_linha(f"desp_{suf}_pc", sigla, ano, v, sha, url))

    # Anexo I-D: investimentos (GND 4) / despesa total geral
    itens = [x for x in _consulta("dca", {**base, "no_anexo": "DCA-Anexo I-D"})
             if x[0].get("coluna") == "Despesas Liquidadas"]
    tot = next((x for x in itens if (x[0].get("conta") or "").startswith("Total Geral")), None)
    inv = [x for x in itens if re.match(r"^4\.4\.00\.00\.00(\.00)? - Investimentos",
                                        x[0].get("conta") or "")]
    if tot and tot[0]["valor"] > 0 and len(inv) == 1:
        linhas.append(_linha("desp_investimentos_pct", sigla, ano,
                             100 * inv[0][0]["valor"] / tot[0]["valor"], inv[0][1], inv[0][2]))
    return linhas


def _rreo(cod: int, sigla: str, ano: int) -> list[dict]:
    """% aplicado em MDE e em saúde, como o próprio estado declarou no Anexo 14.

    Alguns estados (ex.: AP) preenchem os percentuais como fração (0,17 em vez de 17); isso se
    detecta pela linha "% Mínimo a Aplicar" do mesmo quadro (0,12 / 0,25 em vez de 12 / 25),
    e aí o valor é multiplicado por 100. Percentual fora de 0–100 é erro de digitação na
    declaração (ex.: RO 2017, MDE = 2606,59) e é descartado."""
    itens = _consulta("rreo", {"an_exercicio": ano, "nr_periodo": 6,
                               "co_tipo_demonstrativo": "RREO", "no_anexo": "RREO-Anexo 14",
                               "id_ente": cod})
    aplicado, minimo = {}, {}
    for i, sha, url in itens:
        txt = (i.get("cod_conta") or "") + " " + (i.get("conta") or "")
        if "FUNDEB" in txt.upper():
            continue
        if re.search(r"ManutencaoEDesenvolvimentoDoEnsino|Manutenção e Desenvolvimento do Ensino",
                     txt):
            ind = "aplic_mde_pct"
        elif re.search(r"Saude|Saúde", txt):
            ind = "aplic_saude_pct"
        else:
            continue
        col = i.get("coluna") or ""
        if col.startswith("% Aplicado"):
            aplicado.setdefault(ind, (i["valor"], sha, url))
        elif col.startswith("% Mínimo"):
            minimo.setdefault(ind, i["valor"])
    linhas = []
    for ind, (v, sha, url) in aplicado.items():
        if v is None:
            continue
        if 0 < v < 1.5 and (minimo.get(ind) is None or 0 < minimo[ind] < 1):
            v = 100 * v
        if 0 < v <= 100:
            linhas.append(_linha(ind, sigla, ano, v, sha, url))
        else:
            print(f"[siconfi] {sigla} {ano} {ind}: {v} fora de 0–100; descartado", file=sys.stderr)
    return linhas


def _rgf(cod: int, sigla: str, ano: int) -> list[dict]:
    """DCL/RCL e pessoal/RCL do Executivo, recalculados a partir dos valores em R$ do próprio RGF.

    O percentual declarado às vezes vem como fração (AP: 0,41) ou com erro de digitação
    (RS 2019: DCL = 22.437%). Por isso o valor publicado é numerador / denominador (ambos do
    mesmo arquivo); o percentual declarado só é usado quando confere com essa conta ou quando
    faltam os valores. Fonte preferida: Anexo 6 (simplificado); se faltar, Anexo 2 / Anexo 1."""
    base = {"an_exercicio": ano, "in_periodicidade": "Q", "nr_periodo": 3,
            "co_tipo_demonstrativo": "RGF", "co_poder": "E", "id_ente": cod}
    linhas = _rgf_de(_consulta("rgf", {**base, "no_anexo": "RGF-Anexo 06"}), sigla, ano)
    if len(linhas) < 2:  # falta algo no simplificado: baixa o RGF inteiro (Anexos 1 e 2)
        linhas = _rgf_de(_consulta("rgf", base), sigla, ano)
    return linhas


def _rgf_de(itens, sigla, ano):
    def um(anexo, contas, coluna):
        """Primeiro cod_conta de `contas` com exatamente uma linha no anexo/coluna."""
        for c in contas:
            ach = [x for x in itens if x[0].get("anexo") == anexo and x[0].get("cod_conta") == c
                   and (x[0].get("coluna") or "").upper().startswith(coluna.upper())
                   and x[0].get("valor") is not None]
            if len(ach) == 1:  # mais de um (vários órgãos) = ambíguo, não usa
                return ach[0]
        return None

    rcl_div = ["ReceitaCorrenteLiquidaAjustadaParaCalculoDosLimitesDeEndividamento"
               "DemonstrativoSimplificado", "ReceitaCorrenteLiquida"]
    regras = {  # indicador: [(anexo, numerador, denominadores, %declarado, coluna R$, coluna %)]
        "dcl_rcl": [
            ("RGF-Anexo 06", ["DividaConsolidadaLiquidaDemonstrativoSimplificado"], rcl_div,
             ["DividaConsolidadaLiquidaDemonstrativoSimplificado"], "VALOR", "% SOBRE"),
            ("RGF-Anexo 02", ["DividaConsolidadaLiquida"],
             ["ReceitaCorrenteLiquidaAjustadaParaCalculoDosLimitesDeEndividamento",
              "RGF2ReceitaCorrenteLiquida"], ["PercentualDaDCLSobreARCL"],
             "Até o 3º Quadrimestre", "Até o 3º Quadrimestre")],
        "pessoal_rcl": [
            ("RGF-Anexo 06", ["DespesaTotalComPessoalDemonstrativoSimplificado"],
             ["ReceitaCorrenteLiquidaAjustada", "ReceitaCorrenteLiquida"],
             ["DespesaTotalComPessoalDemonstrativoSimplificado"], "VALOR", "% SOBRE"),
            ("RGF-Anexo 01", ["DespesaComPessoalTotal"],
             ["ReceitaCorrenteLiquidaAjustada", "ReceitaCorrenteLiquidaLimiteLegal"],
             ["DespesaComPessoalTotal"], "VALOR", "% SOBRE")],
    }
    linhas = []
    for ind, fontes in regras.items():
        for anexo, num, dens, pct, col_rs, col_pct in fontes:
            n = um(anexo, num, col_rs)
            d = um(anexo, dens, col_rs) or um(anexo, dens, "VALOR")  # RCL: "Valor Até o Quadr."
            p = um(anexo, pct, col_pct)
            calc = 100 * n[0]["valor"] / d[0]["valor"] if n and d and d[0]["valor"] > 0 else None
            decl = p[0]["valor"] if p else None
            if calc is not None:
                v = decl if decl is not None and abs(decl - calc) <= max(0.5, 0.01 * abs(calc)) \
                    else calc
                if v is calc and decl is not None:
                    print(f"[siconfi] {sigla} {ano} {ind}: declarado {decl}, recalculado "
                          f"{calc:.2f} ({anexo})", file=sys.stderr)
                linhas.append(_linha(ind, sigla, ano, v, n[1], n[2]))
                break
            if decl is not None and decl >= 1.5:  # sem valores em R$ para conferir
                linhas.append(_linha(ind, sigla, ano, decl, p[1], p[2]))
                break
    return linhas


IPCA = "https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/2266/p/all"


def _ipca() -> tuple[dict, str, str]:
    """Média anual do número-índice IPCA (só anos com os 12 meses) -> ({ano: média}, sha, url)."""
    corpo, sha = baixar("siconfi", IPCA, ext="json")
    meses = {}
    for r in json.loads(corpo)[1:]:
        try:
            meses.setdefault(int(r["D3C"][:4]), []).append(float(r["V"]))
        except ValueError:
            continue
    return {a: sum(v) / 12 for a, v in meses.items() if len(v) == 12}, sha, IPCA


def _por_habitante(linhas: list[dict]) -> list[dict]:
    """*_pc: R$ nominais totais -> R$ por habitante (Projeção da População IBGE rev. 2024) do
    último ano completo do IPCA; hash e URL das três fontes (DCA, população, IPCA)."""
    media, sha_i, url_i = _ipca()
    pop, sha_p, url_p = _populacao()
    ref = media[max(media)]
    saida = []
    for l in linhas:
        if l["indicador"].endswith("_pc"):
            ano, hab = int(l["periodo"]), pop.get((l["uf"], l["periodo"]))
            if ano not in media or not hab:
                continue  # ano ainda sem IPCA completo ou sem população
            l = dict(l, valor=round(l["valor"] / hab * ref / media[ano], 4),
                     sha256=f"{l['sha256']},{sha_p},{sha_i}",
                     url=f"{l['url']} ; {url_p} ; {url_i}")
        saida.append(l)
    return saida


def coletar() -> list[dict]:
    ultimo = dt.date.today().year - 1  # DCA sai em abril/maio; RREO 6º bim. e RGF em jan/fev
    tarefas = [(fn, cod, sigla, ano)
               for cod, sigla in UFS.items()
               for fn, ini in ((_dca, ANO_DCA), (_rreo, ANO_RREO_RGF), (_rgf, ANO_RREO_RGF))
               for ano in range(ini, ultimo + 1)]
    linhas, falhas = [], []

    def rodar(t):
        fn, cod, sigla, ano = t
        try:
            return fn(cod, sigla, ano)
        except Exception as e:  # uma UF/ano fora do ar não derruba as outras
            falhas.append((fn.__name__, sigla, ano, str(e)))
            return []

    with ThreadPoolExecutor(max_workers=3) as ex:
        for r in ex.map(rodar, tarefas):
            linhas += r
    for f in falhas:
        print(f"[siconfi] falhou {f}", file=sys.stderr)
    if len(falhas) > 0.2 * len(tarefas):
        raise RuntimeError(f"siconfi: {len(falhas)} de {len(tarefas)} consultas falharam")
    return _por_habitante(linhas)


def catalogo() -> dict:
    return {k: dict(nome=m["nome"], unidade=m["unidade"], melhor=m["melhor"],
                    area="Contas públicas", freq="anual", descricao=m["descricao"],
                    origem=ORIGEM, link=LINK, variacao=m["variacao"], escopo="uf",
                    **{c: m[c] for c in ("meta", "limite") if c in m})
            for k, m in INDICADORES.items()}
