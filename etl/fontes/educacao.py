"""INEP — Indicadores Educacionais por UF e Brasil: abandono escolar e distorção idade-série.

Página: https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/indicadores-educacionais
Cada edição anual (Censo Escolar) sai num .zip próprio "Brasil, Regiões e UFs":
  - Taxas de Rendimento Escolar  -> taxa de abandono (anos finais do fundamental e ensino médio)
  - Taxas de Distorção Idade-Série -> TDI do ensino médio
Os nomes dos arquivos mudam de ano para ano (ver ARQUIVOS); edições novas são achadas na
subpágina do ano no gov.br. Cada edição traz só o próprio ano — a série é a junção delas.

Rede usada: ESTADUAL (para UFs e para o Brasil), como no IDEB (etl/fontes/inep.py).
Localização: Total (urbana + rural).

O layout da planilha muda entre edições (siglas x nomes de UF, uma ou três planilhas, colunas
de região a mais, códigos de variável diferentes e às vezes trocados — em 2018–2019 a coluna
"Anos Finais" do abandono tem o código tab_F04). Por isso as colunas são localizadas pelos
RÓTULOS do cabeçalho, e cada indicador precisa casar com exatamente uma coluna.

TDI de 2012–2014 só existe em .xls (formato binário antigo, ilegível sem bibliotecas de
fora): a série de distorção começa em 2015.
"""
import re
import urllib.request
import zipfile
import io

from etl.comum import NOME_UF, UFS, baixar
from etl.fontes.inep import _ler_xlsx, _tls_inep

ORIGEM = "INEP — Indicadores Educacionais (Censo Escolar)"
PAGINA = "https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/indicadores-educacionais"
D = "https://download.inep.gov.br/informacoes_estatisticas/indicadores_educacionais/"
REDE = "estadual"
ANO_INICIAL = 2012

# endereços conferidos em out/2026 nas subpáginas de cada ano (os nomes não seguem padrão)
ARQUIVOS = {
    "rend": {
        2012: "2012/taxas_rendimento/tx_rendimento_brasil_regioes_UFs_2012.zip",
        2013: "2013/taxa_rendimento/tx_rendimento_brasil_regioes_UFs_2013.zip",
        2014: "2014/taxa_rendimento/tx_rendimento_brasil_regioes_UFs_2014.zip",
        2015: "2015/taxa_rendimento/tx_rendimento_brasil_regioes_UFs_2015.zip",
        2016: "2016/TAXA_REND_2016_BRASIL_REGIOES_UFS.zip",
        2017: "2017/TAXA_REND_2017_BRASIL_REGIOES_UFS.zip",
        2018: "2018/TX_REND_BRASIL_REGIOES_UFS_2018.zip",
        **{a: f"{a}/tx_rend_brasil_regioes_ufs_{a}.zip" for a in range(2019, 2026)},
    },
    "tdi": {
        2015: "2015/distorcao_idade_serie/tdi_brasil_regioes_UFs_2015.zip",
        **{a: f"{a}/TDI_{a}_BRASIL_REGIOES_UFS.zip" for a in range(2016, 2026)},
    },
}
SUBPAGINA = {"rend": "taxas-de-rendimento-escolar", "tdi": "taxas-de-distorcao-idade-serie"}

INDICADORES = {
    "abandono_em": dict(
        tabela="rend", taxa="abandono", etapa="médio", folha="total",
        nome="Taxa de abandono — ensino médio (rede estadual)",
        texto="Percentual de alunos do ensino médio da rede estadual que deixaram de "
              "frequentar a escola durante o ano letivo (sem transferência)."),
    "abandono_ef_finais": dict(
        tabela="rend", taxa="abandono", etapa="fundamental", folha="anos finais",
        nome="Taxa de abandono — anos finais do fundamental (rede estadual)",
        texto="Percentual de alunos do 6º ao 9º ano da rede estadual que deixaram de "
              "frequentar a escola durante o ano letivo (sem transferência)."),
    "distorcao_em": dict(
        tabela="tdi", taxa=None, etapa="médio", folha="total",
        nome="Distorção idade-série — ensino médio (rede estadual)",
        texto="Percentual de alunos do ensino médio da rede estadual com 2 anos ou mais de "
              "atraso em relação à idade esperada para a série."),
}

# nome/sigla como aparece nas planilhas (normalizado) -> sigla
_UNIDADE = {**{s.upper(): s for s in UFS.values()},
            **{n.upper(): s for s, n in NOME_UF.items()}, "BRASIL": "BR"}


def _norm(c) -> str:
    return re.sub(r"\s+", " ", str(c or "")).strip()


def _url(tabela: str, ano: int) -> str | None:
    if ano in ARQUIVOS[tabela]:
        return D + ARQUIVOS[tabela][ano]
    # edição nova: procura o .zip "Brasil/Regiões/UFs" na subpágina do ano
    try:
        pag = urllib.request.urlopen(f"{PAGINA}/{SUBPAGINA[tabela]}/{ano}", timeout=60).read()
    except Exception:
        return None
    for u in re.findall(rb'https://download\.inep\.gov\.br/[^"\s<>]+\.zip', pag):
        u = u.decode()
        if re.search(r"brasil.*uf", u, re.I):
            return u
    return None


def _colunas(linhas: list[list], i0: int) -> list[str]:
    """Rótulo de cada coluna: junção das células de cabeçalho acima da 1ª linha de dados,
    com o texto de células mescladas estendido para a direita. Títulos longos (> 80
    caracteres) e códigos de variável (com '_') ficam de fora."""
    ncol = max(len(l) for l in linhas[i0:i0 + 5])
    rot = [[] for _ in range(ncol)]
    for h in linhas[max(0, i0 - 6):i0]:
        ultimo = ""
        for j in range(ncol):
            c = _norm(h[j]) if j < len(h) else ""
            if len(c) > 80 or ("_" in c and " " not in c):
                c = ""
            if c:
                ultimo = c
            rot[j].append((c, ultimo))  # (célula exata, célula estendida)
    return rot


def _achar(rot, taxa, etapa, folha) -> int:
    achados = []
    for j, partes in enumerate(rot):
        estendido = " | ".join(e for _, e in partes).lower()
        exatas = [c.lower() for c, _ in partes if c]
        if not exatas:
            continue
        if taxa and taxa not in estendido:
            continue
        outra = "fundamental" if etapa == "médio" else "médio"
        if not any(etapa in e.lower() and outra not in e.lower() for _, e in partes):
            continue
        folha_ok = exatas[-1].startswith("total") if folha == "total" else folha in exatas[-1]
        if not folha_ok or "seriado" in exatas[-1]:
            continue
        achados.append(j)
    if len(achados) != 1:
        raise ValueError(f"esperava 1 coluna para {taxa}/{etapa}/{folha}, achei {achados}")
    return achados[0]


def _id(rot, padrao) -> int:
    js = [j for j, partes in enumerate(rot) if any(re.search(padrao, c, re.I) for c, _ in partes)]
    if not js:
        raise ValueError(f"coluna de identificação '{padrao}' não encontrada")
    return js[0]


def _ler_edicao(corpo: bytes, ano: int, inds: dict) -> dict:
    """{(indicador, uf): valor} para a rede estadual, localização total."""
    z = zipfile.ZipFile(io.BytesIO(corpo))
    valores = {}
    for nome in z.namelist():
        if not nome.lower().endswith(".xlsx") or "~$" in nome:
            continue
        for linhas in _ler_xlsx(z.read(nome)).values():
            i0 = next((i for i, l in enumerate(linhas)
                       if l and isinstance(l[0], float) and int(l[0]) == ano), None)
            if i0 is None:
                continue
            rot = _colunas(linhas, i0)
            j_loc, j_rede = _id(rot, r"^Localiza"), _id(rot, r"^(Rede|Dependência)")
            cols = {k: _achar(rot, m["taxa"], m["etapa"], m["folha"]) for k, m in inds.items()}
            primeira = min(cols.values())
            for l in linhas[i0:]:
                if not l or len(l) <= primeira or _norm(l[j_rede]).lower() != REDE \
                        or _norm(l[j_loc]).lower() != "total":
                    continue
                uf = next((_UNIDADE[_norm(c).upper()] for c in l[1:primeira]
                           if _norm(c).upper() in _UNIDADE), None)
                if not uf:
                    continue  # regiões
                for k, j in cols.items():
                    v = l[j] if j < len(l) else None
                    if isinstance(v, float):
                        if (k, uf) in valores:
                            raise ValueError(f"{ano}: {k}/{uf} aparece duas vezes")
                        valores[(k, uf)] = v
    return valores


def coletar() -> list[dict]:
    linhas = []
    with _tls_inep():
        for tabela in ("rend", "tdi"):
            inds = {k: m for k, m in INDICADORES.items() if m["tabela"] == tabela}
            ano = min(ARQUIVOS[tabela])
            while True:
                url = _url(tabela, ano)
                if not url:
                    if ano <= max(ARQUIVOS[tabela]):
                        raise RuntimeError(f"educacao: sem arquivo {tabela} {ano}")
                    break  # edição ainda não publicada
                corpo, sha = baixar("educacao", url, ext="zip")
                valores = _ler_edicao(corpo, ano, inds)
                for k in inds:
                    ufs = {u for (i, u) in valores if i == k}
                    if len(ufs) != 28:
                        raise ValueError(f"educacao: {k} {ano} trouxe {len(ufs)} de 28 territórios")
                for (k, uf), v in sorted(valores.items()):
                    linhas.append(dict(indicador=k, uf=uf, periodo=str(ano),
                                       inicio=f"{ano}-01-01", fim=f"{ano}-12-31",
                                       valor=round(v, 1), sha256=sha, url=url,
                                       status="", ic95=None))
                ano += 1
    return linhas


def catalogo() -> dict:
    comum = (" Dado do Censo Escolar (INEP), rede estadual — inclusive no dado do Brasil —, "
             "zonas urbana e rural somadas.")
    pandemia = (" Atenção a 2020: com as aulas remotas e a orientação de não reprovar nem "
                "registrar abandono na pandemia, a taxa daquele ano caiu de forma artificial e "
                "não é comparável com as demais; 2021 também foi atípico. "
                "Quedas bruscas numa UF em "
                "um único ano (ex.: Pará em 2023, Mato Grosso em 2025) podem refletir "
                "mudanças na forma como a rede registra a situação dos alunos no Censo, e "
                "não só menos evasão.")
    extra = {
        "abandono_em": pandemia,
        "abandono_ef_finais": pandemia,
        "distorcao_em": " A série começa em 2015 (as edições de 2012–2014 só existem em "
                        "formato .xls antigo). A aprovação automática de 2020–2021 também "
                        "reduziu a distorção nos anos seguintes.",
    }
    return {k: dict(nome=m["nome"], unidade="%", melhor="menor", area="Educação",
                    freq="anual", descricao=m["texto"] + comum + extra[k],
                    origem=ORIGEM,
                    link=f"{PAGINA}/{SUBPAGINA[m['tabela']]}", variacao="pp",
                    escopo="uf", casas=1)
            for k, m in INDICADORES.items()}
