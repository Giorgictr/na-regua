"""INEP — IDEB por UF e Brasil (anos iniciais, anos finais e ensino médio).

Página: https://www.gov.br/inep/pt-br/areas-de-atuacao/pesquisas-estatisticas-e-indicadores/ideb/resultados
A planilha de divulgação mais recente traz a série inteira (2005 até a última
edição), então basta baixar o arquivo da última edição:
  divulgacao_regioes_ufs_ideb_<ano>.zip  -> abas "UF e Regiões (AI|AF|EM)"
  divulgacao_brasil_ideb_<ano>.zip       -> abas "Brasil (Anos Iniciais|Anos Finais|EM)"
Conferido em out/2026: os valores 2013–2023 do arquivo de 2025 batem 100% com
os do arquivo de 2023 (nenhuma revisão retroativa).

Rede usada: ESTADUAL para as UFs, porque é a rede que o governo estadual administra
(a planilha por UF não traz "Pública" para o ensino médio). Para o Brasil, rede PÚBLICA
(estadual + municipal + federal), nas três etapas: o governo federal não administra as
redes estaduais, então o dado nacional mede o conjunto da escola pública.

Leitura do .xlsx só com biblioteca padrão (zipfile + XML), sem openpyxl.
"""
import contextlib
import io
import re
import ssl
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

from etl.comum import UFS, baixar

ORIGEM = "INEP — IDEB"
LINK = ("https://www.gov.br/inep/pt-br/areas-de-atuacao/pesquisas-estatisticas-e-indicadores/"
        "ideb/resultados")
BASE = "https://download.inep.gov.br/ideb/resultados/"
# edições candidatas, da mais nova para a mais antiga: usa a primeira que existir
EDICOES = [2027, 2025, 2023]
REDE = {"uf": "estadual", "br": "pública"}

INDICADORES = {
    "ideb_ef_iniciais": dict(aba_uf="(AI)", aba_br="(Anos Iniciais)",
                             nome="IDEB — anos iniciais do fundamental (UFs: rede estadual; Brasil: rede pública)",
                             etapa="nos anos iniciais do ensino fundamental (1º ao 5º ano)"),
    "ideb_ef_finais": dict(aba_uf="(AF)", aba_br="(Anos Finais)",
                           nome="IDEB — anos finais do fundamental (UFs: rede estadual; Brasil: rede pública)",
                           etapa="nos anos finais do ensino fundamental (6º ao 9º ano)"),
    "ideb_em": dict(aba_uf="(EM)", aba_br="(EM)",
                    nome="IDEB — ensino médio (UFs: rede estadual; Brasil: rede pública)",
                    etapa="no ensino médio regular"),
}

# nomes como aparecem na planilha (alguns abreviados) -> código IBGE
NOME_PLANILHA = {
    "Rondônia": 11, "Acre": 12, "Amazonas": 13, "Roraima": 14, "Pará": 15, "Amapá": 16,
    "Tocantins": 17, "Maranhão": 21, "Piauí": 22, "Ceará": 23, "R. G. do Norte": 24,
    "Paraíba": 25, "Pernambuco": 26, "Alagoas": 27, "Sergipe": 28, "Bahia": 29,
    "Minas Gerais": 31, "Espírito Santo": 32, "Rio de Janeiro": 33, "São Paulo": 35,
    "Paraná": 41, "Santa Catarina": 42, "R. G. do Sul": 43, "M. G. do Sul": 50,
    "Mato Grosso": 51, "Goiás": 52, "Distrito Federal": 53,
}

# download.inep.gov.br entrega só o certificado folha, sem a intermediária
# (RNP ICPEdu GR46 OV TLS CA 2025, emitida pela raiz GlobalSign R46; vale até
# 19/11/2030; obtida em http://secure.globalsign.com/cacert/rnpicpedugr46ovtlsca2025.crt).
# Sem ela o urllib falha com CERTIFICATE_VERIFY_FAILED. A raiz continua vindo
# do repositório do sistema: a verificação TLS segue ligada.
INTERMEDIARIA_INEP = """-----BEGIN CERTIFICATE-----
MIIGnjCCBIagAwIBAgIRAISsNxNp8rOJbBB1nGV+D9EwDQYJKoZIhvcNAQEMBQAw
RjELMAkGA1UEBhMCQkUxGTAXBgNVBAoTEEdsb2JhbFNpZ24gbnYtc2ExHDAaBgNV
BAMTE0dsb2JhbFNpZ24gUm9vdCBSNDYwHhcNMjUxMTE5MDMyNzU1WhcNMzAxMTE5
MDAwMDAwWjBpMQswCQYDVQQGEwJCUjExMC8GA1UEChMoUkVERSBOQUNJT05BTCBE
RSBFTlNJTk8gRSBQRVNRVUlTQSAtIFJOUDEnMCUGA1UEAxMeUk5QIElDUEVkdSBH
UjQ2IE9WIFRMUyBDQSAyMDI1MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKC
AgEAqBd4pyjCSQPAFcGq8km8PmRE/BoAJdPvYWKz6gr6x4sXfY40iCWxWLgZkGuN
+OwfXRmCXC1hIb2/WWf8Nl92SSfTb/J0D7KVSksnTrXtxyxXSaEnlKEVKltoTVSC
yEop+pZf6SwuK0l66xvmM9dt/xGgngIvpeaxIIMAAgNDp52PlSrJh5IKzD/FJ4s0
Rq9Aiz3bXLYXCMCa+8WSSVfxJWYgK9IdrTAsu1T24c+xj9TvMcbUgzTDZLhvsRwj
FcY332r9XszFkDqZxCSnjb/ztYa5jFrNGGHlmygMUmBCHGqcsqet/trLKjtaGoqO
JwD0Kk/FAsqF4aGUH7hwIwRuD6ce4BjmPbv870jGdhlRyaMITLbP1YwPDOuoRkrI
utjL30dyHZWiJq1WuYbcgWODH8QwF5BUyxdHpGsv/QL2GXn/Z+GFgdO+4dBnGz7S
AokPYKmMQwKdyn3hzNgShDSFq0sj+vhT3fAXSlth1xjCvdDz+ttccinn71FV5Ahu
S4n9gw8RmSlJoYhr1pzn4Aryi6+31gJVPA8UyTfVh9MbBi7BqPmMnYeZYj7Pr6o0
k8wsz5RA+HL5AbS1QouWcFFe4LEKWqXh67xFONVfi1bO/Y31mDU3fhSzW8tx6bkm
s7N2YunWsPgrOGTcBKbrQTseAShEamJoenImGL4fbP8zZF8CAwEAAaOCAWIwggFe
MA4GA1UdDwEB/wQEAwIBhjATBgNVHSUEDDAKBggrBgEFBQcDATASBgNVHRMBAf8E
CDAGAQH/AgEAMB0GA1UdDgQWBBSUsMlPweBs787GK2yztMsiinZJtzAfBgNVHSME
GDAWgBQDXKtzgYeozLCm1ZTiNpZJ/wWZLDB7BggrBgEFBQcBAQRvMG0wLgYIKwYB
BQUHMAGGImh0dHA6Ly9vY3NwLmdsb2JhbHNpZ24uY29tL3Jvb3RyNDYwOwYIKwYB
BQUHMAKGL2h0dHA6Ly9zZWN1cmUuZ2xvYmFsc2lnbi5jb20vY2FjZXJ0L3Jvb3Ry
NDYuY3J0MDYGA1UdHwQvMC0wK6ApoCeGJWh0dHA6Ly9jcmwuZ2xvYmFsc2lnbi5j
b20vcm9vdHI0Ni5jcmwwLgYDVR0gBCcwJTAIBgZngQwBAgIwDAYKKwYBBAGgMgoB
AjALBgkrBgEEAaAyARQwDQYJKoZIhvcNAQEMBQADggIBABAGOWuTA3iFMqABnBPR
rb1YNwcRqQE1Tvz+9f7a0YUWk+wNH3yPVAqd3i9abWtRT6nNBpu49XNAqWSebXpR
9J5Im5NJruhYxqtd5c6Y04GdoS/JSh6HmJxiBS2Tv5E+Z9yqkBgt41VhxszYEbus
qL/56foMry+EWvXRJ0nA9P0GxdFmbTD4DkLFq++E15FBeRf7uRGUe46bZN345OQ7
jhN2eZwpHzIwTrfaPwHxkFThXU8KPgClmq77JJ/NzlAAPEjpr+TF6K17lzBZS1o1
Lrk+EFDOGVGc0Ncad7JcFldwmLd0C9B73jq0t5opQcl/u1wdIanosZ418vCJp25K
QW1BCDCHenf+6mA2VptyuywHcDqM75rSGi5wxbE4IxkMxrl89HsQKfRSJbDT/0v5
gGlMw/UaCMP6O/4nwHrmXQJ2CVS7M4ucbUbm+ZSqOWgkDCTVvXyyIzWFpWxMk7UH
XBTei1qG19/PbShKTgYcgod0ReTr4osyARZ5T7jZqe8UKW1DUXcVasukATKryagk
NRRjRmM9YasyVMO3SVhTFp49aqAe173TKd2yatDmxlvB9s5fZ5pz5ptdyQFTyv+N
yLDZd5PHiO/JWBFL3g2XVFgKmDVlKsBkqLs/NR18/RWv0d7YKTVVfhc64gdXQAMt
Lyso4S/KfU1hV0inHITEfil4
-----END CERTIFICATE-----
"""


@contextlib.contextmanager
def _tls_inep():
    """Durante o bloco, o urlopen (usado por baixar) confia também na intermediária do INEP."""
    ctx = ssl.create_default_context()
    ctx.load_verify_locations(cadata=INTERMEDIARIA_INEP)
    anterior = urllib.request._opener
    urllib.request.install_opener(urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ctx)))
    try:
        yield
    finally:
        urllib.request._opener = anterior


# ---------- leitor mínimo de .xlsx (biblioteca padrão) ----------
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
       "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
       "pr": "http://schemas.openxmlformats.org/package/2006/relationships"}


def _col(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(ch) - 64
    return n - 1


def _ler_xlsx(conteudo: bytes) -> dict[str, list[list]]:
    """{nome_da_aba: linhas}, cada célula como str/float/None."""
    z = zipfile.ZipFile(io.BytesIO(conteudo))
    compartilhadas = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", _NS):
            compartilhadas.append("".join(t.text or "" for t in si.iter(f"{{{_NS['m']}}}t")))
    rels = {r.get("Id"): r.get("Target") for r in
            ET.fromstring(z.read("xl/_rels/workbook.xml.rels")).findall("pr:Relationship", _NS)}
    abas = {}
    for s in ET.fromstring(z.read("xl/workbook.xml")).find("m:sheets", _NS):
        alvo = rels[s.get(f"{{{_NS['r']}}}id")].lstrip("/")
        alvo = alvo if alvo.startswith("xl/") else "xl/" + alvo
        linhas = []
        for row in ET.fromstring(z.read(alvo)).iter(f"{{{_NS['m']}}}row"):
            idx = int(row.get("r")) - 1
            while len(linhas) <= idx:
                linhas.append([])
            cel = linhas[idx]
            for c in row.findall("m:c", _NS):
                j, t = _col(c.get("r")), c.get("t")
                v = c.find("m:v", _NS)
                if t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(f"{{{_NS['m']}}}t"))
                elif v is None:
                    val = None
                elif t == "s":
                    val = compartilhadas[int(v.text)]
                elif t in ("str", "e", "b"):
                    val = v.text
                else:
                    val = float(v.text)
                while len(cel) <= j:
                    cel.append(None)
                cel[j] = val
        abas[s.get("name")] = linhas
    return abas


def _xlsx_do_zip(conteudo: bytes) -> bytes:
    z = zipfile.ZipFile(io.BytesIO(conteudo))
    return z.read(next(n for n in z.namelist() if n.endswith(".xlsx")))


def _colunas_ideb(linhas: list[list]) -> dict[int, int]:
    """{ano: índice da coluna do IDEB observado}.

    O ano vem do rótulo "IDEB\\n2023\\n(N x P)", não do código VL_OBSERVADO_*:
    no arquivo de 2025 a aba Brasil (Anos Finais) tem o código da coluna 2023 em
    branco. Quando o código existe, conferimos que aponta para a mesma coluna."""
    rot = re.compile(r"IDEB\s+(\d{4})")
    i_rot = next(i for i, l in enumerate(linhas) if any(rot.match(str(c)) for c in l if c))
    cols = {int(rot.match(str(c)).group(1)): j
            for j, c in enumerate(linhas[i_rot]) if c and rot.match(str(c))}
    i_cod = next(i for i, l in enumerate(linhas)
                 if any(str(c).startswith("VL_OBSERVADO_") for c in l if c))
    for j, c in enumerate(linhas[i_cod]):
        if c and str(c).startswith("VL_OBSERVADO_"):
            if cols.get(int(str(c)[-4:])) != j:
                raise ValueError(f"cabeçalho do IDEB inconsistente: {c} na coluna {j}")
    return cols


def _rede(celula) -> str:
    # 'Total (3)(4)' -> 'total' ; 'Pública (4)' -> 'pública'
    return re.sub(r"\s*\(\d+\)", "", str(celula or "")).strip().lower()


def _baixar_edicao(prefixo: str):
    erro = None
    for ano in EDICOES:
        url = f"{BASE}{prefixo}_{ano}.zip"
        try:
            corpo, sha = baixar("inep", url, ext="zip", tentativas=1 if ano > EDICOES[1] else 3)
            return corpo, sha, url
        except RuntimeError as e:
            erro = e
    raise RuntimeError(f"nenhuma edição do IDEB encontrada: {erro}")


def coletar() -> list[dict]:
    with _tls_inep():
        arq_uf = _baixar_edicao("divulgacao_regioes_ufs_ideb")
        arq_br = _baixar_edicao("divulgacao_brasil_ideb")

    linhas = []
    for (corpo, sha, url), nivel in ((arq_uf, "uf"), (arq_br, "br")):
        abas = _ler_xlsx(_xlsx_do_zip(corpo))
        for ind, m in INDICADORES.items():
            sufixo = m["aba_uf"] if nivel == "uf" else m["aba_br"]
            nome_aba = next(a for a in abas if a.endswith(sufixo)
                            and a.startswith("UF" if nivel == "uf" else "Brasil"))
            tab = abas[nome_aba]
            cols = _colunas_ideb(tab)
            vistos = set()
            for l in tab:
                if len(l) < 2 or _rede(l[1]) != REDE[nivel]:
                    continue
                nome = str(l[0]).strip()
                if nivel == "br":
                    if nome != "Brasil":
                        continue
                    uf = "BR"
                elif nome in NOME_PLANILHA:
                    uf = UFS[NOME_PLANILHA[nome]]
                else:
                    continue  # regiões
                vistos.add(uf)
                for ano, j in cols.items():
                    v = l[j] if j < len(l) else None
                    if ano < 2012 or not isinstance(v, float):  # '-' = não se aplica
                        continue
                    linhas.append(dict(indicador=ind, uf=uf, periodo=str(ano),
                                       inicio=f"{ano}-01-01", fim=f"{ano}-12-31",
                                       valor=v, sha256=sha, url=url))
            esperado = 1 if nivel == "br" else 27
            if len(vistos) != esperado:
                raise ValueError(f"{nome_aba}: achei {len(vistos)} territórios, esperava {esperado}")
    return linhas


def catalogo() -> dict:
    comum = (" Nas UFs, rede estadual (escolas administradas pelo governo do estado). No "
             "Brasil, rede pública (estaduais, municipais e federais juntas), porque o governo "
             "federal não administra as redes estaduais. Edições bienais, só nos anos ímpares "
             "(2013, 2015, …, 2025): "
             "não há valor nos anos pares. Por isso, ao avaliar um governo, a comparação usa "
             "a última edição anterior ao mandato e a última edição feita durante ele — "
             "num mandato de 2019 a 2022, por exemplo, 2017 contra 2021. O IDEB 2021 foi afetado pela pandemia "
             "(aprovação automática e baixa participação no Saeb); o INEP recomenda cautela "
             "ao compará-lo com outras edições. As metas do 1º ciclo terminaram em 2021.")
    extra = {
        "ideb_ef_iniciais": " Roraima não tem IDEB estadual nos anos iniciais a partir de "
                            "2017 (rede municipalizada).",
        "ideb_ef_finais": "",
        "ideb_em": " Desde 2017 o Saeb do ensino médio é censitário nas escolas públicas; "
                   "até 2015 era amostral.",
    }
    return {k: dict(nome=m["nome"], unidade="índice (0–10)", melhor="maior", area="Educação",
                    freq="anual",
                    descricao=f"Índice de Desenvolvimento da Educação Básica {m['etapa']}: "
                              f"combina aprovação escolar e nota do Saeb.{comum}{extra[k]}",
                    origem=ORIGEM, link=LINK, variacao="abs")
            for k, m in INDICADORES.items()}
