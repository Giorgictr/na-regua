"""IBGE / SIDRA — PNAD Contínua (trabalho, renda, desigualdade, pobreza).

API pública: https://apisidra.ibge.gov.br/ (documentação em /home/ajuda).
Uma chamada por tabela traz Brasil (n1) e as 27 UFs (n3) da série inteira, com o
valor E o coeficiente de variação (CV) publicado pelo IBGE no mesmo arquivo bruto.

Erro amostral: a PNAD é uma pesquisa por amostra. Para cada valor com CV publicado,
ic95 = 1,96 × CV/100 × valor (meia-largura do intervalo de 95%, na unidade do valor),
a aproximação normal usual. O CV vem arredondado a 1 casa pelo IBGE.
"""
import json
from collections import defaultdict

from etl.comum import SIGLA, baixar

SIDRA = "https://apisidra.ibge.gov.br/values"
ORIGEM = "IBGE — PNAD Contínua (SIDRA)"

_ERRO_UF = ("É estimativa por amostra: em UFs pequenas (ex.: AP, RR, AC) a margem de erro "
            "de um trimestre passa de ±1 ponto, e diferenças menores que isso podem ser "
            "ruído. Comparações anuais usam a média dos 4 trimestres do ano.")

# id: tabela, variável, variável do CV (ou None), classificação fixa, periodicidade, metadados
INDICADORES = {
    "desocupacao": dict(
        tabela=4099, variavel=4099, cv=4103, classif="", freq="trimestral",
        nome="Taxa de desocupação", unidade="%", melhor="menor", area="Trabalho",
        descricao="Pessoas de 14 anos ou mais sem trabalho que procuraram emprego na semana "
                  "de referência, em % da força de trabalho. " + _ERRO_UF),
    "subutilizacao": dict(
        tabela=4099, variavel=4118, cv=4119, classif="", freq="trimestral",
        nome="Taxa composta de subutilização", unidade="%", melhor="menor", area="Trabalho",
        descricao="Desocupados + subocupados por insuficiência de horas + força de trabalho "
                  "potencial (quem queria trabalhar mas não procurou ou não estava "
                  "disponível), em % da força de trabalho ampliada. " + _ERRO_UF),
    "informalidade": dict(
        tabela=8529, variavel=12466, cv=12467, classif="", freq="trimestral",
        nome="Taxa de informalidade", unidade="%", melhor="menor", area="Trabalho",
        descricao="Ocupados sem carteira assinada (empregados e domésticos), empregadores e "
                  "conta própria sem CNPJ e trabalhadores familiares auxiliares, em % dos "
                  "ocupados. Série começa no 4º tri de 2015. " + _ERRO_UF),
    "nivel_ocupacao": dict(
        tabela=6466, variavel=4097, cv=4101, classif="", freq="trimestral",
        nome="Nível de ocupação", unidade="%", melhor="maior", area="Trabalho",
        descricao="Pessoas de 14 anos ou mais ocupadas (com qualquer trabalho, formal ou "
                  "informal) na semana de referência, em % de toda a população de 14 anos ou "
                  "mais. Diferente da desocupação, não depende de a pessoa estar procurando "
                  "emprego: mostra quanto da população em idade de trabalhar está de fato "
                  "trabalhando. Reflete também a estrutura etária (UFs com mais idosos tendem "
                  "a ter nível menor). " + _ERRO_UF),
    "emprego_carteira": dict(
        tabela=4097, variavel=4108, cv=4109, classif="/c11913/31722", freq="trimestral",
        nome="Empregados do setor privado com carteira assinada", unidade="% dos ocupados",
        melhor="maior", area="Trabalho",
        descricao="Empregados do setor privado com carteira de trabalho assinada (exclui "
                  "trabalhadores domésticos e setor público), em % de todas as pessoas "
                  "ocupadas de 14 anos ou mais. Mede o peso do emprego formal privado; UFs "
                  "com muito emprego público (ex.: DF, AP, RR) ficam naturalmente abaixo, "
                  "sem que isso signifique mais informalidade. " + _ERRO_UF),
    "rendimento": dict(
        tabela=6472, variavel=5933, cv=5941, classif="", freq="trimestral",
        nome="Rendimento médio real do trabalho", unidade="R$", melhor="maior", area="Renda",
        descricao="Rendimento médio mensal real habitualmente recebido de todos os trabalhos "
                  "pelas pessoas ocupadas de 14 anos ou mais com rendimento (tabela 6472). "
                  "Valores a preços do trimestre mais recente: o IBGE reajusta a série inteira "
                  "a cada divulgação, então os valores antigos mudam de nível (não de "
                  "tendência). É estimativa por amostra (margem de erro de ±5% a ±10% em UFs "
                  "pequenas); comparações anuais usam a média dos 4 trimestres."),
    "gini": dict(
        tabela=7435, variavel=10681, cv=10682, classif="", freq="anual",
        nome="Índice de Gini da renda domiciliar per capita", unidade="índice (0–1)",
        melhor="menor", area="Renda",
        descricao="Desigualdade do rendimento domiciliar per capita (PNAD Contínua anual, "
                  "1ª visita / 5ª visita conforme o ano). 0 = igualdade total. Estimativa por "
                  "amostra, com margem de erro maior nas UFs pequenas."),
    "pobreza": dict(
        tabela=5877, variavel=9948, cv=None, classif="", freq="anual",
        nome="População abaixo da linha de pobreza", unidade="%", melhor="menor", area="Renda",
        descricao="ODS 1.2.1 — % da população com rendimento domiciliar per capita abaixo de "
                  "US$ 8,30 por pessoa por dia em paridade de poder de compra (PPC) de 2021 "
                  "(linha do Banco Mundial para países de renda média-alta), convertida a "
                  "R$ 2,4498 por dólar PPC e corrigida pela inflação de cada ano e UF. A "
                  "tabela 5877 do SIDRA chama a variável de 'linha de pobreza nacional' porque "
                  "esse é o nome do indicador ODS 1.2.1; o Brasil não tem linha de pobreza "
                  "oficial, e a ficha de metadados do indicador no portal ODS Brasil do IBGE "
                  "(odsbrasil.gov.br/objetivo/MetadadosAPIndicador?n=1-2-1) define que a linha "
                  "usada é a de US$ 8,30 PPC 2021 — não é a linha do Bolsa Família nem a de "
                  "meio salário mínimo. Os "
                  "números são mais altos que os da Síntese de Indicadores Sociais (ex.: 2023: "
                  "29,8% aqui × cerca de 27% na SIS) porque a SIS ainda usa a linha antiga de "
                  "US$ 6,85 em PPC de 2017, que equivale a menos reais. Quando a linha é "
                  "revista, o IBGE recalcula a série toda. O IBGE não publica margem de erro "
                  "para esta tabela."),
    "extrema_pobreza": dict(
        tabela=5817, variavel=9617, cv=None, classif="", freq="anual",
        nome="População abaixo da linha de extrema pobreza", unidade="%", melhor="menor",
        area="Renda",
        descricao="ODS 1.1.1 — % da população com rendimento domiciliar per capita abaixo de "
                  "US$ 3,00 por pessoa por dia em PPC de 2021 (linha internacional de pobreza "
                  "extrema do Banco Mundial), convertida a R$ 2,4498 por dólar PPC e corrigida "
                  "pela inflação de cada ano e UF, como define a ficha de metadados do "
                  "indicador no portal ODS Brasil do IBGE "
                  "(odsbrasil.gov.br/objetivo/MetadadosAPIndicador?n=1-1-1). Os números são mais altos que os da Síntese de Indicadores "
                  "Sociais (ex.: 2023: 5,8% aqui × cerca de 4,4% na SIS) porque a SIS ainda usa a linha "
                  "antiga de US$ 2,15 em PPC de 2017, que equivale a menos reais. O IBGE não "
                  "publica margem de erro para esta tabela."),
}

CASAS = {"R$": 0, "índice (0–1)": 4}


def _periodo(codigo: str, freq: str) -> tuple[str, str, str]:
    """'202602' trimestral -> ('2026-T2', '2026-04-01', '2026-06-30')."""
    ano = int(codigo[:4])
    if freq == "anual":
        return str(ano), f"{ano}-01-01", f"{ano}-12-31"
    t = int(codigo[4:])
    ini_mes, fim = {1: (1, "03-31"), 2: (4, "06-30"), 3: (7, "09-30"), 4: (10, "12-31")}[t]
    return f"{ano}-T{t}", f"{ano}-{ini_mes:02d}-01", f"{ano}-{fim}"


def _baixar_tabela(tabela: int, classif: str, variaveis: list[int]):
    """Um arquivo bruto por tabela: Brasil + UFs, todos os valores e CVs pedidos."""
    vs = ",".join(str(v) for v in variaveis)
    url = f"{SIDRA}/t/{tabela}/n1/all/n3/all/v/{vs}/p/all{classif}"
    corpo, sha = baixar("ibge", url)
    dados = json.loads(corpo)
    cab, regs = dados[0], dados[1:]
    col_terr = next(k for k, v in cab.items() if k.endswith("C") and
                    v.startswith(("Brasil", "Unidade da Federação")))
    col_per = next(k for k, v in cab.items() if k.endswith("C") and
                   v.startswith(("Trimestre", "Ano")))
    col_var = next(k for k, v in cab.items() if k.endswith("C") and v.startswith("Variável"))
    valores = {}
    for r in regs:
        try:
            valores[(int(r[col_var]), SIGLA[r[col_terr]], r[col_per])] = float(r["V"])
        except ValueError:  # '...', '-', 'X': sem dado ou sigilo
            continue
    return valores, sha, url


def coletar() -> list[dict]:
    grupos = defaultdict(list)  # (tabela, classif) -> [ids]
    for ind, m in INDICADORES.items():
        grupos[(m["tabela"], m["classif"])].append(ind)

    linhas = []
    for (tabela, classif), inds in grupos.items():
        variaveis = []
        for ind in inds:
            m = INDICADORES[ind]
            variaveis += [m["variavel"]] + ([m["cv"]] if m["cv"] else [])
        valores, sha, url = _baixar_tabela(tabela, classif, variaveis)
        for ind in inds:
            m = INDICADORES[ind]
            casas = CASAS.get(m["unidade"], 2)
            for (var, uf, per), valor in sorted(valores.items()):
                if var != m["variavel"]:
                    continue
                periodo, ini, fim = _periodo(per, m["freq"])
                if int(ini[:4]) < 2012:
                    continue
                cv = valores.get((m["cv"], uf, per)) if m["cv"] else None
                ic95 = round(1.96 * cv / 100 * valor, casas + 1) if cv is not None else None
                linhas.append(dict(indicador=ind, uf=uf, periodo=periodo, inicio=ini, fim=fim,
                                   valor=valor, sha256=sha, url=url, status="", ic95=ic95))
    return linhas


def catalogo() -> dict:
    return {k: dict(nome=m["nome"], unidade=m["unidade"], melhor=m["melhor"], area=m["area"],
                    freq=m["freq"], descricao=m["descricao"], origem=ORIGEM,
                    link=f"https://sidra.ibge.gov.br/tabela/{m['tabela']}")
            for k, m in INDICADORES.items()}
