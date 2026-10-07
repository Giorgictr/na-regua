"""Ministério da Justiça e Segurança Pública — SINESP VDE (Validador de Dados Estatísticos).

Fonte: a "Base de Dados" do SINESP VDE, uma planilha .xlsx por ano (2015 em diante) com
os registros mensais que as secretarias estaduais de segurança enviam ao MJSP, por
município ou por UF, conforme o evento. A lista de planilhas é lida da página oficial
(PAGINA), então anos novos entram sozinhos.

Leitura: cada planilha tem uma só aba, com ~25 MB compactados e ~330 MB de XML. Ela é
lida em fluxo (zipfile + regex por linha <row>), sem carregar o XML inteiro e sem
openpyxl. Soma-se, por UF, ano, mês e evento, a coluna total_vitima (crimes contra a
pessoa) ou total (ocorrências, como roubo de veículo); só a abrangência "Estadual"
(polícias estaduais) entra — PF e PRF ficam de fora.

Downloads: o servidor do gov.br entrega esses arquivos devagar e às vezes corta a
transferência no meio com HTTP 200. Por isso `normalizar` só confere que o arquivo é um
.xlsx íntegro (zip válido) e devolve os bytes intactos; se não for, o download é refeito
e o arquivo truncado não é guardado.

Lacunas: o SINESP depende do envio das UFs, e várias delas não informaram alguns
eventos em alguns anos (ex.: feminicídio no CE só a partir de 2018; mortes por
intervenção de agente do Estado na BA só a partir de 2020) — nesses casos a planilha
traz 0 ou célula vazia. Regras aplicadas a cada UF-ano:
  - todos os eventos que compõem o indicador precisam ter os 12 meses preenchidos;
  - um total anual igual a 0 é tratado como "não informado" (ver EXIGE_POSITIVO);
  - o Brasil só sai quando as 27 UFs passam nas duas regras (senão a soma seria parcial).

Taxas por 100 mil habitantes com a Projeção da População do IBGE, revisão 2024, via
TabNet/DATASUS (a mesma tabela que etl/fontes/datasus.py usa); feminicídio usa a
população feminina. Cada linha cita (sha256/url) a planilha do ano e o arquivo de
população usado.

Anos: só anos encerrados. O último ano encerrado sai como "preliminar": as UFs seguem
consolidando e homologando os dados, e o MJSP republica as planilhas.
"""
import concurrent.futures as cf
import datetime as dt
import html
import io
import re
import zipfile
from collections import defaultdict
from urllib.parse import quote_plus, urljoin

from etl.comum import SIGLA, UFS, baixar
from etl.fontes.datasus import ic95_taxa

FONTE = "seguranca"
ORIGEM = "Ministério da Justiça — SINESP"
PAGINA = ("https://www.gov.br/mj/pt-br/assuntos/sua-seguranca/seguranca-publica/estatistica/"
          "dados-nacionais-1/base-de-dados-e-notas-metodologicas-dos-gestores-estaduais-"
          "sinesp-vde-2022-e-2023")
ANO_INICIAL = 2015

CGI = "https://tabnet.datasus.gov.br/cgi"
DEF_POP = "ibge/cnv/projpop2024uf.def"  # IBGE, Projeção da População revisão 2024

HOMICIDIO = "Homicídio doloso"
LATROCINIO = "Roubo seguido de morte (latrocínio)"
LCSM = "Lesão corporal seguida de morte"
MIAE = "Morte por intervenção de Agente do Estado"
FEMINICIDIO = "Feminicídio"
ESTUPRO = "Estupro"
ESTUPRO_VULN = "Estupro de vulnerável"
ROUBO_VEICULO = "Roubo de veículo"

_NOTA_SINESP = (
    " Os números são registros das polícias estaduais enviados ao SINESP pelas secretarias "
    "de segurança: dependem de como cada UF registra e classifica as ocorrências, e a "
    "cobertura e a qualidade variam por estado e por ano (os primeiros anos, 2015–2018, "
    "têm mais lacunas). UF-ano com mês faltando ou total anual zerado (sinal de dado não "
    "enviado) fica de fora, e o Brasil só aparece quando as 27 UFs informaram. "
    "População: projeção IBGE revisão 2024. O último ano é preliminar.")

# id -> eventos somados, população ("total"|"mulheres"), eventos cujo total anual tem de
# ser > 0 para a UF-ano valer, e metadados do catálogo
INDICADORES = {
    "mvi": dict(
        eventos=[HOMICIDIO, LATROCINIO, LCSM, MIAE], pop="total",
        positivo=[HOMICIDIO, MIAE],
        nome="Mortes violentas intencionais (MVI)",
        descricao="Vítimas de homicídio doloso, latrocínio (roubo seguido de morte), lesão "
                  "corporal seguida de morte e mortes por intervenção de agente do Estado "
                  "(polícias estaduais), por 100 mil habitantes, segundo os boletins de "
                  "ocorrência — é o conceito usado pelo Anuário Brasileiro de Segurança "
                  "Pública. Difere da taxa de homicídios do SIM/Ministério da Saúde, que conta "
                  "atestados de óbito pela residência da vítima. Algumas UFs (como a Bahia até "
                  "2019) não informavam mortes por intervenção policial; nesses anos a UF fica "
                  "sem MVI (veja CVLI). Os valores ficam cerca de 2–3% abaixo dos do Anuário "
                  "Brasileiro de Segurança Pública, porque o Anuário soma os policiais mortos "
                  "e aplica correções próprias às informações das secretarias." + _NOTA_SINESP),
    "cvli": dict(
        eventos=[HOMICIDIO, LATROCINIO, LCSM], pop="total", positivo=[HOMICIDIO],
        nome="Crimes violentos letais intencionais (CVLI)",
        descricao="Vítimas de homicídio doloso, latrocínio e lesão corporal seguida de morte "
                  "por 100 mil habitantes, segundo os boletins de ocorrência — é a MVI sem as "
                  "mortes causadas por policiais, o que permite comparar mais UFs e anos. "
                  "Fica cerca de 2–3% abaixo do número equivalente do Anuário Brasileiro de "
                  "Segurança Pública, que aplica correções próprias às informações das "
                  "secretarias (e, na MVI, soma os policiais mortos)."
                  + _NOTA_SINESP),
    "mortes_intervencao_estado": dict(
        eventos=[MIAE], pop="total", positivo=[MIAE],
        nome="Mortes por intervenção de agentes do Estado",
        descricao="Pessoas mortas por policiais (civis e militares estaduais) em serviço ou "
                  "fora dele, por 100 mil habitantes. Várias UFs não informaram esse dado nos "
                  "primeiros anos da série (ex.: Bahia até 2019, Rondônia em vários anos); "
                  "registros de PF e PRF não entram." + _NOTA_SINESP),
    "feminicidio": dict(
        eventos=[FEMINICIDIO], pop="mulheres", positivo=[FEMINICIDIO],
        nome="Feminicídios", unidade="por 100 mil mulheres",
        descricao="Assassinatos de mulheres registrados como feminicídio (morte por razão da "
                  "condição de sexo feminino, Lei 13.104/2015), por 100 mil mulheres. A "
                  "tipificação é recente e foi adotada aos poucos: vários estados só passaram a "
                  "informar depois (ex.: Ceará a partir de 2018) e, até cerca de 2018, vários "
                  "trazem só parte dos casos (ex.: São Paulo em 2015–2016, Rio em 2016). Parte "
                  "do aumento ao longo dos anos reflete melhor classificação, não "
                  "necessariamente mais casos."
                  + _NOTA_SINESP),
    "estupro": dict(
        eventos=[ESTUPRO, ESTUPRO_VULN], pop="total", positivo=[],
        positivo_soma=True,
        nome="Estupros registrados",
        descricao="Vítimas de estupro e de estupro de vulnerável (menores de 14 anos ou "
                  "pessoas sem condição de resistir) somadas, por 100 mil habitantes. As UFs "
                  "separam as duas categorias de jeitos diferentes (algumas lançam tudo como "
                  "estupro), por isso só a soma é comparável. É um crime muito subnotificado: "
                  "a taxa mede registros na polícia, e uma alta pode refletir mais denúncias."
                  + _NOTA_SINESP),
    "roubo_veiculo": dict(
        eventos=[ROUBO_VEICULO], pop="total", positivo=[ROUBO_VEICULO],
        nome="Roubos de veículo",
        descricao="Ocorrências de roubo de veículo (com violência ou grave ameaça; furtos não "
                  "entram) por 100 mil habitantes. Acre, Goiás, Paraná, Espírito Santo e "
                  "Rondônia não informaram em alguns anos entre 2015 e 2020." + _NOTA_SINESP),
}
EVENTOS = {e for m in INDICADORES.values() for e in m["eventos"]}


# --------------------------------------------------------------------------- downloads
def _xlsx_integro(corpo: bytes) -> bytes:
    """Usado como `normalizar`: não muda nada, só recusa arquivo truncado."""
    try:
        if zipfile.ZipFile(io.BytesIO(corpo)).testzip() is not None:
            raise ValueError("membro corrompido")
    except (zipfile.BadZipFile, ValueError) as e:
        raise ValueError(f"xlsx inválido/truncado ({len(corpo)} bytes): {e}") from None
    return corpo


def _baixar_xlsx(url: str, tentativas: int = 4) -> tuple[bytes, str]:
    erro = None
    for _ in range(tentativas):
        try:
            return baixar(FONTE, url, ext="xlsx", normalizar=_xlsx_integro)
        except (ValueError, RuntimeError) as e:
            erro = e
    raise RuntimeError(f"{FONTE}: não consegui baixar {url} íntegro: {erro}")


def _planilhas() -> dict[int, str]:
    """{ano: url} das bases anuais listadas na página do MJSP (só anos encerrados)."""
    pagina, _ = baixar(FONTE, PAGINA, ext="html")
    links = {}
    for href in re.findall(r'href="([^"]*bancovde-(\d{4})\.xlsx[^"]*)"', pagina.decode("utf-8", "replace")):
        url, ano = urljoin(PAGINA, html.unescape(href[0])), int(href[1])
        if ANO_INICIAL <= ano < dt.date.today().year:
            links[ano] = url
    if len(links) < 5:
        raise RuntimeError(f"{FONTE}: a página do SINESP VDE listou só {sorted(links)}")
    return links


# --------------------------------------------------------------------------- leitura
_ROW = re.compile(rb"<row\b[^>]*>(.*?)</row>", re.S)
_CEL = re.compile(rb'<c r="([A-Z]+)\d+"([^>]*?)(?:/>|>(.*?)</c>)', re.S)
_T = re.compile(rb"<t[^>]*>(.*?)</t>", re.S)
_V = re.compile(rb"<v>(.*?)</v>", re.S)


def _ler_base(conteudo: bytes, ano: int) -> dict:
    """Agrega a base anual: {(uf, evento, mês): [soma, células com número]}."""
    z = zipfile.ZipFile(io.BytesIO(conteudo))
    nomes = z.namelist()
    compart = []
    if "xl/sharedStrings.xml" in nomes:
        xml = z.read("xl/sharedStrings.xml")
        compart = [b"".join(_T.findall(si)) for si in re.findall(rb"<si>(.*?)</si>", xml, re.S)]
    aba = sorted(n for n in nomes if n.startswith("xl/worksheets/sheet"))[0]

    def valor(attrs, corpo):
        if corpo is None:
            return None
        if b'"inlineStr"' in attrs:
            return html.unescape(b"".join(_T.findall(corpo)).decode())
        v = _V.search(corpo)
        if not v:
            return None
        if b't="s"' in attrs:
            return html.unescape(compart[int(v.group(1))].decode())
        if b't="str"' in attrs:
            return html.unescape(v.group(1).decode())
        return float(v.group(1))

    col, agg, buf = None, defaultdict(lambda: [0.0, 0]), b""
    with z.open(aba) as f:
        while True:
            pedaco = f.read(1 << 22)
            buf += pedaco
            fim = buf.rfind(b"</row>")
            if fim >= 0:
                parte, buf = buf[:fim + 6], buf[fim + 6:]
                for r in _ROW.finditer(parte):
                    d = {c.group(1): valor(c.group(2), c.group(3)) for c in _CEL.finditer(r.group(1))}
                    if col is None:  # cabeçalho: nome da coluna -> letra
                        col = {v: k for k, v in d.items() if isinstance(v, str)}
                        falta = {"uf", "evento", "data_referencia", "total_vitima", "total",
                                 "abrangencia"} - set(col)
                        if falta:
                            raise RuntimeError(f"{FONTE}: base {ano} sem colunas {falta}")
                        continue
                    evento = d.get(col["evento"])
                    if evento not in EVENTOS or d.get(col["abrangencia"]) != "Estadual":
                        continue
                    data = dt.date(1899, 12, 30) + dt.timedelta(days=int(d[col["data_referencia"]]))
                    if data.year != ano:
                        raise RuntimeError(f"{FONTE}: base {ano} tem linha de {data}")
                    a = agg[(d[col["uf"]], evento, data.month)]
                    for c in ("total_vitima", "total"):
                        v = d.get(col[c])
                        if isinstance(v, float):
                            a[0] += v
                            a[1] += 1
            if not pedaco:
                break
    if col is None:
        raise RuntimeError(f"{FONTE}: base {ano} vazia")
    return agg


def _anual(agg: dict) -> dict:
    """{(uf, evento): total do ano} só para UF-evento com os 12 meses informados."""
    meses, soma = defaultdict(set), defaultdict(float)
    for (uf, ev, mes), (v, n) in agg.items():
        if n:
            meses[(uf, ev)].add(mes)
            soma[(uf, ev)] += v
    return {k: soma[k] for k, m in meses.items() if len(m) == 12}


# --------------------------------------------------------------------------- população
def _populacao(sexo: str | None) -> tuple[dict, str, str]:
    """TabNet (POST, latin-1): {(uf|'BR', ano): pessoas}. sexo=None (todos) ou '2' (mulheres)."""
    link = f"{CGI}/deftohtm.exe?{DEF_POP}"
    form, _ = baixar(FONTE, link, ext="html")
    form = form.decode("latin-1")
    arquivos = sorted(set(re.findall(r'VALUE="(projuf\d\d\.dbf)"', form)))
    pares = [("Linha", "Unidade_da_Federação"), ("Coluna", "Ano"),
             ("Incremento", "População_residente")]
    pares += [("Arquivos", a) for a in arquivos
              if ANO_INICIAL <= 2000 + int(a[6:8]) < dt.date.today().year]
    pares += [(s, sexo if (s == "SSexo" and sexo) else "TODAS_AS_CATEGORIAS__")
              for s in re.findall(r'NAME="(S[^"]+)"', form)]
    pares += [("formato", "prn"), ("mostre", "Mostra")]
    corpo = "&".join(quote_plus(k, encoding="latin-1") + "=" + quote_plus(v, encoding="latin-1")
                     for k, v in pares).encode("ascii")
    url = f"{CGI}/tabcgi.exe?{DEF_POP}"
    bruto, sha = baixar(FONTE, url, dados=corpo, ext="html")
    pre = re.search(r"<PRE>(.*?)</PRE>", bruto.decode("latin-1"), re.S | re.I)
    if not pre:
        raise RuntimeError(f"{FONTE}: TabNet de população sem tabela")
    linhas = [html.unescape(l).strip() for l in pre.group(1).splitlines() if ";" in l]
    anos = [c.strip('" ') for c in linhas[0].split(";")[1:]]
    pop = {}
    for l in linhas[1:]:
        cel = [c.strip('" ') for c in l.split(";")]
        m = re.match(r"(\d{2}) ", cel[0])
        uf = "BR" if cel[0] == "Total" else (SIGLA.get(m.group(1)) if m else None)
        if uf:
            for ano, v in zip(anos, cel[1:]):
                if ano.isdigit() and v.isdigit():
                    pop[(uf, int(ano))] = int(v)
    if len({u for u, _ in pop}) != 28:
        raise RuntimeError(f"{FONTE}: população do TabNet não trouxe 27 UFs + Brasil")
    return pop, sha, url


# --------------------------------------------------------------------------- contrato
def coletar() -> list[dict]:
    pops = {"total": _populacao(None), "mulheres": _populacao("2")}
    links = _planilhas()

    def um_ano(ano):
        conteudo, sha = _baixar_xlsx(links[ano])
        return ano, _anual(_ler_base(conteudo, ano)), sha

    with cf.ThreadPoolExecutor(max_workers=len(links)) as ex:  # servidor lento por conexão
        bases = {ano: (anual, sha) for ano, anual, sha in ex.map(um_ano, sorted(links))}

    ultimo = dt.date.today().year - 1
    ufs = sorted(UFS.values())
    linhas = []
    for ind, m in INDICADORES.items():
        pop, sha_p, url_p = pops[m["pop"]]
        for ano, (anual, sha) in sorted(bases.items()):
            contagens = {}
            for uf in ufs:
                partes = [anual.get((uf, e)) for e in m["eventos"]]
                if any(p is None for p in partes):
                    continue  # algum mês não informado
                if any(anual[(uf, e)] <= 0 for e in m["positivo"]):
                    continue  # total anual zerado = dado não enviado
                if m.get("positivo_soma") and sum(partes) <= 0:
                    continue
                contagens[uf] = sum(partes)
            if len(contagens) == 27:
                contagens["BR"] = sum(contagens.values())
            for uf, n in contagens.items():
                den = pop.get((uf, ano))
                if not den:
                    continue
                linhas.append(dict(
                    indicador=ind, uf=uf, periodo=str(ano), inicio=f"{ano}-01-01",
                    fim=f"{ano}-12-31", valor=round(100_000 * n / den, 2),
                    sha256=f"{sha},{sha_p}", url=f"{links[ano]} ; {url_p}",
                    status="preliminar" if ano == ultimo else "",
                    ic95=ic95_taxa(n, den, 100_000)))
    return linhas


def catalogo() -> dict:
    return {k: dict(nome=m["nome"], unidade=m.get("unidade", "por 100 mil hab."),
                    melhor="menor", area="Segurança", freq="anual", descricao=m["descricao"],
                    origem=ORIGEM, link=PAGINA, variacao="pct", escopo="uf")
            for k, m in INDICADORES.items()}
