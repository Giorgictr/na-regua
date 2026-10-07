"""IBGE / SIDRA — indicadores complementares (economia, educação, moradia, renda, população).

Complementa etl/fontes/ibge.py (trabalho, Gini, pobreza) sem repetir nada dele.
API pública: https://apisidra.ibge.gov.br/ (documentação em /home/ajuda).
Os brutos vão para a mesma pasta da fonte "ibge" (dados/brutos/ibge/).
A população (e o denominador do PIB per capita) é a Projeção da População do IBGE
revisão 2024, que não está no SIDRA: vem do TabNet do DATASUS (ibge/cnv/projpop2024uf.def),
pedida por POST com o mesmo corpo do formulário, como em etl/fontes/datasus.py.

PIB real (per capita e crescimento por UF): as taxas de volume das Contas Regionais não
estão no SIDRA; saem em planilhas no FTP do IBGE
(https://ftp.ibge.gov.br/Contas_Regionais/<ano>/ods/Especiais_2010_<ano>_ods.zip, tabela 1 =
PIB a preços correntes, tabela 3 = série encadeada do volume do PIB, 2010 = 100). A edição
mais recente é achada pela listagem do FTP; o .ods é lido só com a biblioteca padrão.

Ficou de fora por não haver série oficial confiável no SIDRA:
- esperança de vida por UF (o SIDRA só tem a Projeção da População revisão 2018,
  tabela 7362, que é projeção e não medição; as Tábuas Completas são só Brasil e
  saem em planilhas).
"""
import datetime as dt
import html
import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from urllib.parse import quote_plus

from etl.comum import NOME_UF, SIGLA, baixar

SIDRA = "https://apisidra.ibge.gov.br/values"
PNADC = "IBGE — PNAD Contínua anual (SIDRA)"

# Indicadores "simples": uma tabela, uma variável, classificações fixas.
# Quando há várias categorias na classificação (ex.: esgoto pós-2019), os
# valores da mesma UF/ano são somados — todos vêm do mesmo arquivo bruto.
# id: lista de trechos (tabela, variável, variável do CV ou None, classif) que juntos
# formam a série. Com CV publicado, ic95 = 1,96 × CV/100 × valor (erro amostral da PNAD).
SIMPLES = {
    "analfabetismo": dict(
        trechos=[(7113, 10267, 10268, "/c2/6794/c58/2795")],
        nome="Taxa de analfabetismo (15 anos ou mais)", unidade="%", melhor="menor",
        area="Educação", origem=PNADC, variacao="pp", escopo="uf",
        descricao="Pessoas de 15 anos ou mais que não sabem ler e escrever um bilhete simples, "
                  "em % da população dessa idade. PNAD Contínua, módulo de educação (2º "
                  "trimestre); série começa em 2016 e não há dados de 2020–2021 (pandemia)."),
    "anos_estudo": dict(
        trechos=[(7126, 3593, 3594, "/c2/6794/c58/108866")],
        nome="Média de anos de estudo (25 anos ou mais)", unidade="anos", melhor="maior",
        area="Educação", origem=PNADC, variacao="abs", escopo="uf",
        descricao="Número médio de anos de estudo das pessoas de 25 anos ou mais. PNAD "
                  "Contínua, módulo de educação; série desde 2016, sem 2020–2021. Muda devagar porque "
                  "reflete a escolaridade acumulada de gerações inteiras."),
    "nem_nem": dict(
        trechos=[(9415, 8840, 8842, "")],
        nome="Jovens de 15 a 24 anos que não estudam nem trabalham", unidade="%",
        melhor="menor", area="Educação", origem="IBGE — PNAD Contínua anual (ODS 8.6.1)",
        variacao="pp", escopo="uf",
        descricao="ODS 8.6.1 — pessoas de 15 a 24 anos não ocupadas, que não estudam e não "
                  "fazem qualificação profissional, em % da faixa etária. O recorte 15–29 anos "
                  "só existe no SIDRA para Brasil e Grandes Regiões, por isso aqui é 15–24. "
                  "Sem dados de 2020–2021 (pandemia)."),
    "escolarizacao_0a3": dict(
        trechos=[(7138, 10276, 10277, "/c2/6794/c58/99749")],
        nome="Taxa de escolarização de 0 a 3 anos (creche)", unidade="%", melhor="maior",
        area="Educação", origem=PNADC, variacao="pp", escopo="uf",
        descricao="Crianças de 0 a 3 anos que frequentam escola ou creche, em % da faixa "
                  "etária. Creche não é obrigatória; a meta do PNE é 50%. Série desde 2016, sem 2020–2021 (pandemia)."),
    "escolarizacao_4a5": dict(
        trechos=[(7138, 10276, 10277, "/c2/6794/c58/47813")],
        nome="Taxa de escolarização de 4 a 5 anos (pré-escola)", unidade="%", melhor="maior",
        area="Educação", origem=PNADC, variacao="pp", escopo="uf",
        descricao="Crianças de 4 a 5 anos que frequentam escola, em % da faixa etária. "
                  "Pré-escola é obrigatória desde 2016 (meta do PNE: 100%). Série desde 2016, sem 2020–2021 (pandemia)."),
    "frequencia_liquida_medio": dict(
        trechos=[(7141, 10282, 10283, "/c2/6794/c871/47818")],
        nome="Taxa ajustada de frequência escolar líquida no ensino médio (15 a 17 anos)",
        unidade="%", melhor="maior", area="Educação", origem=PNADC, variacao="pp",
        escopo="uf",
        descricao="Jovens de 15 a 17 anos que frequentam o ensino médio ou já o concluíram, "
                  "em % da faixa etária (indicador da meta 3 do PNE). Série desde 2016, sem 2020–2021 (pandemia)."),
    "agua_rede": dict(
        trechos=[(9468, 12953, 12954, "")],
        nome="Domicílios abastecidos pela rede geral de água", unidade="%", melhor="maior",
        area="Moradia", origem=PNADC, variacao="pp", escopo="uf",
        descricao="Domicílios em que a rede geral de distribuição é a principal forma de "
                  "abastecimento de água, em % do total. Não mede regularidade nem qualidade "
                  "da água. Série desde 2016, sem 2020–2021 (pandemia)."),
    "esgoto_rede": dict(
        trechos=[(6735, 9988, None, "/c1/6795/c11558/46290"),          # 2016–2018
                 (7192, 9988, None, "/c1/6795/c11558/47930,47931")],   # 2019+ (soma)
        nome="Domicílios com esgoto ligado à rede geral", unidade="%", melhor="maior",
        area="Moradia", origem=PNADC, variacao="pp", escopo="uf",
        descricao="Domicílios com banheiro ou sanitário cujo esgoto vai para a rede geral, "
                  "rede pluvial ou fossa ligada à rede, em % desses domicílios. De 2019 em diante "
                  "o IBGE separa 'rede geral ou pluvial' e 'fossa séptica ligada à rede' "
                  "(tabela 7192); aqui as duas são somadas para manter a série de 2016–2018 "
                  "(tabela 6735), o que pode gerar diferença de ±0,1 pp por arredondamento. "
                  "Sem dados de 2020–2021 (pandemia). Não indica se o esgoto é tratado. Sem "
                  "margem de erro: o IBGE publica o CV de cada categoria, mas não o da soma."),
    "internet_domicilios": dict(
        trechos=[(7307, 9784, 9785, "/c1/6795/c688/48534")],
        nome="Domicílios com uso de internet", unidade="%", melhor="maior", area="Moradia",
        origem=PNADC, variacao="pp", escopo="uf",
        descricao="Domicílios em que algum morador usava internet, em % do total. PNAD "
                  "Contínua, módulo de tecnologia da informação (4º trimestre); não há dado "
                  "de 2020 (pandemia)."),
    "rendimento_domiciliar_pc": dict(
        trechos=[(7533, 10816, 10817, "/c1019/49243")],
        nome="Rendimento médio mensal real domiciliar per capita", unidade="R$",
        melhor="maior", area="Renda", origem=PNADC, variacao="pct", escopo="uf",
        descricao="Rendimento domiciliar de todas as fontes (trabalho, aposentadorias, "
                  "programas sociais etc.) dividido pelos moradores, a preços médios do último "
                  "ano divulgado. Toda a série é reajustada a cada nova divulgação, então os "
                  "valores mudam de nível (não de tendência)."),
}

# Demais indicadores (montados em funções próprias abaixo).
ESPECIAIS = {
    "pib_per_capita": dict(
        nome="PIB per capita real", unidade="R$ a preços do último ano das Contas Regionais",
        casas=0, melhor="maior", area="Economia", freq="anual",
        origem="IBGE — Contas Regionais e Contas Nacionais + Projeção da População (rev. 2024)",
        variacao="pct", escopo="uf",
        link="https://www.ibge.gov.br/estatisticas/economicas/contas-nacionais/9054-contas-regionais-do-brasil.html",
        descricao="PIB real por habitante, em reais a preços do último ano publicado pelas "
                  "Contas Regionais do IBGE (na edição de 2025, preços de 2023). O nível é o PIB "
                  "a preços correntes desse ano (tabela 1 das Contas Regionais); os anos "
                  "anteriores saem dele pela série encadeada do volume do PIB de cada UF "
                  "(tabela 3, a medida oficial do crescimento real, sem efeito de preços). Para "
                  "o Brasil, a série das Contas Regionais é a das Contas Nacionais; os anos "
                  "depois da última edição regional seguem a variação em volume das Contas "
                  "Nacionais (SIDRA 6784) ou, se a conta anual ainda não saiu, a taxa "
                  "acumulada no ano das Contas Trimestrais (SIDRA 5932), marcados como "
                  "preliminares. Divide-se pela população da Projeção da População do IBGE "
                  "revisão 2024 (obtida no TabNet do DATASUS), uma única série coerente com o "
                  "Censo 2022 desde 2000 — por isso os valores diferem do PIB per capita "
                  "oficial publicado à época. Variações ao longo do tempo são, portanto, "
                  "crescimento real por habitante. Planilhas das Contas Regionais: "
                  "https://ftp.ibge.gov.br/Contas_Regionais/ (saem com ~2 anos de atraso)."),
    "pib_crescimento_uf": dict(
        nome="Crescimento real do PIB estadual", unidade="% de variação real",
        melhor="maior", area="Economia", freq="anual",
        origem="IBGE — Contas Regionais", variacao="abs", escopo="uf", leitura="media",
        link="https://ftp.ibge.gov.br/Contas_Regionais/",
        descricao="Variação em volume do PIB de cada UF em relação ao ano anterior, calculada "
                  "da série encadeada do volume do PIB das Contas Regionais do IBGE (tabela 3 "
                  "das planilhas 'Especiais', 2010 = 100). É o crescimento real da economia "
                  "do estado, sem efeito de preços e sem dividir pela população. O valor do "
                  "Brasil é o das Contas Nacionais (o mesmo da tabela). As Contas Regionais "
                  "saem com ~2 anos de atraso; para anos mais recentes do Brasil, veja o "
                  "crescimento real do PIB do Brasil."),
    "pib_variacao_br": dict(
        nome="Crescimento real do PIB do Brasil", unidade="% de variação real",
        melhor="maior", area="Economia", freq="anual",
        origem="IBGE — Contas Nacionais", variacao="abs", escopo="br", leitura="media",
        link="https://sidra.ibge.gov.br/tabela/6784",
        descricao="Variação em volume do PIB em relação ao ano anterior. Anos com Contas "
                  "Nacionais anuais vêm da tabela 6784; os mais recentes, da taxa acumulada no "
                  "ano até o 4º trimestre das Contas Trimestrais (tabela 5932), marcados como "
                  "preliminares porque ainda serão revistos quando sair a conta anual."),
    "populacao": dict(
        nome="População residente", unidade="habitantes", melhor="neutro",
        area="Demografia", freq="anual",
        origem="IBGE — Projeção da População, revisão 2024 (via DATASUS)",
        variacao="pct", escopo="uf",
        link="https://tabnet.datasus.gov.br/cgi/deftohtm.exe?ibge/cnv/projpop2024uf.def",
        descricao="População em 1º de julho segundo a Projeção da População do IBGE revisão "
                  "2024, que reconstrói toda a série desde 2000 de forma coerente com o Censo "
                  "2022 (o IBGE não publica essa revisão no SIDRA; ela é distribuída pelo "
                  "TabNet do DATASUS). É a mesma série usada como denominador no PIB per "
                  "capita e nas taxas de saúde. Difere das estimativas oficiais publicadas à "
                  "época (tabela 6579), que partiam do Censo 2010 e tinham quebras em 2013 e "
                  "2022; aqui não há essas quebras. Os anos depois de 2022 são projeção, não "
                  "contagem."),
}

TABNET = "https://tabnet.datasus.gov.br/cgi"
DEF_POP = "ibge/cnv/projpop2024uf.def"  # IBGE, Projeção da População revisão 2024


def _tabela(tabela: int, variaveis, classif: str = "", niveis: str = "n1/all/n3/all"):
    """Um arquivo bruto: {(variável, uf, período): [valores das categorias]}, sha, url.
    Valor sem dado/sigilo vira None (e a soma daquela chave não é feita)."""
    vs = ",".join(str(v) for v in variaveis)
    url = f"{SIDRA}/t/{tabela}/{niveis}/v/{vs}/p/all{classif}"
    corpo, sha = baixar("ibge", url)
    dados = json.loads(corpo)
    cab, regs = dados[0], dados[1:]
    col_terr = next(k for k, v in cab.items() if k.endswith("C") and
                    v.startswith(("Brasil", "Unidade da Federação")))
    col_per = next(k for k, v in cab.items() if k.endswith("C") and
                   v.startswith(("Trimestre", "Ano")))
    col_var = next(k for k, v in cab.items() if k.endswith("C") and v.startswith("Variável"))
    out = defaultdict(list)
    for r in regs:
        try:
            v = float(r["V"])
        except ValueError:  # '...', '-', 'X': sem dado ou sigilo
            v = None
        out[(int(r[col_var]), SIGLA[r[col_terr]], r[col_per])].append(v)
    return out, sha, url


def _serie(tabela: int, variavel: int, cv: int | None = None, classif: str = "",
           niveis: str = "n1/all/n3/all", ano_min: int = 2012):
    """{(uf, ano): (valor, ic95 ou None, sha, url)}.

    Várias categorias da mesma UF/ano são somadas (ex.: esgoto pós-2019); a soma
    incompleta não vira número, e soma não leva margem de erro (o CV de uma soma não sai
    dos CVs das partes sem a covariância)."""
    brutos, sha, url = _tabela(tabela, [variavel] + ([cv] if cv else []), classif, niveis)
    out = {}
    for (var, uf, per), vals in brutos.items():
        if var != variavel or int(per[:4]) < ano_min or None in vals:
            continue
        valor, ic95 = sum(vals), None
        cvs = brutos.get((cv, uf, per)) if cv else None
        if cvs and len(vals) == 1 and cvs[0] is not None:
            ic95 = 1.96 * cvs[0] / 100 * valor
        out[(uf, per)] = (valor, ic95, sha, url)
    return out


def _linha(ind, uf, ano, valor, sha, url, ic95=None, status=""):
    ano = int(ano)
    return dict(indicador=ind, uf=uf, periodo=str(ano), inicio=f"{ano}-01-01",
                fim=f"{ano}-12-31", valor=valor, sha256=sha, url=url, status=status, ic95=ic95)


# ------------------------------------------------------------- população (TabNet)
def _corpo(pares: list[tuple[str, str]]) -> bytes:
    """O TabNet é ISO-8859-1: nomes e valores vão codificados em latin-1."""
    return "&".join(quote_plus(k, encoding="latin-1") + "=" + quote_plus(v, encoding="latin-1")
                    for k, v in pares).encode("ascii")


def _uf_tabnet(rotulo: str) -> str | None:
    """'22 Piauí' -> 'PI'; 'Total' -> 'BR'; outras linhas -> None."""
    rotulo = rotulo.strip()
    if rotulo == "Total":
        return "BR"
    m = re.match(r"(\d{2}) ", rotulo)
    return SIGLA.get(m.group(1)) if m else None


def _populacao() -> tuple[dict, str, str]:
    """Projeção da População IBGE rev. 2024, 2012 até o último ano encerrado, pedida ao
    TabNet por POST com o mesmo corpo do formulário. Devolve ({(uf, 'ano'): hab}, sha, url)."""
    link = f"{TABNET}/deftohtm.exe?{DEF_POP}"
    form, _ = baixar("ibge", link, ext="html")
    form = form.decode("latin-1")
    disponiveis = set(re.findall(r'VALUE="(projuf\d\d\.dbf)"', form))
    arquivos = [a for a in (f"projuf{a % 100:02d}.dbf" for a in range(2012, dt.date.today().year))
                if a in disponiveis]
    pares = [("Linha", "Unidade_da_Federação"), ("Coluna", "Ano"),
             ("Incremento", "População_residente")]
    pares += [("Arquivos", a) for a in arquivos]
    pares += [(s, "TODAS_AS_CATEGORIAS__") for s in re.findall(r'NAME="(S[^"]+)"', form)]
    pares += [("formato", "prn"), ("mostre", "Mostra")]
    url = f"{TABNET}/tabcgi.exe?{DEF_POP}"
    bruto, sha = baixar("ibge", url, dados=_corpo(pares), ext="html")
    pagina = bruto.decode("latin-1")
    pre = re.search(r"<PRE>(.*?)</PRE>", pagina, re.S | re.I)
    if not pre:
        raise RuntimeError("ibge_extra: TabNet da projeção de população sem tabela")
    linhas = [html.unescape(l).strip() for l in pre.group(1).splitlines() if ";" in l]
    anos = [c.strip('" ') for c in linhas[0].split(";")[1:]]
    pop = {}
    for l in linhas[1:]:
        celulas = [c.strip('" ') for c in l.split(";")]
        uf = _uf_tabnet(celulas[0])
        if uf:
            for ano, v in zip(anos, celulas[1:]):
                if ano.isdigit() and v.isdigit():
                    pop[(uf, ano)] = int(v)
    if len({u for u, _ in pop}) != 28 or len({a for _, a in pop}) != len(arquivos):
        raise RuntimeError("ibge_extra: projeção de população incompleta")
    return pop, sha, url


# ------------------------------------------------------------- Contas Regionais (FTP)
FTP_CR = "https://ftp.ibge.gov.br/Contas_Regionais/"
_ODS = {"t": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
        "o": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
        "x": "urn:oasis:names:tc:opendocument:xmlns:text:1.0"}
_UF_POR_NOME = {nome: sigla for sigla, nome in NOME_UF.items()}


def _ler_ods(conteudo: bytes) -> list[list]:
    """Primeira planilha de um .ods (zip + content.xml): linhas de células str/float/None."""
    t, o = f"{{{_ODS['t']}}}", f"{{{_ODS['o']}}}"
    raiz = ET.fromstring(zipfile.ZipFile(io.BytesIO(conteudo)).read("content.xml"))
    tabela = next(raiz.iter(t + "table"))
    linhas = []
    for row in tabela.iter(t + "table-row"):
        cel = []
        for c in row:
            if c.tag not in (t + "table-cell", t + "covered-table-cell"):
                continue
            n = int(c.get(t + "number-columns-repeated", "1"))
            if c.get(o + "value") is not None:
                v = float(c.get(o + "value"))
            else:
                v = "".join("".join(p.itertext()) for p in c.findall("x:p", _ODS)) or None
            cel += [v] * (n if v is not None else min(n, 64))  # vazio repetido até o fim
        while cel and cel[-1] is None:
            cel.pop()
        linhas += [cel] * min(int(row.get(t + "number-rows-repeated", "1")), 2)
    return linhas


def _tabela_cr(linhas: list[list]) -> dict:
    """{(uf, ano): valor} de uma tabela das Contas Regionais (linha de anos + uma linha por
    território; Grandes Regiões e notas são ignoradas)."""
    i_anos = next(i for i, l in enumerate(linhas)
                  if sum(isinstance(c, float) and 1990 < c < 2100 for c in l) >= 5)
    anos = {j: int(c) for j, c in enumerate(linhas[i_anos]) if isinstance(c, float)}
    out = {}
    for l in linhas[i_anos + 1:]:
        uf = _UF_POR_NOME.get(str(l[0]).strip()) if l else None
        if uf:
            out.update({(uf, a): l[j] for j, a in anos.items()
                        if j < len(l) and isinstance(l[j], float)})
    if len({u for u, _ in out}) != 28:
        raise RuntimeError("ibge_extra: Contas Regionais sem 27 UFs + Brasil")
    return out


def _contas_regionais() -> tuple[dict, dict, int, str, str]:
    """Última edição das Contas Regionais no FTP do IBGE. Devolve (PIB corrente em R$ milhões
    {(uf, ano)}, volume encadeado {(uf, ano)}, último ano, sha, url do .zip)."""
    listagem, _ = baixar("ibge", FTP_CR, ext="html")
    edicoes = sorted({int(a) for a in re.findall(r'href="(\d{4})/"', listagem.decode("latin-1"))},
                     reverse=True)
    for ed in edicoes[:3]:
        pasta = f"{FTP_CR}{ed}/ods/"
        try:
            lista, _ = baixar("ibge", pasta, ext="html", tentativas=2)
        except RuntimeError:
            continue
        # séries com início até 2012 (a dos portal começa em 2012); a de referência mais nova
        inicios = [int(a) for a in re.findall(rf'href="Especiais_(\d{{4}})_{ed}_ods\.zip"',
                                              lista.decode("latin-1")) if int(a) <= 2012]
        if inicios:
            url = f"{pasta}Especiais_{max(inicios)}_{ed}_ods.zip"
            break
    else:
        raise RuntimeError("ibge_extra: nenhuma edição das Contas Regionais com planilhas .ods")
    corpo, sha = baixar("ibge", url, ext="zip")
    z = zipfile.ZipFile(io.BytesIO(corpo))
    nomes = {n.rsplit("/", 1)[-1]: n for n in z.namelist()}
    corrente = _tabela_cr(_ler_ods(z.read(nomes["tab01.ods"])))
    volume = _tabela_cr(_ler_ods(z.read(nomes["tab03.ods"])))
    # conferências: tab01 em R$ milhões e tab03 com base 100; mesma cobertura de anos
    cab1 = " ".join(str(c) for l in _ler_ods(z.read(nomes["tab01.ods"]))[:4] for c in l if c)
    cab3 = " ".join(str(c) for l in _ler_ods(z.read(nomes["tab03.ods"]))[:4] for c in l if c)
    if "1 000 000 R$" not in cab1 or "encadeada do volume" not in cab3:
        raise RuntimeError("ibge_extra: Contas Regionais mudaram de formato (tab01/tab03)")
    ultimo = max(a for _, a in volume)
    if ultimo != max(a for _, a in corrente):
        raise RuntimeError("ibge_extra: tab01 e tab03 das Contas Regionais com anos diferentes")
    return corrente, volume, ultimo, sha, url


def coletar() -> list[dict]:
    linhas = []
    for ind, m in SIMPLES.items():
        for tabela, var, cv, classif in m["trechos"]:
            casas = 2
            for (uf, ano), (v, ic, sha, url) in sorted(_serie(tabela, var, cv, classif).items()):
                linhas.append(_linha(ind, uf, ano, round(v, casas), sha, url,
                                     ic95=None if ic is None else round(ic, casas + 1)))

    pop, sha_p, url_p = _populacao()
    for (uf, ano), v in sorted(pop.items()):
        linhas.append(_linha("populacao", uf, ano, v, sha_p, url_p))

    # PIB real: Contas Regionais (nível corrente do último ano × volume encadeado).
    corrente, volume, ult, sha_cr, url_cr = _contas_regionais()
    for (uf, ano), v in sorted(volume.items()):
        ant = volume.get((uf, ano - 1))
        if ano >= 2012 and ant:
            linhas.append(_linha("pib_crescimento_uf", uf, ano, round(100 * (v / ant - 1), 2),
                                 sha_cr, url_cr))
    nivel = {}  # {(uf, ano): (PIB real em R$ do ano `ult`, sha, url, status)}
    for (uf, ano), v in volume.items():
        nivel[(uf, ano)] = (corrente[(uf, ult)] * 1e6 * v / volume[(uf, ult)],
                            sha_cr, url_cr, "")

    # Crescimento do PIB do Brasil: anual oficial + trimestral (4º tri) para anos recentes.
    anual = _serie(6784, 9810, niveis="n1/all")
    taxa_br = {}  # {ano: (variação %, sha, url, status)}
    for (uf, ano), (v, _, sha, url) in sorted(anual.items()):
        linhas.append(_linha("pib_variacao_br", uf, ano, v, sha, url))
        taxa_br[int(ano)] = (v, sha, url, "")
    anos = {a for _, a in anual}
    for (uf, per), (v, _, sha, url) in sorted(
            _serie(5932, 6563, classif="/c11255/90707", niveis="n1/all").items()):
        if per.endswith("04") and per[:4] not in anos:
            linhas.append(_linha("pib_variacao_br", uf, per[:4], v, sha, url,
                                 status="preliminar"))
            taxa_br[int(per[:4])] = (v, sha, url, "preliminar")

    # Brasil depois da última edição regional: encadeia as taxas das Contas Nacionais
    ano = ult + 1
    while ano in taxa_br:
        v0, s0, u0, st0 = nivel[("BR", ano - 1)]
        v, sha, url, st = taxa_br[ano]
        novo = sha not in s0.split(",")  # cada arquivo citado uma vez
        nivel[("BR", ano)] = (v0 * (1 + v / 100), f"{s0},{sha}" if novo else s0,
                              f"{u0} ; {url}" if novo else u0,
                              "preliminar" if "preliminar" in (st, st0) else "")
        ano += 1
    for (uf, ano), (v, sha, url, st) in sorted(nivel.items()):
        if (uf, str(ano)) in pop:
            linhas.append(_linha("pib_per_capita", uf, ano, round(v / pop[(uf, str(ano))], 0),
                                 f"{sha},{sha_p}", f"{url} ; {url_p}", status=st))
    return linhas


def catalogo() -> dict:
    cat = {k: dict(nome=m["nome"], unidade=m["unidade"], melhor=m["melhor"], area=m["area"],
                   freq="anual", descricao=m["descricao"], origem=m["origem"],
                   link=f"https://sidra.ibge.gov.br/tabela/{m['trechos'][-1][0]}",
                   variacao=m["variacao"], escopo=m["escopo"])
           for k, m in SIMPLES.items()}
    cat.update({k: dict(m) for k, m in ESPECIAIS.items()})
    return cat
