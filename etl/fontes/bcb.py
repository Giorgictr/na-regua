"""Banco Central do Brasil — SGS (Sistema Gerenciador de Séries Temporais).

API pública: https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json
Indicadores macroeconômicos e fiscais do Brasil (uf='BR') e o IBC-R, índice de
atividade regional que o BC calcula para 13 UFs. Séries diárias só aceitam
janelas de até 10 anos por chamada; aqui elas são pedidas em blocos de 5 anos.
"""
import calendar
import datetime as dt
import json
import time

from etl.comum import baixar

API = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json"
ORIGEM = "Banco Central — SGS"
LINK = ("https://www3.bcb.gov.br/sgspub/consultarvalores/consultarValoresSeries.do"
        "?method=consultarValores&optSelecionaSerie={codigo}")

# IBC-R com ajuste sazonal (base 2022 = 100: a média de 2022 dá 100,0 nas séries do SGS
# em out/2026 — o BC rebaseou o índice, antes 2002 = 100), códigos conferidos no catálogo de dados
# abertos do BC. O BC só calcula o índice para estas 13 UFs; o Brasil entra pelo IBC-Br.
IBCR = {"BR": 24364, "AM": 25412, "PA": 25410, "CE": 25391, "PE": 25418, "BA": 25416,
        "MG": 25380, "ES": 25399, "RJ": 25397, "SP": 25394, "PR": 25413, "SC": 25405,
        "RS": 25404, "GO": 25384}

SALARIO_MINIMO, IPCA_MENSAL = 1619, 433

# id: metadados + séries ({uf: código}); "sinal" -1 inverte o sinal da série original;
# "escala" multiplica; "diaria" agrega dia -> mês pelo último valor do mês.
INDICADORES = {
    "selic": dict(
        series={"BR": 432}, diaria=True,
        nome="Taxa Selic (meta)", unidade="% a.a.", melhor="neutro", area="Economia",
        descricao="Meta da taxa Selic definida pelo Copom, valor vigente no último dia de cada "
                  "mês (série diária 432). Só entram meses já encerrados. Juro alto não é "
                  "bom nem ruim em si: depende da inflação e do ciclo econômico."),
    "ipca_12m": dict(
        series={"BR": 13522},
        nome="Inflação (IPCA acumulado em 12 meses)", unidade="%", melhor="menor",
        area="Economia",
        descricao="Variação do IPCA (IBGE) nos 12 meses encerrados no mês de referência. "
                  "A meta de inflação do CMN foi 4,5% até 2018 e caiu gradualmente para 3% "
                  "a partir de 2024."),
    "divida_bruta": dict(
        series={"BR": 13762},
        nome="Dívida bruta do governo geral", unidade="% do PIB", melhor="menor",
        area="Contas públicas",
        descricao="Dívida bruta do governo geral (governo federal, INSS, estados e municípios), "
                  "metodologia do BC a partir de 2008, em % do PIB acumulado em 12 meses. "
                  "Revisões do PIB pelo IBGE alteram a série inteira."),
    "divida_liquida": dict(
        series={"BR": 4513},
        nome="Dívida líquida do setor público", unidade="% do PIB", melhor="menor",
        area="Contas públicas",
        descricao="Dívida líquida do setor público consolidado (governos, BC e estatais, exceto "
                  "Petrobras e Eletrobras), em % do PIB. Por descontar ativos como as reservas "
                  "internacionais, oscila com o câmbio."),
    "resultado_primario": dict(
        series={"BR": 5793}, sinal=-1,
        nome="Resultado primário do setor público (12 meses)", unidade="% do PIB",
        melhor="maior", area="Contas públicas",
        descricao="Resultado primário do setor público consolidado acumulado em 12 meses, em % "
                  "do PIB; positivo = superávit. O BC publica como necessidade de "
                  "financiamento (déficit positivo, série 5793), aqui com sinal invertido. "
                  "Inclui governos regionais e estatais, não só a União."),
    "cambio": dict(
        series={"BR": 3698},
        nome="Taxa de câmbio (dólar PTAX)", unidade="R$/US$", melhor="neutro", area="Economia",
        descricao="Média mensal da taxa PTAX de venda do dólar americano (série 3698). O câmbio "
                  "responde sobretudo a fatores externos e de juros; não há valor 'certo'."),
    "atividade": dict(
        series=IBCR,
        nome="Atividade econômica (IBC-Br / IBC-R)", unidade="índice", melhor="maior",
        area="Economia",
        descricao="Índice de Atividade Econômica do BC, com ajuste sazonal (base: média de "
                  "2022 = 100): "
                  "IBC-Br para o Brasil e IBC-R para as 13 UFs que o BC acompanha. É uma "
                  "prévia do PIB, não o PIB; compare variações, não níveis entre UFs."),
    "endividamento_familias": dict(
        series={"BR": 29037},
        nome="Endividamento das famílias", unidade="% da renda", melhor="menor",
        area="Economia",
        descricao="Dívida das famílias com o Sistema Financeiro Nacional em % da renda "
                  "familiar disponível acumulada em 12 meses, incluindo crédito imobiliário. "
                  "O dado mais recente costuma sair com 2 a 3 meses de defasagem."),
    "inadimplencia_pf": dict(
        series={"BR": 21084},
        nome="Inadimplência das pessoas físicas", unidade="%", melhor="menor",
        area="Economia",
        descricao="Percentual da carteira de crédito das pessoas físicas com atraso acima de "
                  "90 dias (recursos livres e direcionados)."),
    "reservas": dict(
        series={"BR": 3546}, escala=0.001,
        nome="Reservas internacionais", unidade="US$ bi", melhor="neutro", area="Economia",
        descricao="Reservas internacionais no conceito liquidez, posição de fim de mês, em "
                  "bilhões de dólares. Variam também com a cotação dos ativos e do ouro, não "
                  "só com compras e vendas do BC. Mais reservas não é automaticamente melhor: "
                  "dão proteção contra crises, mas têm custo fiscal de carregamento."),
    "salario_minimo_real": dict(
        series={"BR": SALARIO_MINIMO}, deflacionar=True, variacao="pct",
        nome="Salário mínimo real", unidade="R$ (preços do último mês com IPCA)",
        melhor="maior", area="Renda",
        descricao="Salário mínimo nacional vigente no mês (SGS 1619), corrigido pelo IPCA "
                  "(SGS 433, variação mensal) para preços do último mês com IPCA publicado, "
                  "para que anos diferentes fiquem comparáveis em poder de compra. Meses "
                  "posteriores ao último IPCA ficam de fora. No ano vale o valor de dezembro. "
                  "Não considera estados com piso regional próprio."),
}


def _json(url: str) -> tuple[list, str]:
    """O SGS às vezes devolve uma página de erro HTML com status 200: tenta de novo."""
    for i in range(4):
        corpo, sha = baixar("bcb", url, ext="json")
        try:
            return json.loads(corpo), sha
        except ValueError:
            time.sleep(5 * (i + 1))
    raise RuntimeError(f"bcb: resposta não é JSON: {url}")


def _janelas(diaria: bool) -> list[tuple[str, str]]:
    if not diaria:
        return [("01/01/2012", "31/12/2030")]
    # janela inteiramente no futuro dá 404; a última vai até 31/12/2030 como as mensais
    return [(f"01/01/{a}", f"31/12/{min(a + 4, 2030)}")
            for a in range(2012, min(dt.date.today().year, 2030) + 1, 5)]


def _mensal(codigo: int) -> tuple[dict, str, str]:
    """{'AAAA-MM': valor} de uma série mensal do SGS (2012 em diante, até hoje)."""
    ini, fim = _janelas(False)[0]
    url = API.format(codigo=codigo) + f"&dataInicial={ini}&dataFinal={fim}"
    dados, sha = _json(url)
    hoje = dt.date.today()
    out = {}
    for r in dados:
        d = dt.datetime.strptime(r["data"], "%d/%m/%Y").date()
        if d <= hoje and r["valor"] not in (None, ""):
            out[f"{d.year}-{d.month:02d}"] = float(r["valor"])
    return out, sha, url


def _salario_minimo_real() -> list[dict]:
    """Nominal (1619) × índice IPCA do último mês ÷ índice IPCA do mês, índice encadeado a
    partir das variações mensais (433). Cita os dois arquivos."""
    nominal, sha_n, url_n = _mensal(SALARIO_MINIMO)
    ipca, sha_i, url_i = _mensal(IPCA_MENSAL)
    indice, nivel = {}, 1.0
    for mes in sorted(ipca):
        nivel *= 1 + ipca[mes] / 100
        indice[mes] = nivel
    ultimo = max(indice)
    linhas = []
    for mes, v in sorted(nominal.items()):
        if mes not in indice:
            continue  # sem IPCA do mês (posterior ao último publicado): fica de fora
        a, m_ = int(mes[:4]), int(mes[5:])
        linhas.append(dict(indicador="salario_minimo_real", uf="BR", periodo=mes,
                           inicio=f"{mes}-01",
                           fim=f"{mes}-{calendar.monthrange(a, m_)[1]:02d}",
                           valor=round(v * indice[ultimo] / indice[mes], 2),
                           sha256=f"{sha_n},{sha_i}", url=f"{url_n} ; {url_i}"))
    return linhas


def coletar() -> list[dict]:
    hoje = dt.date.today()
    linhas = _salario_minimo_real()
    for ind, m in INDICADORES.items():
        if m.get("deflacionar"):
            continue
        sinal, escala = m.get("sinal", 1), m.get("escala", 1)
        for uf, codigo in m["series"].items():
            pontos = {}  # 'AAAA-MM' -> (data, valor, sha, url)
            for ini, fim in _janelas(m.get("diaria", False)):
                url = API.format(codigo=codigo) + f"&dataInicial={ini}&dataFinal={fim}"
                dados, sha = _json(url)
                for r in dados:
                    d = dt.datetime.strptime(r["data"], "%d/%m/%Y").date()
                    try:
                        v = float(r["valor"])
                    except (TypeError, ValueError):
                        continue
                    if d.year < 2012 or d > hoje:
                        continue
                    chave = f"{d.year}-{d.month:02d}"
                    if chave not in pontos or d >= pontos[chave][0]:  # fica o último do mês
                        pontos[chave] = (d, v, sha, url)
            for chave, (d, v, sha, url) in sorted(pontos.items()):
                ultimo = calendar.monthrange(d.year, d.month)[1]
                fim_mes = dt.date(d.year, d.month, ultimo)
                if m.get("diaria") and fim_mes > hoje:
                    continue  # mês ainda em curso: valor de fim de mês não existe
                linhas.append(dict(indicador=ind, uf=uf, periodo=chave,
                                   inicio=f"{chave}-01", fim=fim_mes.isoformat(),
                                   valor=round(sinal * v * escala, 6) + 0.0,
                                   sha256=sha, url=url))
    return linhas


def catalogo() -> dict:
    return {k: dict(nome=m["nome"], unidade=m["unidade"], melhor=m["melhor"], area=m["area"],
                    freq="mensal", descricao=m["descricao"], origem=ORIGEM,
                    link=LINK.format(codigo=m["series"].get("BR", next(iter(m["series"].values())))),
                    variacao=m.get("variacao") or (
                        "pct" if m["unidade"] in ("R$/US$", "índice", "US$ bi") else "pp"),
                    escopo="uf" if len(m["series"]) > 1 else "br",
                    # estoques e taxas acumuladas em 12 meses: o ano vale o que estava em dezembro
                    **({"agregacao": "fim"} if k in FIM_DO_ANO else {}),
                    **({"casas": 2} if k in ("selic", "cambio") else {}))
            for k, m in INDICADORES.items()}


FIM_DO_ANO = {"selic", "ipca_12m", "divida_bruta", "divida_liquida", "resultado_primario",
              "endividamento_familias", "inadimplencia_pf", "reservas", "salario_minimo_real"}
