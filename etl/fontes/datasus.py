"""Ministério da Saúde — DATASUS TabNet: SIM, SINASC, PNI e população (IBGE via TabNet).

Tudo vem de tabelas agregadas do TabNet, pedidas por POST com o mesmo corpo que o
formulário da página envia (sem planilha, sem microdados). Cada tabela traz as 27 UFs
de residência e a linha "Total" (= Brasil) para todos os anos de uma vez.

- TabNet clássico (tabcgi.exe): SIM e SINASC (um arquivo .dbf por ano), população.
  O corpo é ISO-8859-1; todo filtro S<dimensão> vai como "todas as categorias", exceto
  o grande grupo CID-10 X85-Y09 no pedido de homicídios e Y10-Y34 no de óbitos de
  intenção indeterminada.
- TabNetBD (webtabx.exe): cobertura vacinal do PNI. Os VALUEs das opções são
  descritores opacos do servidor e voltam exatamente como a página os entrega.

Taxas: cada linha cita (sha256/url, nessa ordem) o arquivo do numerador (óbitos) e o
do denominador (nascidos vivos ou população).

Anos: só de 2012 em diante e só anos encerrados (o ano corrente fica de fora, porque o
TabNet publica "prévias" parciais dele). O último ano fechado de SIM/SINASC costuma
ser preliminar: a nota da página do TabNet diz qual ("Dados de 2025 - Preliminares"),
e essas linhas saem com status 'preliminar'. Se a nota sumir/mudar de formato, o
último ano da tabela é marcado preliminar por cautela.
"""
import datetime as dt
import html
import re
from urllib.parse import quote_plus

from etl.comum import SIGLA, baixar

CGI = "https://tabnet.datasus.gov.br/cgi"
ORIGEM = "Ministério da Saúde — SIM/SINASC (DATASUS)"
ANO_INICIAL = 2012

DEF_INF = "sim/cnv/inf10uf.def"      # óbitos infantis (< 1 ano)
DEF_MAT = "sim/cnv/mat10uf.def"      # óbitos de mulheres em idade fértil / maternos
DEF_EXT = "sim/cnv/ext10uf.def"      # óbitos por causas externas
DEF_NV = "sinasc/cnv/nvuf.def"       # nascidos vivos
DEF_POP = "ibge/cnv/projpop2024uf.def"  # IBGE, Projeção da População revisão 2024
DEF_PNI = "bd_pni/cpnibr.def"        # PNI, cobertura vacinal (TabNetBD)


def _link(deffile: str) -> str:
    if deffile.startswith("bd_"):
        return f"{CGI}/dhdat.exe?{deffile}"
    return f"{CGI}/deftohtm.exe?{deffile}"


INDICADORES = {
    "mortalidade_infantil": dict(
        nome="Taxa de mortalidade infantil", unidade="por mil nascidos vivos",
        melhor="menor", area="Saúde", variacao="pct", link=_link(DEF_INF),
        descricao="Óbitos de menores de 1 ano por mil nascidos vivos no ano, pela UF de "
                  "residência da mãe (SIM ÷ SINASC, cálculo direto, sem fator de correção de "
                  "sub-registro). O último ano fechado é preliminar e ainda pode mudar."),
    "mortalidade_materna": dict(
        nome="Razão de mortalidade materna", unidade="por 100 mil nascidos vivos",
        melhor="menor", area="Saúde", variacao="pct", link=_link(DEF_MAT),
        descricao="Óbitos maternos (até 42 dias após o fim da gestação; tardios excluídos) por "
                  "100 mil nascidos vivos, cálculo direto SIM ÷ SINASC, sem o fator de "
                  "correção usado nas estimativas oficiais. Em UFs pequenas poucos casos mudam "
                  "muito a razão; 2020–2021 incluem o excesso de mortes por covid-19. O último "
                  "ano fechado é preliminar."),
    "homicidios": dict(
        nome="Taxa de homicídios", unidade="por 100 mil hab.",
        melhor="menor", area="Segurança", variacao="pct", link=_link(DEF_EXT),
        descricao="Óbitos por agressão (CID-10 X85–Y09) por 100 mil habitantes, pela UF de "
                  "residência da vítima, registrados no SIM. Não inclui intervenção legal "
                  "(Y35–Y36) nem mortes de intenção indeterminada (Y10–Y34). Atenção: a partir "
                  "de 2018–2019 muitas mortes violentas passaram a ser registradas como de "
                  "intenção indeterminada, e parte da queda dos homicídios nesses anos é "
                  "mudança de registro, não de violência (Atlas da Violência, Ipea/FBSP, "
                  "estima os 'homicídios ocultos'). O Atlas da Violência 2026 estima que os "
                  "homicídios ocultos subiram fortemente de 2023 para 2024 (+88,6%, de 3.755 "
                  "para 7.083), então a queda recente da taxa reflete em parte classificação, "
                  "não só menos violência — compare com o indicador de óbitos de intenção "
                  "indeterminada. População: projeção IBGE revisão 2024. "
                  "O último ano fechado é preliminar."),
    "obitos_intencao_indeterminada": dict(
        nome="Óbitos por causa externa de intenção indeterminada", unidade="por 100 mil hab.",
        melhor="neutro", area="Segurança", variacao="pct", link=_link(DEF_EXT),
        descricao="Óbitos por eventos cuja intenção é indeterminada (CID-10 Y10–Y34) por 100 "
                  "mil habitantes, pela UF de residência, registrados no SIM: mortes violentas "
                  "em que o atestado não diz se foi agressão, suicídio ou acidente. É o sinal "
                  "dos 'homicídios ocultos' (Atlas da Violência, Ipea/FBSP): quando esta taxa "
                  "sobe e a de homicídios cai, parte da queda pode ser só pior classificação. "
                  "Por isso não tem direção boa ou ruim: valor alto pode indicar mais "
                  "violência mal investigada, e não mais mortes. Mesmo arquivo do SIM e mesma "
                  "população (projeção IBGE revisão 2024) da taxa de homicídios. O último ano "
                  "fechado é preliminar."),
    "cobertura_triplice_viral": dict(
        nome="Cobertura vacinal — tríplice viral (1ª dose)", unidade="%",
        melhor="maior", area="Saúde", variacao="pp", link=_link(DEF_PNI),
        descricao="Doses de tríplice viral D1 aplicadas em crianças de 1 ano, em % da "
                  "população-alvo, como calculado pelo PNI. Pode passar de 100% (vacinação de "
                  "atrasados, denominador estimado). A série termina em 2022: o TabNet do PNI "
                  "não tem anos posteriores; a partir de 2023 o dado oficial está no painel "
                  "do SI-PNI/RNDS, com outra metodologia e não comparável, por isso não entra "
                  "aqui. Governos a partir de 2023 ficam sem este indicador."),
}


# --------------------------------------------------------------------------- utilidades
def _corpo(pares: list[tuple[str, str]]) -> bytes:
    """O TabNet é ISO-8859-1: nomes e valores vão codificados em latin-1."""
    return "&".join(quote_plus(k, encoding="latin-1") + "=" + quote_plus(v, encoding="latin-1")
                    for k, v in pares).encode("ascii")


def _anos_fechados() -> range:
    return range(ANO_INICIAL, dt.date.today().year)


def _uf(rotulo: str) -> str | None:
    """'22 Piauí' -> 'PI'; 'Total' -> 'BR'; outras linhas (ignorado/exterior) -> None."""
    rotulo = rotulo.strip()
    if rotulo == "Total":
        return "BR"
    m = re.match(r"(\d{2}) ", rotulo)
    return SIGLA.get(m.group(1)) if m else None


def _tabnet(deffile: str, linha: str, coluna: str, incremento: str, prefixo: str,
            filtros: dict | None = None) -> tuple[dict, str, str, set]:
    """POST no TabNet clássico. Devolve ({(uf, ano): número}, sha256, url, anos preliminares).
    `filtros`: {campo S...: (código, início do rótulo)} — o rótulo é conferido no formulário."""
    form, _ = baixar("datasus", _link(deffile), ext="html")
    form = form.decode("latin-1")
    preliminares = {int(a) for a in re.findall(r"Dados de (\d{4})\s*-\s*Preliminar", form, re.I)}
    disponiveis = set(re.findall(r'VALUE="(' + prefixo + r'\d\d\.dbf)"', form))
    arquivos = [a for a in (f"{prefixo}{a % 100:02d}.dbf" for a in _anos_fechados())
                if a in disponiveis]
    pares = [("Linha", linha), ("Coluna", coluna), ("Incremento", incremento)]
    pares += [("Arquivos", a) for a in arquivos]
    filtros = dict(filtros or {})
    for s, (v, rotulo) in filtros.items():  # confere que o código ainda é a categoria pedida
        if not re.search(rf'VALUE="{v}"\s*>\s*{re.escape(rotulo)}', form):
            raise RuntimeError(f"datasus: {deffile}: {s}={v} não é mais '{rotulo}'")
        filtros[s] = v
    pares += [(s, filtros.get(s, "TODAS_AS_CATEGORIAS__"))
              for s in re.findall(r'NAME="(S[^"]+)"', form)]
    pares += [("formato", "prn"), ("mostre", "Mostra")]

    url = f"{CGI}/tabcgi.exe?{deffile}"
    bruto, sha = baixar("datasus", url, dados=_corpo(pares), ext="html")
    pagina = bruto.decode("latin-1")
    pre = re.search(r"<PRE>(.*?)</PRE>", pagina, re.S | re.I)
    if not pre:
        texto = re.sub(r"<[^>]+>", " ", pagina)
        raise RuntimeError(f"datasus: TabNet sem tabela em {deffile}: {texto[:300]}")
    linhas = [html.unescape(l).strip() for l in pre.group(1).splitlines() if ";" in l]
    anos = [c.strip('" ') for c in linhas[0].split(";")[1:]]
    tabela = {}
    for l in linhas[1:]:
        celulas = [c.strip('" ') for c in l.split(";")]
        uf = _uf(celulas[0])
        if not uf:
            continue
        for ano, v in zip(anos, celulas[1:]):
            if ano.isdigit():
                tabela[(uf, int(ano))] = 0 if v in ("-", "") else int(v)
    if len({u for u, _ in tabela}) != 28:
        raise RuntimeError(f"datasus: {deffile} não trouxe 27 UFs + Brasil")
    if not preliminares and not deffile.startswith("ibge/"):
        preliminares = {max(a for _, a in tabela)}  # nota não achada: último ano, por cautela
    return tabela, sha, url, preliminares


def _cobertura_pni(vacina: str = "Tríplice Viral  D1") -> list[dict]:
    """TabNetBD do PNI (webtabx.exe). Atenção ao espaço duplo no rótulo da vacina."""
    form, _ = baixar("datasus", _link(DEF_PNI), ext="html")
    form = form.decode("latin-1")
    sel = {}
    for m in re.finditer(r"<select([^>]*)>(.*?)</select>", form, re.S | re.I):
        nome = re.search(r'name="([^"]*)"', m.group(1), re.I).group(1)
        if not nome.startswith("listahidden"):
            sel[nome] = re.findall(r'<option\s+value="([^"]*)"([^>]*)>([^<\r\n]*)',
                                   m.group(2), re.I)

    def opcao(campo, rotulo):
        return next(v for v, _, r in sel[campo] if r.strip() == rotulo)

    anos = set(_anos_fechados())
    pares = [("Linha", opcao("Linha", "Unidade da Federação")), ("Coluna", opcao("Coluna", "Ano")),
             ("Incremento", opcao("Incremento", vacina))]
    pares += [("PAno", v) for v, _, r in sel["PAno"] if int(r) in anos]
    pares += [(n, next(v for v, a, _ in o if "selected" in a.lower()))
              for n, o in sel.items() if n.startswith("S")]
    pares += [("nomedef", DEF_PNI), ("grafico", "")]

    url = f"{CGI}/webtabx.exe?{DEF_PNI}"
    bruto, sha = baixar("datasus", url, dados=_corpo(pares), ext="html")
    pagina = bruto.decode("latin-1")
    colunas = re.findall(r"data\.addColumn\('number','\s*([^']*)'\)", pagina)
    linhas = []
    for rotulo, corpo in re.findall(r'\["([^"]+)"\s*((?:,\{v:[^}]*\}\s*)+)\]', pagina):
        uf = _uf(rotulo)
        if not uf:
            continue
        for ano, v in zip(colunas, re.findall(r"\{v:\s*([-\d.eE]+|null)", corpo)):
            if ano.isdigit() and v != "null":
                linhas.append(_linha("cobertura_triplice_viral", uf, int(ano),
                                     round(float(v), 2), sha, url))
    if len({l["uf"] for l in linhas}) != 28:
        raise RuntimeError("datasus: PNI não trouxe 27 UFs + Brasil")
    return linhas


def _linha(ind, uf, ano, valor, sha, url, status=""):
    return dict(indicador=ind, uf=uf, periodo=str(ano), inicio=f"{ano}-01-01",
                fim=f"{ano}-12-31", valor=valor, sha256=sha, url=url, status=status)


def poisson_ic95(n: float) -> float:
    """Meia-largura do IC 95% de Poisson para a contagem n (aproximação de Byar do exato):
    (superior - inferior) / 2, na escala da contagem. n=0: [0; 3,689]."""
    if n <= 0:
        return 3.689 / 2
    inf = n * (1 - 1 / (9 * n) - 1.96 / (3 * n ** 0.5)) ** 3
    m = n + 1
    sup = m * (1 - 1 / (9 * m) + 1.96 / (3 * m ** 0.5)) ** 3
    return (sup - inf) / 2


def ic95_taxa(n: float, den: float, fator: float) -> float:
    """IC 95% (meia-largura) de fator·n/den, só com o erro de Poisson do numerador; 4 sig."""
    return float(f"{fator * poisson_ic95(n) / den:.4g}")


def _taxa(ind, num, den, fator):
    """num/den = (tabela, sha256, url, anos preliminares); cita os dois arquivos."""
    (tn, sn, un, pn), (td, sd, ud, pd) = num, den
    prelim = pn | pd
    return [dict(_linha(ind, uf, ano, round(fator * n / td[(uf, ano)], 2), f"{sn},{sd}",
                        f"{un} ; {ud}", "preliminar" if ano in prelim else ""),
                 ic95=ic95_taxa(n, td[(uf, ano)], fator))
            for (uf, ano), n in sorted(tn.items()) if td.get((uf, ano))]


# --------------------------------------------------------------------------- contrato
def coletar() -> list[dict]:
    nv = _tabnet(DEF_NV, "Unidade_da_Federação", "Ano_do_nascimento",
                 "Nascim_p/resid.mãe", "nvuf")
    pop = _tabnet(DEF_POP, "Unidade_da_Federação", "Ano", "População_residente", "projuf")

    infantis = _tabnet(DEF_INF, "Unidade_da_Federação", "Ano_do_Óbito",
                       "Óbitos_p/Residênc", "infuf")
    maternos = _tabnet(DEF_MAT, "Unidade_da_Federação", "Ano_do_Óbito",
                       "Óbitos_maternos", "matuf")
    agressoes = _tabnet(DEF_EXT, "Unidade_da_Federação", "Ano_do_Óbito",
                        "Óbitos_p/Residênc", "extuf",
                        filtros={"SGrande_Grupo_CID10": ("4", "X85-Y09")})
    indeterminados = _tabnet(DEF_EXT, "Unidade_da_Federação", "Ano_do_Óbito",
                             "Óbitos_p/Residênc", "extuf",
                             filtros={"SGrande_Grupo_CID10": ("5", "Y10-Y34")})

    linhas = []
    linhas += _taxa("mortalidade_infantil", infantis, nv, 1_000)
    linhas += _taxa("mortalidade_materna", maternos, nv, 100_000)
    linhas += _taxa("homicidios", agressoes, pop, 100_000)
    linhas += _taxa("obitos_intencao_indeterminada", indeterminados, pop, 100_000)
    linhas += _cobertura_pni()
    return linhas


def catalogo() -> dict:
    return {k: dict(nome=m["nome"], unidade=m["unidade"], melhor=m["melhor"], area=m["area"],
                    freq="anual", descricao=m["descricao"], origem=(
                        "Ministério da Saúde — PNI (DATASUS)" if k.startswith("cobertura")
                        else ORIGEM),
                    link=m["link"], variacao=m["variacao"])
            for k, m in INDICADORES.items()}
