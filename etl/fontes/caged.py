"""MTE — Novo CAGED: saldo mensal de empregos formais (admissões − desligamentos) por UF.

Fonte de leitura: IPEADATA (API OData v4, http://www.ipeadata.gov.br/api/odata4/),
que republica o Novo CAGED do MTE na base Regional:
  ADMISNC  — Empregados - admissões - Novo Caged sem ajuste (mensal, 2020-01 em diante)
  DESLIGNC — Empregados - demissões - Novo Caged sem ajuste
Cada série vem inteira numa chamada (Brasil, regiões, UFs, regiões metropolitanas e
municípios; ~450 mil registros, ~64 MB). A API ignora $filter nessa função, então
o filtro por nível territorial é feito aqui.

Por que não o MTE direto: as tabelas mensais (.xlsx) em
gov.br/trabalho-e-emprego/.../estatisticas-trabalho/novo-caged respondiam 404 em
out/2026, e os microdados do FTP (ftp.mtps.gov.br/pdet/microdados/NOVO CAGED/)
são grandes demais para este uso.

Conferência (out/2026): saldo Brasil de ago/2026 = 165.827, igual ao divulgado pelo
MTE ("165,8 mil vagas"), e igual à série nacional CAGED12_SALDON12 do IPEADATA.

Ajuste (declarações entregues fora do prazo): o MTE anuncia os totais do ano "com
ajustes". O IPEADATA tem a série COM ajuste só para o Brasil (base Macroeconômica,
CAGED12_SALDONAJU12; out/2026: 2021 = 2.782.502, 2020 = −189.370, já com as revisões
posteriores — o MTE anunciou +142,7 mil para 2020 em jan/2021, antes delas). Por UF só
existe a série sem ajuste. Então: linha Brasil = com ajuste (bate com o total do MTE);
linhas das UFs = sem ajuste (ADMISNC − DESLIGNC). Por isso a soma das UFs não fecha
com o Brasil.

O CAGED antigo (até dez/2019) não tem série por UF no IPEADATA; a série aqui
começa em jan/2020 e não deve ser emendada com o CAGED antigo (mudança de
metodologia: eSocial, inclusão de temporários e intermitentes etc.).
"""
import calendar
import json

from etl.comum import UFS, baixar

ORIGEM = "MTE — Novo CAGED (via IPEADATA)"
LINK = "http://www.ipeadata.gov.br/Default.aspx"  # base Regional > Emprego > séries ADMISNC/DESLIGNC
API = "http://www.ipeadata.gov.br/api/odata4/"
ADMISSOES, DESLIGAMENTOS = "ADMISNC", "DESLIGNC"
SALDO_BR_AJUSTADO = "CAGED12_SALDONAJU12"


def _ordenado(corpo: bytes) -> bytes:
    """Mesmo dado, em ordem fixa (o IPEADATA pode mudar a ordem entre chamadas)."""
    linhas = sorted(json.loads(corpo)["value"], key=lambda r: r["VALDATA"])
    return json.dumps({"value": linhas}, ensure_ascii=False, sort_keys=True).encode()


def _so_brasil_e_ufs(corpo: bytes) -> bytes:
    """O IPEADATA devolve ~64 MB com todos os municípios, em ordem diferente a cada chamada.
    Guardamos só as linhas de Brasil e Estados, ordenadas — o mesmo dado, recortado, para que
    o hash só mude quando a fonte mudar de fato."""
    linhas = [r for r in json.loads(corpo)["value"] if r["NIVNOME"] in ("Brasil", "Estados")]
    linhas.sort(key=lambda r: (r["NIVNOME"], str(r["TERCODIGO"]), r["VALDATA"]))
    return json.dumps({"value": linhas}, ensure_ascii=False, sort_keys=True).encode()


def _serie(codigo: str) -> tuple[dict, str, str]:
    """{(uf, 'AAAA-MM'): valor} só para Brasil e UFs, mais sha256 e url do bruto."""
    url = f"{API}ValoresSerie(SERCODIGO='{codigo}')"
    corpo, sha = baixar("caged", url, ext="json", normalizar=_so_brasil_e_ufs)
    valores = {}
    for r in json.loads(corpo)["value"]:
        nivel = r["NIVNOME"]
        if nivel == "Brasil":
            uf = "BR"
        elif nivel == "Estados":
            uf = UFS[int(r["TERCODIGO"])]
        else:
            continue
        if r["VALVALOR"] is None:
            continue
        valores[(uf, r["VALDATA"][:7])] = float(r["VALVALOR"])
    if not valores:
        raise ValueError(f"{codigo}: nenhuma linha de Brasil/UF")
    return valores, sha, url


def _saldo_br_ajustado() -> tuple[dict, str, str]:
    """{'AAAA-MM': saldo com ajuste} do Brasil (CAGED12_SALDONAJU12)."""
    url = f"{API}ValoresSerie(SERCODIGO='{SALDO_BR_AJUSTADO}')"
    corpo, sha = baixar("caged", url, ext="json", normalizar=_ordenado)
    valores = {r["VALDATA"][:7]: float(r["VALVALOR"])
               for r in json.loads(corpo)["value"] if r["VALVALOR"] is not None}
    if not valores:
        raise ValueError(f"{SALDO_BR_AJUSTADO}: série vazia")
    return valores, sha, url


def _linha(uf, mes, valor, sha, url):
    ano, m = int(mes[:4]), int(mes[5:])
    return dict(indicador="caged_saldo", uf=uf, periodo=mes, inicio=f"{mes}-01",
                fim=f"{mes}-{calendar.monthrange(ano, m)[1]:02d}", valor=valor,
                sha256=sha, url=url)


def coletar() -> list[dict]:
    adm, sha_adm, url_adm = _serie(ADMISSOES)
    desl, sha_desl, url_desl = _serie(DESLIGAMENTOS)
    br, sha_br, url_br = _saldo_br_ajustado()
    ufs = {uf for uf, _ in adm}
    if len(ufs) != 28:
        raise ValueError(f"esperava Brasil + 27 UFs, veio {len(ufs)}")
    linhas = []
    # UFs: saldo sem ajuste = admissões − desligamentos (os dois brutos citados)
    for (uf, mes), a in sorted(adm.items()):
        if uf == "BR" or (uf, mes) not in desl:
            continue
        linhas.append(_linha(uf, mes, a - desl[(uf, mes)], f"{sha_adm},{sha_desl}",
                             f"{url_adm} ; {url_desl}"))
    # Brasil: saldo com ajuste, o mesmo conceito dos totais anunciados pelo MTE
    linhas += [_linha("BR", mes, v, sha_br, url_br) for mes, v in sorted(br.items())]
    return linhas


def catalogo() -> dict:
    return {"caged_saldo": dict(
        nome="Saldo de empregos formais (Novo CAGED)", unidade="empregos", melhor="maior",
        area="Trabalho", freq="mensal", variacao="abs", agregacao="soma", leitura="soma",
        origem=ORIGEM, link=LINK,
        descricao="Admissões menos desligamentos de empregados com carteira no mês, pelo "
                  "Novo CAGED (MTE). Brasil: saldo COM ajuste (inclui declarações entregues "
                  "fora do prazo; série CAGED12_SALDONAJU12 do IPEADATA), o mesmo conceito dos "
                  "totais anuais do MTE, já com revisões — por isso 2020 aparece negativo "
                  "(cerca de −189 mil), embora o MTE tenha anunciado +142,7 mil em jan/2021. "
                  "Estados: só existe a série SEM ajuste (admissões ADMISNC − desligamentos "
                  "DESLIGNC), que difere dos números anunciados — em 2021, por exemplo, o "
                  "Brasil sem ajuste soma 2,85 milhões e com ajuste 2,78 milhões. Por isso a "
                  "soma dos estados não fecha com o Brasil. Série começa em jan/2020: o CAGED "
                  "antigo (até 2019) tem metodologia diferente e não é comparável.")}
