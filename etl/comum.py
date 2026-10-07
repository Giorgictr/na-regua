"""Peças comuns aos coletores: download com trilha de auditoria e tabela de UFs.

Cada resposta baixada de uma fonte oficial é guardada byte a byte em
dados/brutos/<fonte>/<sha256>.<ext>, e cada download (mudou ou não) vira uma
linha em dados/proveniencia.csv: quando, de onde, qual hash. Assim qualquer
número do portal pode ser refeito a partir do arquivo exato que a fonte
entregou naquele dia. Pedidos POST guardam também o corpo enviado, em
dados/brutos/<fonte>/<sha256_do_corpo>.post (coluna post_sha256 da procedência).
"""
import csv
import datetime as dt
import gzip
import hashlib
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BRUTOS = RAIZ / "dados" / "brutos"
PROVENIENCIA = RAIZ / "dados" / "proveniencia.csv"

# código IBGE -> sigla (27 UFs) ; 1 = Brasil
UFS = {
    11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO",
    21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL", 28: "SE", 29: "BA",
    31: "MG", 32: "ES", 33: "RJ", 35: "SP",
    41: "PR", 42: "SC", 43: "RS",
    50: "MS", 51: "MT", 52: "GO", 53: "DF",
}
SIGLA = {**{str(k): v for k, v in UFS.items()}, "1": "BR"}
NOME_UF = {
    "RO": "Rondônia", "AC": "Acre", "AM": "Amazonas", "RR": "Roraima", "PA": "Pará",
    "AP": "Amapá", "TO": "Tocantins", "MA": "Maranhão", "PI": "Piauí", "CE": "Ceará",
    "RN": "Rio Grande do Norte", "PB": "Paraíba", "PE": "Pernambuco", "AL": "Alagoas",
    "SE": "Sergipe", "BA": "Bahia", "MG": "Minas Gerais", "ES": "Espírito Santo",
    "RJ": "Rio de Janeiro", "SP": "São Paulo", "PR": "Paraná", "SC": "Santa Catarina",
    "RS": "Rio Grande do Sul", "MS": "Mato Grosso do Sul", "MT": "Mato Grosso",
    "GO": "Goiás", "DF": "Distrito Federal", "BR": "Brasil",
}


GZIP_A_PARTIR = 256 * 1024  # brutos maiores que isso são guardados comprimidos


def baixar(fonte: str, url: str, *, dados: bytes | None = None, ext: str = "json",
           tentativas: int = 4, cabecalhos: dict | None = None,
           normalizar=None) -> tuple[bytes, str]:
    """Baixa `url` (POST se `dados`), guarda o bruto e registra a procedência.

    Devolve (conteúdo, sha256) — o hash vai junto de cada número extraído.

    `normalizar(bytes) -> bytes`, quando dado, é aplicado ANTES do hash: serve para fontes
    que devolvem o mesmo conteúdo em ordem diferente a cada chamada (ex.: IPEADATA). O
    arquivo guardado é o normalizado, e o coletor documenta o que a normalização faz.
    Arquivos grandes vão como <sha256>.<ext>.gz; o hash é sempre do conteúdo descomprimido."""
    erro = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, data=dados, headers={
                "User-Agent": "portal-indicadores-sociais (+github)", **(cabecalhos or {})})
            with urllib.request.urlopen(req, timeout=180) as r:
                corpo = r.read()
            break
        except Exception as e:  # rede instável das fontes públicas: tenta de novo
            erro = e
            # 429 = "muitos pedidos": a fonte pede calma, espera bem mais
            time.sleep((30 if getattr(e, "code", None) == 429 else 5) * (i + 1))
    else:
        raise RuntimeError(f"{fonte}: falhou {url}: {erro}")

    if normalizar:
        corpo = normalizar(corpo)
    sha = hashlib.sha256(corpo).hexdigest()
    pasta = BRUTOS / fonte
    pasta.mkdir(parents=True, exist_ok=True)
    novo = not any(pasta.glob(f"{sha}.*"))
    if novo:
        if len(corpo) > GZIP_A_PARTIR:
            (pasta / f"{sha}.{ext}.gz").write_bytes(gzip.compress(corpo, mtime=0))
        else:
            (pasta / f"{sha}.{ext}").write_bytes(corpo)

    # POST: o corpo do pedido também é guardado (<sha256_do_corpo>.post), senão a url sozinha
    # não basta para refazer a consulta
    sha_post = ""
    if dados:
        sha_post = hashlib.sha256(dados).hexdigest()
        if not any(pasta.glob(f"{sha_post}.post*")):
            if len(dados) > GZIP_A_PARTIR:
                (pasta / f"{sha_post}.post.gz").write_bytes(gzip.compress(dados, mtime=0))
            else:
                (pasta / f"{sha_post}.post").write_bytes(dados)

    _registrar([dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), fonte, url,
                "sim" if dados else "", sha, len(corpo), "sim" if novo else "não", sha_post])
    return corpo, sha


CABECALHO_PROV = ["baixado_em", "fonte", "url", "post", "sha256", "bytes", "conteudo_novo",
                  "post_sha256"]


def _registrar(linha: list) -> None:
    """Acrescenta uma linha a dados/proveniencia.csv. Arquivo antigo (sem a coluna
    post_sha256) é migrado uma vez: cabeçalho novo e a coluna vazia nas linhas antigas."""
    PROVENIENCIA.parent.mkdir(parents=True, exist_ok=True)
    if PROVENIENCIA.exists():
        with PROVENIENCIA.open(encoding="utf-8", newline="") as f:
            primeira = next(csv.reader(f), None)
        if primeira != CABECALHO_PROV:
            with PROVENIENCIA.open(encoding="utf-8", newline="") as f:
                antigas = list(csv.reader(f))[1:]
            tmp = PROVENIENCIA.with_suffix(".csv.tmp")
            with tmp.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(CABECALHO_PROV)
                w.writerows(r + [""] * (len(CABECALHO_PROV) - len(r)) for r in antigas if r)
            tmp.replace(PROVENIENCIA)
    cabecalho = not PROVENIENCIA.exists()
    with PROVENIENCIA.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if cabecalho:
            w.writerow(CABECALHO_PROV)
        w.writerow(linha)
