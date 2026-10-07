"""Saúde por UF e Brasil: leitos SUS, esperança de vida e mortes evitáveis (5 a 74 anos).

- Leitos de internação SUS por mil habitantes — CNES via TabNet (cnes/cnv/leiintbr.def),
  competência DEZEMBRO de cada ano, "Quantidade SUS"; população: projeção IBGE revisão 2024
  (a mesma que etl/fontes/datasus.py usa via TabNet), lida direto do arquivo do IBGE. Leitos complementares (UTI/UCI) ficam
  fora desta consulta desde 2010 (nota do próprio TabNet).
- Esperança de vida ao nascer — IBGE, Projeções da População revisão 2024, tabela 4
  ("Indicadores implícitos", coluna e0_T), que traz Brasil e as 27 UFs ano a ano. As tábuas
  completas de mortalidade anuais do IBGE só cobrem o Brasil (e batem com esta tabela: 76,4
  anos em 2023); por UF o dado oficial anual é este, coerente com a população usada nos
  denominadores do portal.
- Óbitos por causas evitáveis de 5 a 74 anos por 100 mil hab., PADRONIZADOS POR IDADE —
  SIM via TabNet (sim/cnv/evitb10uf.def, grupos 1.1 a 1.5 da Lista de causas evitáveis:
  imunoprevenção, doenças infecciosas, doenças não transmissíveis, causas maternas e causas
  externas), pela UF de residência. Padronização direta: taxa de cada faixa etária (TabNet)
  ÷ população da faixa (projeção IBGE), ponderada pela estrutura etária de 5 a 74 anos do
  Brasil em 2022 (ano do Censo) — assim UFs mais velhas e mais jovens ficam comparáveis.

Ficou DE FORA a cobertura da Atenção Primária (e-Gestor AB): o relatório público é um
formulário JSF com estado de sessão (sem endereço estável para baixar) e a série mudou de
método em 2020–2021 (Previne Brasil; depois nova "cobertura APS"), de modo que a janela
consistente (2012–2020) acabaria em 2020.

Anos: de 2012 em diante, só anos encerrados. O último ano do SIM é marcado "preliminar".
"""
import datetime as dt
import functools
import html
import re

from etl.comum import UFS, baixar
from etl.fontes.datasus import CGI, _corpo, _link, _uf, poisson_ic95
from etl.fontes.inep import _ler_xlsx

ANO_INICIAL = 2012
DEF_LEITOS = "cnes/cnv/leiintbr.def"
DEF_EVIT = "sim/cnv/evitb10uf.def"
_FTP = "https://ftp.ibge.gov.br/Projecao_da_Populacao/Projecao_da_Populacao_2024/"
IBGE_PROJ = _FTP + "projecoes_2024_tab4_indicadores.xlsx"
IBGE_POP = _FTP + "projecoes_2024_tab2_grupo_quinquenal.xlsx"
IBGE_PAGINA = ("https://www.ibge.gov.br/estatisticas/sociais/populacao/"
               "9109-projecao-da-populacao.html")
ANO_PADRAO = 2022          # estrutura etária-padrão (Brasil) da taxa de mortes evitáveis
CAUSAS_EVITAVEIS = ["1", "2", "3", "4", "5"]  # 1.1 a 1.5; fora: mal definidas e demais


def _anos() -> range:
    return range(ANO_INICIAL, dt.date.today().year)


_FORMS = {}


def _tabnet(deffile: str, linha: str, coluna: str, incremento: str, arquivos: list[str],
            filtros: dict[str, list[str]] | None = None):
    """POST no TabNet clássico. Devolve ({uf: {rótulo_coluna: número}}, sha256, url).
    Filtros aceitam várias categorias (pares repetidos, como o formulário envia)."""
    if deffile not in _FORMS:  # o formulário só muda quando entra arquivo novo: 1x por coleta
        _FORMS[deffile] = baixar("saude", _link(deffile), ext="html")[0].decode("latin-1")
    form = _FORMS[deffile]
    disponiveis = set(re.findall(r'VALUE="([^"]+\.dbf)"', form))
    faltam = [a for a in arquivos if a not in disponiveis]
    if faltam:
        raise RuntimeError(f"saude: {deffile} sem os arquivos {faltam}")
    filtros = filtros or {}
    pares = [("Linha", linha), ("Coluna", coluna), ("Incremento", incremento)]
    pares += [("Arquivos", a) for a in arquivos]
    for s in re.findall(r'NAME="(S[^"]+)"', form):
        pares += [(s, v) for v in filtros.get(s, ["TODAS_AS_CATEGORIAS__"])]
    pares += [("formato", "prn"), ("mostre", "Mostra")]

    url = f"{CGI}/tabcgi.exe?{deffile}"
    bruto, sha = baixar("saude", url, dados=_corpo(pares), ext="html")
    pagina = bruto.decode("latin-1")
    pre = re.search(r"<PRE>(.*?)</PRE>", pagina, re.S | re.I)
    if not pre:
        texto = re.sub(r"<[^>]+>", " ", pagina)
        raise RuntimeError(f"saude: TabNet sem tabela em {deffile}: {texto[:300]}")
    linhas = [html.unescape(l).strip() for l in pre.group(1).splitlines() if ";" in l]
    cab = [c.strip('" ') for c in linhas[0].split(";")]
    tabela = {}
    for l in linhas[1:]:
        cel = [c.strip('" ') for c in l.split(";")]
        uf = _uf(cel[0])
        if uf:
            tabela[uf] = {k: (0 if v in ("-", "") else int(v)) for k, v in zip(cab[1:], cel[1:])}
    if len(tabela) != 28:
        raise RuntimeError(f"saude: {deffile} não trouxe 27 UFs + Brasil")
    return tabela, sha, url


def _linha(ind, uf, ano, valor, sha, url, status=""):
    return dict(indicador=ind, uf=uf, periodo=str(ano), inicio=f"{ano}-01-01",
                fim=f"{ano}-12-31", valor=valor, sha256=sha, url=url, status=status, ic95=None)


@functools.cache
def _populacao():
    """IBGE, Projeção da População revisão 2024, tabela 2 (grupos quinquenais, ambos os sexos):
    ({(uf, ano): {(idade_ini, idade_fim): pop}}, sha256). É a mesma projeção que o TabNet
    (ibge/cnv/projpop2024uf.def) republica; lida na fonte para não fazer 14 consultas."""
    corpo, sha = baixar("saude", IBGE_POP, ext="xlsx")
    tab = next(iter(_ler_xlsx(corpo).values()))
    i_cab = next(i for i, l in enumerate(tab) if l and l[0] == "GRUPO ETÁRIO")
    cab = tab[i_cab]
    j_sexo, j_sigla = cab.index("SEXO"), cab.index("SIGLA")
    cols = {int(c): j for j, c in enumerate(cab) if isinstance(c, float)}
    validas = set(UFS.values()) | {"BR"}
    pop = {}
    for l in tab[i_cab + 1:]:
        if len(l) <= j_sigla or l[j_sexo] != "Ambos" or l[j_sigla] not in validas:
            continue
        m = re.fullmatch(r"\s*(\d+)-(\d+)\s*", str(l[0]))
        grupo = (int(m.group(1)), int(m.group(2))) if m else (90, 999)  # " 90+"
        for ano, j in cols.items():
            if ano in _anos() and j < len(l) and isinstance(l[j], float):
                pop.setdefault((l[j_sigla], ano), {})[grupo] = l[j]
    if len({u for u, _ in pop}) != 28 or any(len(g) != 19 for g in pop.values()):
        raise RuntimeError("saude: projeção IBGE (tab. 2) fora do formato esperado")
    return pop, sha


# ------------------------------------------------------------------ leitos SUS
def _leitos() -> list[dict]:
    grupos, sha_pop = _populacao()
    pop = {k: sum(g.values()) for k, g in grupos.items()}
    anos = list(_anos())
    tab, sha, url = _tabnet(DEF_LEITOS, "Unidade_da_Federação", "Ano/mês_compet.",
                            "Quantidade_SUS", [f"ltbr{a % 100:02d}12.dbf" for a in anos])
    linhas = []
    for uf, cols in tab.items():
        for rot, n in cols.items():
            m = re.fullmatch(r"(\d{4})/Dez", rot)
            if m and pop.get((uf, int(m.group(1)))):
                ano = int(m.group(1))
                linhas.append(_linha("leitos_sus", uf, ano, round(1000 * n / pop[(uf, ano)], 3),
                                     f"{sha},{sha_pop}", f"{url} ; {IBGE_POP}"))
    return linhas


# ------------------------------------------------------------------ esperança de vida
def _esperanca_vida() -> list[dict]:
    corpo, sha = baixar("saude", IBGE_PROJ, ext="xlsx")
    abas = _ler_xlsx(corpo)
    tab = next(v for k, v in abas.items() if "INDICADORES" in k.upper())
    i_cab = next(i for i, l in enumerate(tab) if "e0_T" in l)
    cab = tab[i_cab]
    j_ano, j_sigla, j_e0 = cab.index("ANO"), cab.index("SIGLA"), cab.index("e0_T")
    validas = set(UFS.values()) | {"BR"}
    linhas = []
    for l in tab[i_cab + 1:]:
        if len(l) <= j_e0 or not isinstance(l[j_ano], float) or l[j_sigla] not in validas:
            continue
        ano = int(l[j_ano])
        if ano in _anos() and isinstance(l[j_e0], float):
            linhas.append(_linha("esperanca_vida", l[j_sigla], ano, round(l[j_e0], 2), sha,
                                 IBGE_PROJ))
    if len({l["uf"] for l in linhas}) != 28:
        raise RuntimeError("saude: projeção IBGE não trouxe 27 UFs + Brasil")
    return linhas


# ------------------------------------------------------------------ mortes evitáveis
def _faixa(rotulo: str):
    m = re.fullmatch(r"(\d+) a (\d+) anos", rotulo.strip())
    return (int(m.group(1)), int(m.group(2))) if m else None


def _agrupar(pop_q: dict, faixas: list) -> dict:
    """Soma os grupos quinquenais da projeção dentro de cada faixa do SIM (ex.: 20 a 29)."""
    saida = {}
    for ini, fim in faixas:
        partes = [v for (a, b), v in pop_q.items() if a >= ini and b <= fim]
        cobre = sum(b - a + 1 for (a, b) in pop_q if a >= ini and b <= fim)
        if cobre != fim - ini + 1:
            raise ValueError(f"saude: faixa {ini}-{fim} não é soma de grupos quinquenais")
        saida[(ini, fim)] = sum(partes)
    return saida


def _evitaveis() -> list[dict]:
    anos = list(_anos())
    grupos, sha_pop = _populacao()
    padrao = None
    linhas = []
    for ano in anos:
        obitos, sha, url = _tabnet(DEF_EVIT, "Unidade_da_Federação", "Faixa_Etária",
                                   "Óbitos_p/Residênc", [f"evitbuf{ano % 100:02d}.dbf"],
                                   {"SCausas_evitáveis": CAUSAS_EVITAVEIS})
        faixas = sorted({f for cols in obitos.values() for k in cols if (f := _faixa(k))})
        if faixas[0][0] != 5 or faixas[-1][1] != 74:
            raise ValueError(f"saude: faixas inesperadas no SIM {ano}: {faixas}")
        if padrao is None:
            br = _agrupar(grupos[("BR", ANO_PADRAO)], faixas)
            total = sum(br.values())
            padrao = {f: v / total for f, v in br.items()}
        for uf, cols in obitos.items():
            p = _agrupar(grupos[(uf, ano)], faixas)
            taxa = sum(padrao[f] * cols.get(f"{f[0]} a {f[1]} anos", 0) / p[f] for f in faixas)
            # IC 95%: erro relativo de Poisson da contagem bruta (5 a 74 anos) aplicado à
            # taxa padronizada
            n = sum(cols.get(f"{f[0]} a {f[1]} anos", 0) for f in faixas)
            valor = round(100_000 * taxa, 1)
            linhas.append(dict(_linha("obitos_evitaveis", uf, ano, valor,
                                      f"{sha},{sha_pop}", f"{url} ; {IBGE_POP}",
                                      "preliminar" if ano == anos[-1] else ""),
                               ic95=float(f"{100_000 * taxa * poisson_ic95(n) / n:.4g}")
                               if n else None))
    return linhas


# ------------------------------------------------------------------ contrato
def coletar() -> list[dict]:
    linhas = _leitos()
    linhas += _esperanca_vida()
    linhas += _evitaveis()
    return linhas


def catalogo() -> dict:
    return {
        "leitos_sus": dict(
            nome="Leitos de internação do SUS por mil habitantes", unidade="por mil hab.",
            melhor="maior", area="Saúde", freq="anual", variacao="pct", escopo="uf", casas=2,
            origem="Ministério da Saúde — CNES (DATASUS)", link=_link(DEF_LEITOS),
            descricao="Leitos de internação disponíveis ao SUS (públicos e conveniados) em "
                      "dezembro de cada ano, por mil habitantes. Não inclui leitos "
                      "complementares (UTI e unidades intermediárias), que o CNES publica em "
                      "outra tabela. O pico de 2020–2021 reflete leitos abertos para a "
                      "covid-19. Mais leitos não significa, sozinho, melhor atendimento: "
                      "depende de ocupação, equipe e distribuição no território. População: "
                      "projeção IBGE revisão 2024."),
        "esperanca_vida": dict(
            nome="Esperança de vida ao nascer", unidade="anos", melhor="maior", area="Saúde",
            freq="anual", variacao="abs", escopo="uf", casas=1,
            origem="IBGE — Projeções da População (revisão 2024)", link=IBGE_PAGINA,
            descricao="Quantos anos, em média, viveria quem nasce no ano se as taxas de "
                      "mortalidade daquele ano se mantivessem. Valores do IBGE para cada UF, "
                      "estimados na Projeção da População revisão 2024 (com base no Censo 2022 "
                      "e nos registros de óbitos); para o Brasil, coincidem com as Tábuas "
                      "Completas de Mortalidade anuais. A queda de 2020–2021 é o efeito da "
                      "covid-19. É uma estimativa demográfica, não uma contagem: a série "
                      "inteira pode ser revista quando o IBGE publicar nova revisão da "
                      "projeção."),
        "obitos_evitaveis": dict(
            nome="Mortes evitáveis de 5 a 74 anos (taxa padronizada)",
            unidade="por 100 mil hab. de 5 a 74 anos", melhor="menor", area="Saúde",
            freq="anual", variacao="pct", escopo="uf", casas=1,
            origem="Ministério da Saúde — SIM (DATASUS)", link=_link(DEF_EVIT),
            descricao="Óbitos de pessoas de 5 a 74 anos por causas consideradas evitáveis "
                      "pela ação do SUS e de outras políticas (vacinação, prevenção e "
                      "tratamento de doenças infecciosas e crônicas, atenção à gestante, "
                      "prevenção de acidentes e violências), segundo a Lista Brasileira de "
                      "Causas Evitáveis, por 100 mil habitantes da mesma idade. A taxa é "
                      "padronizada por idade (estrutura etária do Brasil em 2022), para que "
                      "estados mais velhos não pareçam piores só por terem mais idosos. "
                      "Atenção: a lista de causas evitáveis é anterior à covid-19, e a taxa "
                      "quase não sobe em 2020–2021, o que indica que as mortes por covid não "
                      "estão nesses grupos — para o efeito da pandemia, veja a esperança de vida. "
                      "O último ano é preliminar. Cálculo do portal a partir do "
                      "SIM e da projeção de população do IBGE."),
    }
