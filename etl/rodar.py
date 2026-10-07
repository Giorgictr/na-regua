"""Atualiza o portal: roda cada coletor, junta tudo e gera site/dados.json.

    python -m etl.rodar            # todas as fontes
    python -m etl.rodar ibge inep  # só algumas
    python -m etl.rodar --so-site  # não coleta; só regera site/dados.json

Se uma fonte falhar (site fora do ar, formato mudou), as linhas dela da última
coleta boa são mantidas e a falha fica registrada em dados/status.json — uma
fonte instável nunca apaga dado já auditado.
"""
import csv
import datetime as dt
import importlib
import json
import sys
import traceback

from etl.comum import NOME_UF, RAIZ

# toda fonte é um módulo em etl/fontes/ com coletar() e catalogo()
FONTES = sorted(p.stem for p in (RAIZ / "etl" / "fontes").glob("*.py") if p.stem != "__init__")
# status: "preliminar" quando a fonte ainda vai revisar; ic95: meia-largura do intervalo de 95%
# (erro amostral, nas pesquisas por amostra). sha256/url podem listar vários arquivos (", " e " ; ").
CAMPOS = ["fonte", "indicador", "uf", "periodo", "inicio", "fim", "valor", "sha256", "url", "status", "ic95"]
TABELA = RAIZ / "dados" / "indicadores.csv"
CATALOGO = RAIZ / "dados" / "catalogo.json"
STATUS = RAIZ / "dados" / "status.json"
MANDATOS = RAIZ / "dados" / "mandatos.csv"
SAIDA = RAIZ / "site" / "dados.json"


def _ler_csv(caminho):
    if not caminho.exists():
        return []
    with caminho.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def atualizar(fontes):
    linhas = _ler_csv(TABELA)
    catalogo = json.loads(CATALOGO.read_text()) if CATALOGO.exists() else {}
    status = json.loads(STATUS.read_text()) if STATUS.exists() else {}
    agora = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    for nome in fontes:
        # marca "em andamento" antes: se o processo for interrompido (tempo esgotado), fica registrado
        anterior = status.get(nome, {})
        status[nome] = {"ok": False, "em": agora, "erro": "coleta interrompida (tempo esgotado ou erro fatal)",
                        "ultima_ok": anterior.get("em") if anterior.get("ok") else anterior.get("ultima_ok")}
        STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=1, sort_keys=True))
        try:
            mod = importlib.import_module(f"etl.fontes.{nome}")
            novas = mod.coletar()
            if not novas:
                raise RuntimeError("coletor não devolveu nenhuma linha")
            linhas = [l for l in linhas if l["fonte"] != nome]
            linhas += [{"fonte": nome, **l} for l in novas]
            for k, v in mod.catalogo().items():
                catalogo[k] = {**v, "fonte": nome}
            status[nome] = {"ok": True, "em": agora, "linhas": len(novas)}
            print(f"[ok]    {nome}: {len(novas)} linhas")
        except Exception as e:
            status[nome] = {"ok": False, "em": agora, "erro": f"{type(e).__name__}: {e}",
                            "ultima_ok": anterior.get("em") if anterior.get("ok")
                            else anterior.get("ultima_ok")}
            print(f"[falha] {nome}: {e}", file=sys.stderr)
            traceback.print_exc()

    linhas.sort(key=lambda l: (l["fonte"], l["indicador"], l["uf"], l["inicio"]))
    with TABELA.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, restval="", extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)
    CATALOGO.write_text(json.dumps(catalogo, ensure_ascii=False, indent=1, sort_keys=True))
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=1, sort_keys=True))
    return linhas, catalogo, status


_CACHE_ARQ = {}


def _arquivo(sha):
    """Caminho (relativo a dados/) do arquivo bruto com esse hash — a extensão varia por fonte."""
    if not _CACHE_ARQ:
        for p in (RAIZ / "dados" / "brutos").glob("*/*"):
            _CACHE_ARQ[p.name.split(".")[0]] = str(p.relative_to(RAIZ / "dados"))
    return _CACHE_ARQ.get(sha, "")


def _carimbar_versao():
    """Põe ?v=<hash> nos links de app.js/estilo.css do index.html para furar o cache."""
    import hashlib
    import re
    site = RAIZ / "site"
    v = hashlib.sha256((site / "app.js").read_bytes() + (site / "estilo.css").read_bytes()).hexdigest()[:10]
    vd = hashlib.sha256((site / "dados.json").read_bytes()).hexdigest()[:10]
    html = (site / "index.html").read_text()
    html = re.sub(r'(app\.js|estilo\.css)(\?v=[0-9a-f]+)?"', rf'\1?v={v}"', html)
    html = re.sub(r'data-dados="[0-9a-f]*"', f'data-dados="{vd}"', html)
    (site / "index.html").write_text(html)


def gerar_site(linhas, catalogo, status):
    """Formato compacto para o navegador: séries[ind][uf] = [[periodo, inicio, fim, valor]]."""
    series, origem = {}, {}
    for l in linhas:
        if l["indicador"] not in catalogo:
            continue
        # compacto: [periodo, valor, ic95?, "p"?] — início/fim saem do rótulo no navegador
        v = float(l["valor"])  # contagens ficam exatas; frações com 8 algarismos significativos
        ponto = [l["periodo"], int(v) if v.is_integer() and abs(v) < 2**53 else float(f"{v:.8g}")]
        if l.get("ic95") or l.get("status"):
            ponto += [float(f'{float(l["ic95"]):.3g}') if l.get("ic95") else None, "p" if l.get("status") == "preliminar" else ""]
        if l["periodo"].isdigit() and not l["inicio"].endswith("-01-01"):
            catalogo[l["indicador"]]["mes_inicio"] = int(l["inicio"][5:7])  # ex.: PRODES (ago–jul)
        series.setdefault(l["indicador"], {}).setdefault(l["uf"], []).append(ponto)
        o = origem.setdefault(l["indicador"], {}).setdefault(l["uf"], {"sha256": [], "url": []})
        for h, u in zip(l["sha256"].split(","), l["url"].split(" ; ") + [""] * 9):
            h = h.strip()
            if h and h not in o["sha256"]:  # todos os arquivos que entraram na série, sem repetir
                o["sha256"].append(h); o["url"].append(u.strip())
    # a trilha de arquivos de cada indicador vai em site/origem/<indicador>.json, carregada só na
    # página do indicador (é a maior parte do volume e quase ninguém precisa dela na abertura)
    pasta_origem = RAIZ / "site" / "origem"
    pasta_origem.mkdir(exist_ok=True)
    for ind, por_uf in origem.items():
        for o in por_uf.values():
            o["arquivos"] = [_arquivo(h) for h in o["sha256"]]
        (pasta_origem / f"{ind}.json").write_text(json.dumps(por_uf, ensure_ascii=False, separators=(",", ":")))
    mandatos = _ler_csv(MANDATOS)
    SAIDA.write_text(json.dumps({
        "gerado_em": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "catalogo": catalogo, "status": status, "ufs": NOME_UF,
        "mandatos": mandatos, "series": series,
    }, ensure_ascii=False, separators=(",", ":")))
    _carimbar_versao()
    print(f"site/dados.json: {SAIDA.stat().st_size // 1024} KB, {len(series)} indicadores, "
          f"{len(mandatos)} mandatos")


if __name__ == "__main__":
    if sys.argv[1:] == ["--so-site"]:
        # relê os metadados de cada coletor (sem baixar nada) e regera o site
        cat = json.loads(CATALOGO.read_text())
        for nome in FONTES:
            for k, v in importlib.import_module(f"etl.fontes.{nome}").catalogo().items():
                cat[k] = {**v, "fonte": nome}
        CATALOGO.write_text(json.dumps(cat, ensure_ascii=False, indent=1, sort_keys=True))
        gerar_site(_ler_csv(TABELA), cat, json.loads(STATUS.read_text()))
        sys.exit(0)
    escolhidas = sys.argv[1:] or FONTES
    gerar_site(*atualizar(escolhidas))
    # código de saída != 0 só se TODAS falharam (o agendador avisa), parcial segue
    st = json.loads(STATUS.read_text())
    sys.exit(0 if any(st.get(f, {}).get("ok") for f in escolhidas) else 1)
