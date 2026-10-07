"""Gera site/brasil.json: o contorno de cada UF (malha oficial do IBGE) já projetado para SVG.

    python -m etl.mapa_brasil

A malha vem da API de malhas do IBGE (qualidade "mínima", divisão por UF) e é baixada por
etl.comum.baixar, então o arquivo original fica guardado e registrado como qualquer outra fonte.
Projeção: equiretangular com a longitude encolhida pelo cosseno da latitude média do Brasil
(suficiente para um mapa temático). As linhas são simplificadas (Douglas–Peucker) só para o
arquivo ficar leve; nenhuma conta usa essa geometria.
"""
import gzip
import json
import math

from etl.comum import RAIZ, SIGLA, baixar

URL = ("https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
       "?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=UF")
LARGURA = 1000
TOLERANCIA = 0.6  # em unidades do SVG


def _simplificar(pts, tol):
    if len(pts) < 4:
        return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    norma = math.hypot(dx, dy) or 1e-9
    i_max, d_max = 0, -1.0
    for i in range(1, len(pts) - 1):
        x, y = pts[i]
        d = abs(dy * x - dx * y + x2 * y1 - y2 * x1) / norma
        if d > d_max:
            i_max, d_max = i, d
    if d_max <= tol:
        return [pts[0], pts[-1]]
    return _simplificar(pts[: i_max + 1], tol)[:-1] + _simplificar(pts[i_max:], tol)


def _simplificar_anel(pts, tol):
    """Anel fechado: corta no ponto mais distante do início e simplifica as duas metades."""
    if pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 4:
        return pts
    x0, y0 = pts[0]
    m = max(range(len(pts)), key=lambda i: (pts[i][0] - x0) ** 2 + (pts[i][1] - y0) ** 2)
    a = _simplificar(pts[: m + 1], tol)
    b = _simplificar(pts[m:] + [pts[0]], tol)
    return a[:-1] + b[:-1]


def _aneis(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    return [p[0] for p in geom["coordinates"]]


def gerar():
    # a API às vezes responde comprimida mesmo sem pedir; guardamos o GeoJSON descomprimido
    corpo, sha = baixar("ibge", URL, ext="geojson",
                        normalizar=lambda b: gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b)
    feats = json.loads(corpo)["features"]
    todos = [pt for f in feats for anel in _aneis(f["geometry"]) for pt in anel]
    lon0, lon1 = min(p[0] for p in todos), max(p[0] for p in todos)
    lat0, lat1 = min(p[1] for p in todos), max(p[1] for p in todos)
    k = math.cos(math.radians((lat0 + lat1) / 2))
    escala = LARGURA / ((lon1 - lon0) * k)
    altura = (lat1 - lat0) * escala
    proj = lambda p: ((p[0] - lon0) * k * escala, (lat1 - p[1]) * escala)

    ufs = {}
    for f in feats:
        uf = SIGLA[f["properties"]["codarea"]]
        caminhos, maior, area_maior = [], None, -1
        for anel in _aneis(f["geometry"]):
            pts = _simplificar_anel([proj(p) for p in anel], TOLERANCIA)
            if len(pts) < 3:
                continue
            area = abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))) / 2
            if area < 2:  # ilhotas minúsculas não aparecem no tamanho do mapa
                continue
            caminhos.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z")
            if area > area_maior:
                maior, area_maior = pts, area
        # centro visual: centroide do maior polígono
        a = cx = cy = 0.0
        for (x0, y0), (x1, y1) in zip(maior, maior[1:] + maior[:1]):
            c = x0 * y1 - x1 * y0
            a += c; cx += (x0 + x1) * c; cy += (y0 + y1) * c
        ufs[uf] = {"d": "".join(caminhos), "c": [round(cx / (3 * a), 1), round(cy / (3 * a), 1)],
                   "area": round(area_maior)}
    saida = {"largura": LARGURA, "altura": round(altura, 1), "fonte": URL, "sha256": sha, "ufs": ufs}
    destino = RAIZ / "site" / "brasil.json"
    destino.write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")))
    print(f"site/brasil.json: {destino.stat().st_size // 1024} KB, {len(ufs)} UFs")


if __name__ == "__main__":
    gerar()
