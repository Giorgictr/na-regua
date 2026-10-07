"use strict";
// Na Régua — tudo calculado no navegador a partir de dados.json (gerado por etl/rodar.py).

const ORDEM_UF = ["RO", "AC", "AM", "RR", "PA", "AP", "TO", "MA", "PI", "CE", "RN", "PB", "PE",
  "AL", "SE", "BA", "MG", "ES", "RJ", "SP", "PR", "SC", "RS", "MS", "MT", "GO", "DF"];
// mapa do Brasil em blocos: [linha, coluna]
const BLOCOS = {
  RR: [0, 1], AP: [0, 3],
  AM: [1, 1], PA: [1, 2], MA: [1, 3], CE: [1, 4], RN: [1, 5],
  AC: [2, 0], RO: [2, 1], TO: [2, 2], PI: [2, 3], PE: [2, 4], PB: [2, 5],
  MT: [3, 1], GO: [3, 2], BA: [3, 3], SE: [3, 4], AL: [3, 5],
  MS: [4, 1], DF: [4, 2], MG: [4, 3], ES: [4, 4],
  PR: [5, 2], SP: [5, 3], RJ: [5, 4],
  SC: [6, 2], RS: [7, 2],
};
// "governo do Pará", "da Bahia", "de São Paulo"
const PREP = { AC: "do", AP: "do", AM: "do", CE: "do", ES: "do", MA: "do", PA: "do", PI: "do", PR: "do", RJ: "do",
  RN: "do", RS: "do", TO: "do", DF: "do", BA: "da", PB: "da" };
const prep = (uf) => `${PREP[uf] ?? "de"} ${D.ufs[uf]}`;
const ORDEM_AREAS = ["Economia", "Trabalho", "Renda", "Proteção social", "Saúde", "Educação", "Segurança",
  "Contas públicas", "Moradia", "Meio ambiente", "Cultura", "Demografia"];
const HOJE = new Date().toISOString().slice(0, 10);
const INICIO_REGUA = "2011-01-01";
const ESTREITO = () => innerWidth < 700;
// quando o total da série não é "o Brasil" (ex.: desmatamento = total do bioma)
const ROTULO_TOTAL = { desmatamento_amazonia: "Amazônia Legal", desmatamento_cerrado: "Cerrado" };
const nomeUF = (ind, uf) => uf === "BR" && ROTULO_TOTAL[ind] ? ROTULO_TOTAL[ind] : D.ufs[uf];

let D;
const $ = (sel, r = document) => r.querySelector(sel);
const SVGNS = "http://www.w3.org/2000/svg";
function s(tag, attrs = {}, filhos = []) {
  const e = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    k === "text" ? (e.textContent = v) : e.setAttribute(k, v);
  }
  for (const f of [].concat(filhos)) if (f) e.append(f);
  return e;
}
const esc = (x) => String(x ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const dataBR = (iso) => iso ? iso.slice(0, 10).split("-").reverse().join("/") : "";
const sobrenome = (n) => n.split(" ").filter((p) => !/^(da|de|do|dos|das|e)$/i.test(p)).at(-1);
const NOMES_CURTOS = { "Dilma Rousseff": "Dilma", "Michel Temer": "Temer", "Jair Bolsonaro": "Bolsonaro", "Luiz Fernando Pezão": "Pezão",
  "Tarcísio de Freitas": "Tarcísio", "Jerônimo Rodrigues": "Jerônimo", "Wanderlei Barbosa": "Wanderlei", "Helder Barbalho": "Helder",
  "Cláudio Castro": "Castro", "Ibaneis Rocha": "Ibaneis", "Celina Leão": "Celina", "Elmano de Freitas": "Elmano", "Camilo Santana": "Camilo",
  "Rui Costa": "Rui Costa", "Jaques Wagner": "Wagner", "Flávio Dino": "Dino", "Carlos Brandão": "Brandão", "Fátima Bezerra": "Fátima",
  "Paulo Câmara": "Câmara", "Raquel Lyra": "Raquel", "Eduardo Campos": "Campos", "Romeu Zema": "Zema", "Ratinho Junior": "Ratinho Jr.",
  "Eduardo Leite": "Leite", "Ronaldo Caiado": "Caiado", "Gladson Cameli": "Gladson", "Waldez Góes": "Waldez", "Clécio Luís": "Clécio",
  "Renato Casagrande": "Casagrande", "Paulo Hartung": "Hartung", "Reinaldo Azambuja": "Azambuja", "Eduardo Riedel": "Riedel",
  "Geraldo Alckmin": "Alckmin", "João Doria": "Doria", "Márcio França": "França", "Rodrigo Garcia": "Garcia", "Fernando Pimentel": "Pimentel",
  "Antonio Anastasia": "Anastasia", "Mateus Simões": "Simões", "Rafael Fonteles": "Fonteles", "Wellington Dias": "W. Dias",
  "Fábio Mitidieri": "Mitidieri", "Belivaldo Chagas": "Belivaldo", "Jackson Barreto": "Jackson", "Marcelo Déda": "Déda",
  "João Azevêdo": "Azevêdo", "Ricardo Coutinho": "Coutinho", "Mauro Mendes": "Mauro Mendes", "Mauro Carlesse": "Carlesse",
  "Marcelo Miranda": "Miranda", "Wilson Lima": "W. Lima", "Antonio Denarium": "Denarium", "Marcos Rocha": "M. Rocha",
  "Renan Filho": "Renan Filho", "Paulo Dantas": "Dantas", "Jorginho Mello": "Jorginho", "Carlos Moisés": "Moisés",
  "Raimundo Colombo": "Colombo", "José Ivo Sartori": "Sartori", "Tarso Genro": "Tarso", "Beto Richa": "Richa", "Marconi Perillo": "Marconi",
  "Rodrigo Rollemberg": "Rollemberg", "Agnelo Queiroz": "Agnelo", "Simão Jatene": "Jatene", "Robinson Faria": "Robinson" };
const nomeCurto = (n) => NOMES_CURTOS[n] ?? (n.length <= 14 ? n : sobrenome(n));

// ---------------- tema e cores ----------------
const escuro = () => {
  const t = document.documentElement.dataset.theme;
  return t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
};
// divergente: pior (vermelho) ← neutro → melhor (azul)
const DIV = {
  claro: ["#a8322b", "#d6453d", "#ec8a80", "#f6c6bf", "#e6e8e3", "#bdd3f5", "#7fa9ec", "#2a6fdb", "#1b4f9f"],
  escuro: ["#f0a39c", "#e5675f", "#b5463f", "#6d302b", "#4a524d", "#24406b", "#2f5fae", "#5b93ea", "#a9c6f5"],
};
// sequencial neutro (tinta), para quantidades sem juízo de valor
const SEQ = {
  claro: ["#eceeea", "#d3d8d2", "#b4bcb5", "#909a92", "#6c776f", "#4b554e", "#2c3530"],
  escuro: ["#232825", "#323a35", "#47504a", "#606a63", "#7f8981", "#a7b0a9", "#d6dcd7"],
};
function textoSobre(hex) {
  const n = parseInt(hex.slice(1), 16), r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const L = [r, g, b].map((c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; });
  return 0.2126 * L[0] + 0.7152 * L[1] + 0.0722 * L[2] > 0.3 ? "#111814" : "#ffffff";
}

// ---------------- números ----------------
const cat = (ind) => D.catalogo[ind];
function casas(ind) {
  const c = cat(ind), u = c.unidade;
  if (c.casas != null) return c.casas;
  if (u.startsWith("%")) return 1;
  if (u.startsWith("índice")) return u.includes("0–1)") ? 3 : 1;
  if (/milh|\bbi\b/.test(u)) return 1;
  if (/^R\$/.test(u) || /^(empregos|focos|habitantes|salas|projetos|famílias|km²)$/.test(u)) return 0;
  return 1;
}
const fmtN = (v, k) => v.toLocaleString("pt-BR", { minimumFractionDigits: k, maximumFractionDigits: k }).replace("-", "−");
// casas suficientes para que dois valores diferentes não apareçam iguais ("1,4 → 1,4")
function casasPar(ind, a, b) {
  let k = casas(ind);
  while (a !== b && k < 4 && fmtN(a, k) === fmtN(b, k)) k++;
  return k;
}
function fmt(ind, v, k = casas(ind)) {
  if (v == null || Number.isNaN(v)) return "—";
  const u = cat(ind).unidade, n = fmtN(v, k);
  if (u.startsWith("%")) return n + "%";
  if (u.startsWith("R$") && !/milh|\bbi\b/.test(u)) return "R$ " + n;
  return n;
}
// sufixo de unidade para frases e tabelas ("12,8%" já traz a unidade)
function unidadeCurta(ind) {
  const u = cat(ind).unidade;
  if (u === "%" || (u.startsWith("R$") && !/milh|\bbi\b/.test(u))) return "";
  if (u.startsWith("% ")) return u.slice(2);
  if (u.startsWith("índice")) return "";
  return u;
}
// "US$ 334,1 bi", "2,0 milhões de vagas", "214,2 milhões de habitantes"
function humano(ind, v) {
  const u = cat(ind).unidade, a = Math.abs(v);
  const escala = (x, unidade = "") => {
    const ax = Math.abs(x);
    if (ax >= 1e9) return `${fmtN(x / 1e9, 1)} bi${unidade}`;
    if (ax >= 1e6) return `${fmtN(x / 1e6, 1)} ${ax < 2e6 ? "milhão" : "milhões"}${unidade ? " de" + unidade : ""}`;
    if (ax >= 1e4) return `${fmtN(x / 1e3, 1)} mil${unidade ? " " + unidade.trim() : ""}`;
    return null;
  };
  if (u === "US$ bi") return `US$ ${fmtN(v, 1)} bi`;
  let m = /^(US\$|R\$) milhões(.*)$/.exec(u);
  if (m) { const t = escala(v * 1e6); return t ? `${m[1]} ${t}${m[2] ? " (" + m[2].trim().replace(/^de /, "valores de ") + ")" : ""}` : null; }
  const nomes = { habitantes: " habitantes", empregos: " vagas", "famílias": " famílias" };
  if (nomes[u] && a >= 1e4) return escala(v, nomes[u]);
  return null;
}
const fmtU = (ind, v, k) => { if (v != null && !Number.isNaN(v)) { const h = humano(ind, v); if (h) return h; } return fmtU0(ind, v, k); };
// unidade por extenso depois do número ("78,6% do PIB", "217,3% da RCL")
const sufixoPct = (ind) => { const u = cat(ind).unidade; return u.startsWith("% ") ? u.slice(2) : ""; };
const fmtU0 = (ind, v, k) => {
  const x = fmt(ind, v, k), u = unidadeCurta(ind);
  if (x === "—") return x;
  if (cat(ind).unidade.startsWith("% ")) return `${x} ${sufixoPct(ind)}`;
  return !u || cat(ind).unidade.startsWith("%") ? x : `${x} ${u}`;
};
// quantidades absolutas (população, km², focos, US$): não faz sentido no mesmo eixo que o Brasil
const extensivo = (ind) => cat(ind).extensivo ?? /^(habitantes|km²|focos|salas|projetos|famílias|empregos)$|milh|\bbi\b/.test(cat(ind).unidade);
function modoVar(ind) {
  const c = cat(ind);
  if (c.variacao) return c.variacao;
  if (c.unidade.startsWith("%")) return "pp";
  if (c.unidade.startsWith("índice") || c.unidade === "anos") return "abs";
  return "pct";
}
function variacao(ind, a, b) {
  if (a == null || b == null) return null;
  if (modoVar(ind) === "pct") return a === 0 ? null : (b / a - 1) * 100 * (a < 0 ? -1 : 1);
  return b - a;
}
function fmtVarAbs(ind, d) {
  const e = escalaPar(ind, d, d);
  if (modoVar(ind) === "abs" && e.div > 1) return `${e.pre}${fmtN(Math.abs(d) / e.div, 1)}${e.suf}`;
  const m = modoVar(ind), a = Math.abs(d);
  if (m === "pp") return fmtN(a, 1) + " p.p.";
  if (m === "pct") return fmtN(a, a >= 100 ? 0 : 1) + "%";
  const h = humano(ind, a);
  if (h) return h;
  const u = unidadeCurta(ind);
  return fmtN(a, casas(ind)) + (u ? " " + u : "");
}
const fmtVar = (ind, d) => d == null ? "—" : (d > 0 ? "+" : d < 0 ? "−" : "") + fmtVarAbs(ind, d);
// >0 = melhorou; null = indicador sem direção (câmbio, gasto por área, população…)
function sentido(ind, d) {
  const m = cat(ind).melhor;
  if (d == null || !m || m === "neutro") return null;
  return m === "menor" ? -d : d;
}
function limiar(ind) {
  const c = cat(ind);
  if (c.limiar != null) return c.limiar;
  const m = modoVar(ind);
  if (m === "pp") return 0.5;
  if (m === "pct") return 2;
  if (c.unidade.includes("0–1)")) return 0.005;
  if (c.unidade.includes("0–10")) return 0.1;
  return 10 ** -casas(ind);
}
function classe(ind, d, lim = limiar(ind)) {
  if (d == null || sentido(ind, 1) == null) return d != null && Math.abs(d) < lim ? "igual-neutra" : "neutra";
  if (Math.abs(d) < lim) return "igual";
  const sg = sentido(ind, d);
  return sg == null ? "neutra" : sg > 0 ? "melhor" : "pior";
}
// selo da variação: a seta segue o sinal; a cor e a palavra dizem se foi bom ou ruim
function selo(ind, d, r = null) {
  if (d == null) return "";
  let dTxt = null;
  if (r && r.herdado != null && r.atual != null && !r.leitura) { const ex = exibirPar(ind, r.herdado, r.atual); if (ex.dVis != null) d = ex.dVis; dTxt = ex.dTxt; }
  const fva = (x) => dTxt ?? fmtVarAbs(ind, x);
  if (r?.semVeredito) return `<span class="selo neutra" title="${esc(r.semVeredito)}">${d > 0 ? "▲" : d < 0 ? "▼" : "="} ${esc(fva(d))} <span class="palavra">sem veredito</span></span>`;
  // variação calculada a partir dos valores exatamente como aparecem na frase
  if (r && r.herdado != null && r.atual != null && !r.leitura) { const dv = exibirPar(ind, r.herdado, r.atual).dVis; if (dv != null) d = dv; }
  let c = classe(ind, d, Math.max(limiar(ind), r?.icD ?? 0));
  const estavel = c === "igual" || c === "igual-neutra";
  const seta = estavel ? "=" : d > 0 ? "▲" : "▼";
  const palavra = { melhor: "melhorou", pior: "piorou", igual: "estável", "igual-neutra": "estável", neutra: "" }[c];
  if (c === "igual-neutra" || c === "neutra") return `<span class="selo neutra">${d > 0 ? "▲" : d < 0 ? "▼" : "="} ${esc(fva(d))}</span>`;
  if (r?.prelim) return `<span class="selo previa" title="O último ano (${r.final}) é preliminar e fica fora da contagem."><span aria-hidden="true">${seta}</span> ${esc(fva(d))} <span class="palavra">prévia</span></span>`;
  const tit = r?.dentroDaMargem ? ` title="A variação (${esc(fmtVar(ind, d))}) está dentro da margem de erro da pesquisa (±${esc(fmtVarAbs(ind, r.icD))})."` : "";
  return `<span class="selo ${c}"${tit}><span aria-hidden="true">${seta}</span> ${estavel ? (r?.dentroDaMargem ? esc(fmtVar(ind, d)) : "") : esc(fva(d))}${palavra ? ` <span class="palavra">${r?.dentroDaMargem ? "dentro da margem de erro" : palavra}</span>` : ""}</span>`;
}
// Comparação com o Brasil por PROGRESSO RELATIVO: quanto do "problema" inicial cada um reduziu.
// Ex.: pobreza 15,7% → 10,1% (−36%) num estado contra 26,5% → 19,3% (−27%) no Brasil = melhor.
// Evita o efeito teto: quem já estava perto do ideal não é punido por ter menos espaço para cair.
// Regras por indicador (decisões de método, documentadas em "Como ler"):
// - como comparar com o Brasil: "lacuna" (quanto da distância ao ideal foi fechada), "pp" (diferença de
//   pontos) ou "relativo" (variação %). Ocupação/carteira/creche não têm 100% como meta; desemprego não tem 0.
const MODO_BR = { nivel_ocupacao: "pp", emprego_carteira: "pp", escolarizacao_0a3: "pp", informalidade: "pp",
  cobertura_triplice_viral: "pp", desocupacao: "relativo", subutilizacao: "relativo" };
// - sem veredito: o número existe, mas "subiu/caiu" não diz se o governo foi melhor ou pior
const SEM_VEREDITO = {
  estupro: "Mais registros podem refletir mais denúncias, não mais crimes.",
  feminicidio: "A classificação de feminicídio ainda varia muito entre estados e anos.",
  esperanca_vida: "A série anual é projeção demográfica do IBGE, não medição.",
  obitos_intencao_indeterminada: "Mais mortes de intenção indeterminada indicam pior registro, não necessariamente mais violência.",
};
// - a regra de "salto brusco = provável mudança de registro" só vale para registros administrativos
//   (polícia, cartórios de óbito, escolas, declarações fiscais) — nunca para pesquisas ou contas nacionais
const VERIFICAR_SALTOS = new Set(["abandono_em", "abandono_ef_finais", "distorcao_em", "cobertura_triplice_viral"]);
// - ressalvas que acompanham o veredito
// (homicídios/MVI/CVLI: a ressalva só aparece se a taxa caiu E as mortes de intenção indeterminada subiram no estado)
const RESSALVA_RECLASS = new Set(["homicidios", "mvi", "cvli"]);
function ressalvaDe(ind, uf, a, b, d) {
  if (!RESSALVA_RECLASS.has(ind) || !(d < 0) || !D.catalogo.obitos_intencao_indeterminada) return "";
  const I = anual("obitos_intencao_indeterminada", uf), x = I.get(a), y = I.get(b);
  if (x == null || y == null || !(y > x)) return "";
  return `No mesmo período, as mortes de intenção indeterminada ${uf === "BR" ? "no país" : "no estado"} subiram de ${fmtN(x, 1)} para ${fmtN(y, 1)} por 100 mil — parte da queda pode ser reclassificação.`;
}
// - indicadores só estaduais que não aparecem no escopo Brasil (há equivalente nacional)
const SO_ESTADOS = new Set(["pib_crescimento_uf"]);
// - anos atípicos que não servem de ponta de comparação (pandemia)
const ATIPICOS = { ideb_ef_iniciais: [2021], ideb_ef_finais: [2021], ideb_em: [2021], abandono_em: [2020, 2021], abandono_ef_finais: [2020, 2021],
  mortalidade_materna: [2020, 2021] };
// séries bienais: a base tem de estar a até 2 anos da posse e a edição do 1º ano não pode ser o ponto final
const BIENAIS = new Set(["ideb_ef_iniciais", "ideb_ef_finais", "ideb_em"]);
function problema(ind, v) {
  const c = cat(ind), u = c.unidade;
  if (u.startsWith("%") && !u.includes("variação") && !u.includes("PIB") && !u.includes("RCL") && !u.includes("receita") && v >= 0 && v <= 100)
    return c.melhor === "menor" ? v : 100 - v;
  if (u.includes("0–10")) return c.melhor === "maior" ? 10 - v : v;
  if (u.includes("0–1)")) return c.melhor === "maior" ? 1 - v : v;
  return null;
}
const arred = (v, k) => v == null ? null : +v.toFixed(k);
function seloBR(ind, r) {
  if (!r || r.prelim || r.semVeredito) return "";
  if (r.leitura) return r.pBR == null || extensivo(ind) ? "" : `<span class="selo neutra">Brasil: ${cat(ind).unidade.includes("variação")
    ? esc(fmtN(r.pBR, 1)) + "%" + (r.base === r.final ? ` em ${r.final}` : " ao ano") : esc(fmtU(ind, r.pBR))}</span>`;
  if (!r.vBR) return "";
  const tit = explicaBR(ind, r);
  if (r.vBR === "igual") return `<span class="selo igual contorno" title="${esc(tit)}">igual ao Brasil</span>`;
  return `<span class="selo ${r.vBR} contorno" title="${esc(tit)}">${r.vBR} que o Brasil</span>`;
}
function explicaBR(ind, r) {
  if (!r || r.rel == null) return "";
  const n0 = (x) => fmtN(Math.abs(x), Math.abs(x) < 10 ? 1 : 0);
  let t;
  if (r.leitura === "media") return `Estado: ${fmtN(r.pUF, 1)}% ao ano; Brasil: ${fmtN(r.pBR, 1)}% ao ano.`;
  if (r.modo === "lacuna") t = `Estado ${r.pUF >= 0 ? "reduziu" : "aumentou"} ${n0(r.pUF)}% do problema que tinha; Brasil ${r.pBR >= 0 ? "reduziu" : "aumentou"} ${n0(r.pBR)}%`;
  else if (r.modo === "pp") t = `Estado ${fmtVar(ind, r.d)}; Brasil ${fmtVar(ind, r.dBR)}`;
  else t = `Estado ${r.pUF >= 0 ? "melhorou" : "piorou"} ${n0(r.pUF)}%; Brasil ${r.pBR >= 0 ? "melhorou" : "piorou"} ${n0(r.pBR)}%`;
  if (r.vBR === "igual") t += r.motivoBR ? ` (${r.motivoBR})` : " (diferença dentro da margem)";
  return t + ".";
}

// ---------------- séries ----------------
const serie = (ind, uf) => D.series[ind]?.[uf] ?? [];
const meio = (p) => new Date((Date.parse(p[1]) + Date.parse(p[2])) / 2).toISOString().slice(0, 10);
// ano = ano do RÓTULO do período (PRODES "2019" = ago/2018–jul/2019 conta como 2019)
const anoDe = (p) => +p[0].slice(0, 4);
const _cacheAnual = new Map();
function anual(ind, uf) { return anualDet(ind, uf).v; }
function anualDet(ind, uf) {
  const k = ind + "|" + uf;
  if (!_cacheAnual.has(k)) _cacheAnual.set(k, calcAnual(ind, uf));
  return _cacheAnual.get(k);
}
function calcAnual(ind, uf) {
  const c = cat(ind), porAno = new Map();
  for (const p of serie(ind, uf)) {
    const a = anoDe(p);
    (porAno.get(a) ?? porAno.set(a, []).get(a)).push(p);
  }
  const precisa = c.freq === "trimestral" ? 4 : c.freq === "mensal" ? 12 : 1;
  const out = new Map(), ic = new Map(), prelim = new Set();
  for (const [a, ps] of porAno) {
    if (ps.length < precisa) continue;
    ps.sort((x, y) => x[1].localeCompare(y[1]));
    const vs = ps.map((p) => p[3]);
    const usados = c.agregacao === "fim" ? [ps.at(-1)] : ps;
    out.set(a, c.agregacao === "soma" ? vs.reduce((x, y) => x + y, 0)
      : c.agregacao === "fim" ? ps.at(-1)[3]
      : vs.reduce((x, y) => x + y, 0) / vs.length);
    // margem de erro: média de n períodos → √Σic² / n; soma → √Σic²
    if (usados.every((p) => p[4] != null)) {
      const q = Math.sqrt(usados.reduce((t, p) => t + p[4] ** 2, 0));
      ic.set(a, c.agregacao === "soma" ? q : q / usados.length);
    }
    if (usados.some((p) => p[5] === "p")) prelim.add(a);
  }
  return { v: out, ic, prelim };
}
const ultimo = (ind, uf) => serie(ind, uf).at(-1);
const preliminar = (p) => p && p[5] === "p";
const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
function nomePeriodo(p) {
  let m = /^(\d{4})-T(\d)$/.exec(p);
  if (m) return `${m[2]}º tri ${m[1]}`;
  m = /^(\d{4})-(\d{2})$/.exec(p);
  if (m) return `${MESES[+m[2] - 1]}/${m[1]}`;
  return p;
}
const indicadoresDe = (uf) => Object.keys(D.catalogo).filter((i) => serie(i, uf).length && !(uf === "BR" && SO_ESTADOS.has(i)));
const porArea = (inds) => {
  const m = new Map();
  for (const i of inds) (m.get(cat(i).area) ?? m.set(cat(i).area, []).get(cat(i).area)).push(i);
  const ordem = (a) => { const k = ORDEM_AREAS.indexOf(a); return k < 0 ? 99 : k; };
  return [...m.entries()].sort((a, b) => ordem(a[0]) - ordem(b[0]) || a[0].localeCompare(b[0]))
    .map(([a, is]) => [a, is.sort((x, y) => cat(x).nome.localeCompare(cat(y).nome))]);
};
// "ticks redondos": 1, 2, 2,5, 5 × 10ⁿ
function ticksBonitos(lo, hi, n = 4) {
  const passo0 = (hi - lo) / n || Math.abs(hi) / n || 1, p10 = 10 ** Math.floor(Math.log10(passo0));
  const passo = [1, 2, 2.5, 5, 10].map((k) => k * p10).find((k) => k >= passo0) ?? p10 * 10;
  const out = [];
  for (let v = Math.floor(lo / passo) * passo; v <= hi + passo * 0.999; v += passo) out.push(+v.toPrecision(12));
  return out;
}
// quebra a linha onde falta dado (ex.: PNAD sem 2020–2021)
function caminho(ss, X, Y) {
  let d = "", ant = null;
  for (const p of ss) {
    const salto = !ant || Date.parse(p[1]) - Date.parse(ant[2]) > 3 * 864e5;
    d += `${salto ? "M" : "L"}${X(meio(p)).toFixed(1)},${Y(p[3]).toFixed(1)}`;
    ant = p;
  }
  return d;
}

// ---------------- governos ----------------
// Gestão = a mesma pessoa no mesmo mandato eleitoral, do primeiro ao último dia (afastamentos no
// meio — licença, suspensão judicial — ficam dentro dela e são listados). Quem substituiu
// interinamente durante o mandato do titular ganha uma gestão própria, marcada "absorvida",
// que não entra nas comparações.
let GESTOES = [];
const dias = (a, b) => (Date.parse(b || HOJE) - Date.parse(a)) / 864e5;
function montarGestoes() {
  // chave: titulares juntam os pedaços do mesmo mandato; cada passagem interina é separada,
  // a não ser que emende direto num período efetivo da mesma pessoa (Temer: interino → efetivo)
  const ordenados = [...D.mandatos].sort((a, b) => a.uf.localeCompare(b.uf) || a.inicio.localeCompare(b.inicio));
  const chave = new Map();
  ordenados.forEach((m, i) => {
    const prox = ordenados[i + 1];
    const emenda = prox && prox.uf === m.uf && prox.nome === m.nome && !provisorio(prox.tipo);
    chave.set(m, provisorio(m.tipo) && !emenda ? [m.uf, m.nome, m.inicio].join("|") : [m.uf, m.nome, m.mandato_eleitoral].join("|"));
  });
  const g = new Map();
  for (const m of [...D.mandatos].sort((a, b) => a.inicio.localeCompare(b.inicio))) {
    const k = chave.get(m), x = g.get(k);
    if (!x) { g.set(k, { ...m, pedacos: [m], afastamentos: [] }); continue; }
    x.pedacos.push(m);
    x.fim = !x.fim || !m.fim ? "" : (m.fim > x.fim ? m.fim : x.fim);
    if (!provisorio(m.tipo) && provisorio(x.tipo)) x.tipo = m.tipo;
  }
  GESTOES = [...g.values()];
  for (const x of GESTOES) x.id = `${x.uf}-${x.inicio}`;
  // substitutos dentro do período de outro titular
  for (const t of GESTOES) for (const o of GESTOES) {
    if (o === t || o.uf !== t.uf || t.pedacos.length < 2) continue;
    if (o.inicio > t.inicio && (o.fim || HOJE) < (t.fim || HOJE)) { o.absorvida = true; t.afastamentos.push(o); }
  }
}
const gestaoDoMandato = (m) => GESTOES.find((x) => x.pedacos.includes(m));
const gestaoPorId = (id) => GESTOES.find((g) => g.id === id);
const gestoesDe = (uf) => GESTOES.filter((g) => g.uf === uf).sort((a, b) => a.inicio.localeCompare(b.inicio));
const quemGoverna = (uf, data) => D.mandatos.find((m) => m.uf === uf && m.inicio <= data && (!m.fim || data <= m.fim));
function periodoTxt(g) {
  const a = g.inicio.slice(0, 4), b = g.fim ? g.fim.slice(0, 4) : "hoje";
  return a === b ? a : `${a}–${b}`;
}
const tipoTxt = (g) => ({ vice_assumiu: "vice que assumiu", interino: "interino", interventor: "interventor federal",
  eleito_indireto: "eleito pela Assembleia" })[g.tipo] ?? "";
const provisorio = (t) => t === "interino" || t === "interventor";
const cargo = (g) => g.uf === "BR" ? "Presidência da República" : `Governo ${prep(g.uf)}`;

function anosDaGestao(g) {
  const fim = g.fim || HOJE, anos = [];
  for (let a = +g.inicio.slice(0, 4); a <= +fim.slice(0, 4); a++) {
    const ini = Math.max(Date.parse(`${a}-01-01`), Date.parse(g.inicio));
    const f = Math.min(Date.parse(`${a}-12-31`), Date.parse(fim));
    if (f - ini > 182 * 864e5) anos.push(a);
  }
  return anos;
}
// valor herdado (ano anterior à posse) × último ano completo com dado dentro da gestão
function avaliar(ind, g) {
  if (provisorio(g.tipo) || g.absorvida) return { motivo: g.tipo === "interventor" ? "Intervenção federal: não entra na comparação." : "Governo interino: não entra na comparação." };
  const det = anualDet(ind, g.uf), A = det.v, anos = anosDaGestao(g);
  if (!anos.length) return { motivo: "Governou menos de seis meses em cada ano." };
  const base = anos[0] - 1, comDado = anos.filter((a) => A.has(a));
  const anosSerie = [...A.keys()];
  if (anosSerie.length && Math.min(...anosSerie) > anos.at(-1)) return { motivo: `A série começa em ${Math.min(...anosSerie)}, depois deste governo.` };
  if (anosSerie.length && Math.max(...anosSerie) < anos[0]) return { motivo: `O último dado é de ${Math.max(...anosSerie)}, antes deste governo.` };
  const emCurso = !g.fim;
  const leitura = cat(ind).leitura;
  if (leitura === "media" || leitura === "soma") {
    if (!comDado.length) return { motivo: "Ainda não há ano completo com dado neste governo." };
    const resumo = (M) => { const v = comDado.map((a) => M.get(a)); if (v.some((x) => x == null)) return null;
      const t = v.reduce((x, y) => x + y, 0); return leitura === "soma" ? t : t / v.length; };
    const v = resumo(A), vbr = g.uf !== "BR" ? resumo(anual(ind, "BR")) : null;
    const rel = vbr == null || v == null || extensivo(ind) ? null : sentido(ind, v - vbr);
    return { leitura, base: comDado[0], final: comDado.at(-1), resumo: v, d: v, rel, pUF: v, pBR: vbr,
      parcial: comDado.at(-1) < anos.at(-1), emCurso };
  }
  const primeiro = Math.min(...A.keys());
  const atip = new Set(ATIPICOS[ind] ?? []);
  // base: último ano com dado até 2 anos antes da posse (séries bienais), fora de anos atípicos
  let baseUsada = base;
  const bienal = BIENAIS.has(ind);
  // bienais: até 2 anos antes da posse; anuais: só um ano a mais (posse−2), e só se o governo teve 2+ anos contados
  const recuo = bienal ? 2 : anos.length >= 2 ? 1 : 0;
  while ((!A.has(baseUsada) || atip.has(baseUsada)) && baseUsada > base - recuo) baseUsada--;
  let notaBase = !bienal && baseUsada < base && A.has(baseUsada) ? `ponto de partida: ${baseUsada} (não há dado de ${base})` : "";
  if (!A.has(baseUsada) || atip.has(baseUsada)) {
    // série bienal cuja edição anterior é atípica: usa a edição do 1º ano do governo como ponto de partida
    const ed1 = anos[0];
    if (bienal && A.has(ed1) && !atip.has(ed1) && comDado.some((a) => a > ed1 && !atip.has(a))) { baseUsada = ed1; notaBase = `ponto de partida: edição de ${ed1}, 1º ano do governo (a anterior, ${ed1 - 2}, foi atípica)`; }
    else return { motivo: bienal ? "Sem comparação limpa: a edição anterior à posse é atípica (pandemia) ou não existe." : primeiro > base ? `Os dados reunidos aqui começam em ${primeiro}; falta o ano anterior à posse (${base}).` : `Sem dado de ${base}, o ano anterior à posse.` };
  }
  // fim: último ano da gestão com dado, não atípico, posterior à base e (bienais) não o 1º ano
  const validos = comDado.filter((a) => !atip.has(a) && a > baseUsada && !(bienal && a === anos[0]));
  if (!validos.length) return { motivo: bienal && comDado.length ? "Sem comparação limpa: a única edição do governo é do 1º ano ou atípica (pandemia)."
    : comDado.length ? `O único ano com dado (${comDado.join(", ")}) é atípico (pandemia).` : "Ainda não há ano completo com dado neste governo." };
  const definitivos = validos.filter((a) => !det.prelim.has(a));
  const final = definitivos.length ? definitivos.at(-1) : validos.at(-1);
  const anoPrevia = validos.at(-1) > final ? validos.at(-1) : null;
  const herdado = A.get(baseUsada), atual = A.get(final);
  const k0 = casasPar(ind, herdado, atual);
  // compara o que aparece na tela (arredondado), para que empates não dependam de ruído de ponto flutuante
  const d0 = variacao(ind, arred(herdado, k0), arred(atual, k0)) ?? variacao(ind, herdado, atual);
  const d = d0 == null ? null : +d0.toFixed(k0 + 3);
  const icDe = (D_, a, b, ref) => {
    if (!D_.ic.has(a) || !D_.ic.has(b)) return null;
    if (modoVar(ind) === "pct") return Math.hypot(D_.ic.get(a) / Math.abs(D_.v.get(a)), D_.ic.get(b) / Math.abs(D_.v.get(b))) * 100;
    return Math.hypot(D_.ic.get(a), D_.ic.get(b));
  };
  const icD = icDe(det, baseUsada, final, herdado);
  const dentroDaMargem = icD != null && Math.abs(d) < icD;
  // mudança brusca de um ano para outro em taxas: provável mudança de registro → sem veredito
  let verificar = false;
  if (VERIFICAR_SALTOS.has(ind)) {
    for (let a = baseUsada + 1; a <= final; a++) {
      const x = A.get(a - 1), y = A.get(a);
      if (x != null && y != null && x > 1 && y > 0 && Math.abs(y / x - 1) > 0.6 && !atip.has(a) && !atip.has(a - 1)) verificar = true;
    }
  }
  const acima100 = ind === "cobertura_triplice_viral" && (herdado > 100 || atual > 100);
  const semVeredito = SEM_VEREDITO[ind]
    || (acima100 ? "Cobertura acima de 100% indica erro de denominador ou campanha; a comparação não é confiável." : "")
    || (verificar ? "Há uma variação brusca de um ano para outro, provavelmente mudança no registro; confira antes de usar." : "");
  let dBR = null, pUF = null, pBR = null, rel = null, banda = null, vBR = null, modo = null, motivoBR = "";
  if (g.uf !== "BR" && !semVeredito) {
    const BD = anualDet(ind, "BR"), B = BD.v, hb = B.get(baseUsada), ab = B.get(final);
    const absoluto = extensivo(ind) && modoVar(ind) !== "pct";
    const pequeno = extensivo(ind) && hb && Math.abs(herdado) < 0.01 * Math.abs(hb);
    if (hb != null && ab != null && !absoluto && !pequeno && sentido(ind, 1) != null) {
      dBR = variacao(ind, arred(hb, k0), arred(ab, k0)); if (dBR != null) dBR = +dBR.toFixed(k0 + 3);
      const icBR = icDe(BD, baseUsada, final, hb);
      const pa = problema(ind, herdado), pb = problema(ind, atual), qa = problema(ind, hb), qb = problema(ind, ab);
      modo = MODO_BR[ind] ?? ([pa, pb, qa, qb].every((x) => x != null) ? "lacuna" : "relativo");
      if (modo === "lacuna" && [pa, qa].some((x) => x === 0)) modo = "pp";
      const resol = 0.5 * 10 ** -k0 * Math.SQRT2;
      if (modo === "pp") {
        modo = "pp"; pUF = sentido(ind, d); pBR = sentido(ind, dBR); rel = pUF - pBR;
        banda = Math.max(limiar(ind), Math.hypot(icD ?? 0, icBR ?? 0), 2 * resol);
      } else if (modo === "lacuna") {
        pUF = (pa - pb) / pa * 100; pBR = (qa - qb) / qa * 100; rel = pUF - pBR;
        const icRel = Math.hypot((icD ?? 0) / pa, (icBR ?? 0) / qa) * 100;
        banda = Math.max(3, icRel, 100 * 2 * resol / pa);
        // se a régua de pontos discorda da régua de lacuna, não há veredito claro
        const ppRel = sentido(ind, d - dBR);
        if (Math.abs(ppRel) >= limiar(ind) && Math.sign(ppRel) !== Math.sign(rel) && Math.abs(rel) >= banda) { rel = 0; motivoBR = "depende da régua: em pontos e em proporção do problema o resultado se inverte"; }
      } else {
        // relativo: variação % de cada um (não vale quando o valor troca de sinal)
        if (herdado * atual <= 0 || hb * ab <= 0) { rel = null; }
        else {
          pUF = sentido(ind, (atual / herdado - 1) * 100); pBR = sentido(ind, (ab / hb - 1) * 100); rel = pUF - pBR;
          const icRel = Math.hypot((icD ?? 0) / (modoVar(ind) === "pct" ? 100 : Math.abs(herdado)), (icBR ?? 0) / (modoVar(ind) === "pct" ? 100 : Math.abs(hb))) * 100;
          banda = Math.max(3, icRel, 100 * 2 * resol / Math.abs(herdado));
        }
      }
      if (rel != null) {
        vBR = Math.abs(+rel.toFixed(6)) < banda ? "igual" : rel > 0 ? "melhor" : "pior";
        // estado perto do teto: oscilou dentro da margem e segue em nível melhor que o Brasil
        if (vBR === "pior" && dentroDaMargem && sentido(ind, atual - ab) > 0) { vBR = "igual"; motivoBR = "o estado oscilou dentro da margem de erro e segue acima do nível do Brasil"; }
      }
    }
  }
  // A4: homicídios — a conclusão se mantém somando as mortes de intenção indeterminada?
  if (ind === "homicidios" && d != null && D.catalogo.obitos_intencao_indeterminada) {
    const soma = (uf_, a) => { const h = anual("homicidios", uf_).get(a), i = anual("obitos_intencao_indeterminada", uf_).get(a); return h == null || i == null ? null : h + i; };
    const cA = soma(g.uf, baseUsada), cB = soma(g.uf, final);
    if (cA != null && cB != null) {
      const dc = (cB / cA - 1) * 100;
      const lim = limiar(ind);
      const mudaSentido = Math.abs(d) >= lim && ((Math.sign(dc) !== Math.sign(d) && Math.abs(dc) >= 2) || Math.abs(dc) < lim);
      let mudaBR = false;
      if (vBR && vBR !== "igual") {
        const bA = soma("BR", baseUsada), bB = soma("BR", final);
        if (bA != null && bB != null) { const relC = -(dc - (bB / bA - 1) * 100); mudaBR = Math.sign(relC) !== Math.sign(rel) || Math.abs(relC) < 3; }
      }
      if (mudaSentido) { vBR = vBR ? "igual" : vBR; motivoBR = "somando as mortes de intenção indeterminada, a tendência se inverte ou desaparece"; }
      else if (mudaBR) { vBR = "igual"; motivoBR = "somando as mortes de intenção indeterminada, a diferença para o Brasil desaparece"; }
      if (mudaSentido) return { base: baseUsada, final, herdado, atual, d, dBR, pUF, pBR, rel, banda, vBR, modo, motivoBR, icD, dentroDaMargem,
        semVeredito: "Somando as mortes de intenção indeterminada (possíveis homicídios não classificados), a tendência se inverte ou desaparece.",
        prelim: det.prelim.has(final), anoPrevia, valorPrevia: anoPrevia ? A.get(anoPrevia) : null, parcial: final < anos.at(-1), emCurso, anos, notaBase };
    }
  }
  return { base: baseUsada, final, herdado, atual, d, dBR, pUF, pBR, rel, banda, vBR, modo, motivoBR, icD, dentroDaMargem, semVeredito, ressalva: ressalvaDe(ind, g.uf, baseUsada, final, d), notaBase,
    prelim: det.prelim.has(final), anoPrevia, valorPrevia: anoPrevia ? A.get(anoPrevia) : null,
    parcial: final < anos.at(-1), emCurso, anos };
}
// Exibe dois valores na mesma escala ("de 22,6 para 21,0 milhões de famílias") e devolve também os números
// exatamente como aparecem, para o selo ser calculado a partir deles.
function escalaPar(ind, a, b) {
  const u = cat(ind).unidade, mx = Math.max(Math.abs(a), Math.abs(b));
  const nomes = { habitantes: "habitantes", empregos: "vagas", "famílias": "famílias" };
  let m = /^(US\$|R\$) milhões(.*)$/.exec(u);
  if (m) { const v = mx * 1e6, extra = m[2] ? " (" + m[2].trim().replace(/^de /, "valores de ") + ")" : "";
    return v >= 1e9 ? { div: 1e3, pre: m[1] + " ", suf: " bi" + extra } : { div: 1, pre: m[1] + " ", suf: " milhões" + extra }; }
  if (u === "US$ bi") return { div: 1, pre: "US$ ", suf: " bi" };
  if (nomes[u] && mx >= 1e6) return { div: 1e6, pre: "", suf: ` ${mx < 2e6 ? "milhão" : "milhões"} de ${nomes[u]}` };
  if (nomes[u] && mx >= 1e4) return { div: 1e3, pre: "", suf: ` mil ${nomes[u]}` };
  if (u.startsWith("% ")) return { div: 1, pre: "", suf: "% " + sufixoPct(ind), pct: true };
  if (u.startsWith("%")) return { div: 1, pre: "", suf: "%", pct: true };
  if (u.startsWith("R$")) return { div: 1, pre: "R$ ", suf: "" };
  const uc = unidadeCurta(ind);
  return { div: 1, pre: "", suf: uc ? " " + uc : "" };
}
function variacaoExibida(ind, va, vb) { return modoVar(ind) === "pct" ? (va === 0 ? null : (vb / va - 1) * 100 * (va < 0 ? -1 : 1)) : vb - va; }
function exibirPar(ind, a, b) {
  const e = escalaPar(ind, a, b), x = a / e.div, y = b / e.div;
  const kVar = modoVar(ind) === "pct" ? 1 : modoVar(ind) === "pp" ? 1 : casas(ind);
  let k = e.div > 1 ? 1 : casas(ind);
  const dinheiro = e.pre.startsWith("R$") && e.div === 1;
  // dinheiro sem centavos (a não ser em valores abaixo de R$ 10); demais, no máximo uma casa a mais
  const kMax = dinheiro ? (Math.max(Math.abs(x), Math.abs(y)) < 10 ? 2 : 0) : Math.min(3, k + 1);
  if (dinheiro && kMax === 2) k = 2;   // centavos: "R$ 0,30 para R$ 0,00"
  // mais casas até: (1) os dois números ficarem diferentes e (2) a variação calculada com eles coincidir com a verdadeira no que o selo mostra
  const verdade = variacaoExibida(ind, x, y);
  while (k < kMax) {
    const xa = +x.toFixed(k), ya = +y.toFixed(k);
    const vis = variacaoExibida(ind, xa, ya);
    const ok = (x === y || fmtN(xa, k) !== fmtN(ya, k)) && vis != null && verdade != null && fmtN(Math.abs(vis), kVar) === fmtN(Math.abs(verdade), kVar);
    if (ok) break;
    k++;
  }
  const xa = +x.toFixed(k), ya = +y.toFixed(k);
  const dVis = variacaoExibida(ind, xa, ya);
  // "de 12,8% para 7,9%", "de 71,7% para 78,6% do PIB", "de R$ 2.394 para R$ 2.862", "de US$ 61,5 para 68,1 bi"
  let de = e.pre + fmtN(xa, k), para = fmtN(ya, k), fim = e.suf;
  if (e.pct) { de += "%"; para += "%"; fim = e.suf.slice(1); }
  else if (!e.suf) para = e.pre + para;
  // variação absoluta escrita na mesma escala e com as mesmas casas da frase ("US$ 0,4 bi")
  const dTxt = modoVar(ind) === "abs" && e.div > 1 && dVis != null ? `${e.pre}${fmtN(Math.abs(ya - xa), k)}${e.suf}` : null;
  return { de, para, fim, k, dTxt,
    // a variação em pontos/absoluta precisa voltar à unidade original para o selo
    dVis: dVis == null ? null : modoVar(ind) === "pct" ? dVis : dVis * e.div };
}

// a frase que responde "o que aconteceu com X neste governo?"
function frase(ind, r) {
  if (r.motivo) return esc(r.motivo);
  const anos = r.base === r.final ? `${r.final}` : `${r.base}–${r.final}`;
  if (r.leitura === "media" && cat(ind).unidade.includes("variação"))
    return r.base === r.final ? `${r.resumo >= 0 ? "Cresceu" : "Encolheu"} <b>${esc(fmtN(Math.abs(r.resumo), 1))}%</b> em ${anos}`
      : `${r.resumo >= 0 ? "Cresceu" : "Encolheu"} em média <b>${esc(fmtN(Math.abs(r.resumo), 1))}%</b> ao ano (${anos})`;
  if (r.leitura === "media") return `Média de <b>${esc(fmtU(ind, r.resumo))}</b> por ano em ${anos}`;
  if (r.leitura === "soma") return cat(ind).unidade === "empregos"
    ? `${r.resumo >= 0 ? "Saldo de" : "Perda líquida de"} <b>${esc(fmtU(ind, Math.abs(r.resumo)))}</b> com carteira em ${anos}`
    : `Somou <b>${esc(fmtU(ind, r.resumo))}</b> em ${anos}`;
  const ex = exibirPar(ind, r.herdado, r.atual);
  const de = ex.de, para = ex.para, fim = ex.fim;
  const neutro = sentido(ind, 1) == null || !!r.semVeredito;
  const estavel = !neutro && (r.dentroDaMargem || Math.abs(ex.dVis ?? r.d) < limiar(ind));
  let txt = neutro ? `Passou de <b>${esc(de)}</b> para <b>${esc(para)}</b>${esc(fim)}`
    : estavel ? `Ficou estável: <b>${esc(de)}</b> → <b>${esc(para)}</b>${esc(fim)}`
    : `${(ex.dVis ?? r.d) < 0 ? "Caiu" : "Subiu"} de <b>${esc(de)}</b> para <b>${esc(para)}</b>${esc(fim)}`;
  const c = cat(ind);
  if (c.limite != null && r.atual > c.limite) txt += ` — <span class="alerta">acima do limite legal de ${esc(fmtN(c.limite, 0))}%</span>`;
  if (c.meta != null && r.atual < c.meta) txt += ` — <span class="alerta">abaixo do mínimo legal de ${esc(fmtN(c.meta, 0))}%</span>`;
  return txt;
}
function nota(r) {
  if (r.motivo) return "";
  const extra = [r.notaBase ?? "", r.anoPrevia ? `${r.anoPrevia > r.final + 1 ? `${r.final + 1}–${r.anoPrevia}` : r.anoPrevia} (preliminar) ainda não entra` : "", r.semVeredito ? "sem veredito: " + r.semVeredito : "", r.ressalva ? "atenção: " + r.ressalva : ""].filter(Boolean).join(" · ");
  const fim = r.emCurso ? "governo em andamento" : r.parcial ? "o dado ainda não cobre o fim do governo" : "";
  return [r.leitura ? "" : `${r.base} → ${r.final}`, r.prelim ? `${r.final} é preliminar (fora da contagem)` : "", extra, fim].filter(Boolean).join(" · ");
}

// ---------------- dica (tooltip) ----------------
const dica = $("#dica");
function mostrarDica(ev, html) {
  dica.innerHTML = html; dica.hidden = false;
  const r = dica.getBoundingClientRect();
  const cx = ev.clientX, cy = ev.clientY;
  let x = cx + 14, y = cy + 16;
  if (x + r.width > innerWidth - 8) x = cx - r.width - 14;
  if (y + r.height > innerHeight - 8) y = cy - r.height - 14;
  dica.style.left = Math.max(8, x) + "px"; dica.style.top = Math.max(8, y) + "px";
}
const esconderDica = () => { dica.hidden = true; };

// ---------------- gráfico de linha ----------------
// g: governo grifado (marca-texto); faixas: todos os governos ao fundo, com sobrenome
// fluxos mensais (saldo de empregos): o gráfico mostra a soma dos últimos 12 meses
const movel12 = (ind) => cat(ind).freq === "mensal" && cat(ind).agregacao === "soma";
function serieGrafico(ind, uf) {
  const sr = serie(ind, uf);
  if (!movel12(ind)) return sr;
  const out = [];
  for (let i = 11; i < sr.length; i++) out.push([sr[i][0], sr[i][1], sr[i][2], sr.slice(i - 11, i + 1).reduce((t, p) => t + p[3], 0)]);
  return out;
}
function grafico(ind, uf, o = {}) {
  const { w = 300, h = 70, g = null, br = false, todasUF = false, eixos = false, interativo = false, faixas = false } = o;
  const sr = serieGrafico(ind, uf);
  if (!sr.length) return s("svg", { viewBox: `0 0 ${w} ${h}` });
  const sbr = br && uf !== "BR" && !extensivo(ind) ? serieGrafico(ind, "BR") : [];
  const outras = todasUF && !extensivo(ind) ? ORDEM_UF.filter((u) => u !== uf).map((u) => serieGrafico(ind, u)).filter((x) => x.length) : [];
  // eixo começa em 2012, ou no início da série se ela for bem mais curta (ex.: Novo CAGED, 2020)
  const t0 = Date.parse(sr[0][1]) > Date.parse("2015-01-01") ? Date.parse(sr[0][1].slice(0, 4) + "-01-01") : Math.min(Date.parse("2012-01-01"), Date.parse(sr[0][1]));
  const t1 = Date.parse(HOJE);
  const e = eixos ? 54 : 2, d = 8, topo = faixas ? 24 : 6, base = eixos ? 24 : 4;
  const X = (iso) => e + (Date.parse(iso) - t0) / (t1 - t0) * (w - e - d);
  const ref = cat(ind).meta ?? cat(ind).limite;
  let vs = sr.map((p) => p[3]).concat(sbr.map((p) => p[3]), (o.marcas ?? []).map((m) => m[1]), ref != null ? [ref] : []);
  for (const x of outras) vs = vs.concat(x.map((p) => p[3]));
  let lo = Math.min(...vs), hi = Math.max(...vs);
  let tks = [];
  if (eixos) { tks = ticksBonitos(lo, hi); lo = tks[0]; hi = tks.at(-1); }
  else { const folga = (hi - lo) * 0.08 || Math.abs(hi) * 0.05 || 1; lo -= folga; hi += folga; }
  const Y = (v) => topo + (hi - v) / (hi - lo || 1) * (h - topo - base);
  const svg = s("svg", { viewBox: `0 0 ${w} ${h}`, width: o.px ? w : null, height: o.px ? h : null, role: "img", "aria-label": `${cat(ind).nome}, ${D.ufs[uf]}` });
  if (faixas) {
    let livreDesde = 0;
    gestoesDe(uf).filter((x) => !x.absorvida && (x.fim || HOJE) >= new Date(t0).toISOString().slice(0, 10)).forEach((x, i) => {
      const a = Math.max(e, X(x.inicio)), z = X(x.fim || HOJE);
      if (z - a < 1) return;
      if (i % 2) svg.append(s("rect", { x: a, y: topo, width: z - a, height: h - topo - base, class: "faixa" }));
      if (a > e + 1) svg.append(s("line", { x1: a, x2: a, y1: 4, y2: h - base, class: "divisa" }));
      const rot = nomeCurto(x.nome), largRot = rot.length * 6.2 + 8;
      if (z - a > largRot && a >= livreDesde) { svg.append(s("text", { x: a + 4, y: 15, class: "rot-gov", text: rot })); livreDesde = a + largRot; }
    });
  }
  if (g && X(g.fim || HOJE) > e + 2) {
    const a = Math.max(e, X(g.inicio < INICIO_REGUA ? INICIO_REGUA : g.inicio)), z = X(g.fim || HOJE);
    svg.append(s("rect", { x: a, y: faixas ? topo : 0, width: Math.max(2, z - a), height: h - base - (faixas ? topo : 0) + 2, class: "grifo" }));
  }
  if (eixos) {
    for (const v of tks) {
      svg.append(s("line", { x1: e, x2: w - d, y1: Y(v), y2: Y(v), class: "eixo" }));
      const av = Math.abs(v);
      const rot = av >= 1e6 && casas(ind) === 0 ? fmtN(v / 1e6, av % 1e6 ? 1 : 0) + " mi" : av >= 1e4 && casas(ind) === 0 ? fmtN(v / 1e3, 0) + " mil" : fmt(ind, v).replace("R$ ", "");
      svg.append(s("text", { x: e - 6, y: Y(v) + 4, "text-anchor": "end", text: rot }));
    }
    const passo = w < 560 ? 4 : w < 900 ? 2 : 1;
    for (let a = new Date(t0).getUTCFullYear(); a <= +HOJE.slice(0, 4); a++) {
      svg.append(s("line", { x1: X(`${a}-01-01`), x2: X(`${a}-01-01`), y1: h - base, y2: h - base + 4, class: "tique" }));
      if ((a - new Date(t0).getUTCFullYear()) % passo === 0) svg.append(s("text", { x: X(`${a}-07-01`), y: h - 6, "text-anchor": "middle", text: passo === 1 ? "’" + String(a).slice(2) : a }));
    }
  }
  if (lo < 0 && hi > 0) svg.append(s("line", { x1: e, x2: w - d, y1: Y(0), y2: Y(0), class: "linha-zero" }));
  if (ref != null) {
    svg.append(s("line", { x1: e, x2: w - d, y1: Y(ref), y2: Y(ref), class: "linha-ref" }));
    if (eixos || w > 250) svg.append(s("text", { x: w - d, y: Y(ref) - 4, "text-anchor": "end", class: "rot-ref",
      text: `${cat(ind).meta != null ? "mínimo legal" : "limite legal"} ${fmt(ind, ref)}` }));
  }
  for (const x of outras) svg.append(s("path", { d: caminho(x, X, Y), class: "linha-uf" }));
  if (sbr.length) svg.append(s("path", { d: caminho(sbr, X, Y), class: "linha-br" }));
  svg.append(s("path", { d: caminho(sr, X, Y), class: "linha-serie" }));
  const u = sr.at(-1);
  if (o.marcas) {
    const [[a0, v0], [a1, v1]] = o.marcas;
    svg.append(s("circle", { cx: X(`${a0}-07-01`), cy: Y(v0), r: 3.5, class: "ponto-ini" }));
    svg.append(s("circle", { cx: X(`${a1}-07-01`), cy: Y(v1), r: 3.5, class: "ponto-marca" }));
  } else svg.append(s("circle", { cx: X(meio(u)), cy: Y(u[3]), r: eixos ? 4.5 : 3, class: "ponto-fim" }));
  if (interativo) {
    const cursor = s("line", { y1: topo, y2: h - base, class: "cursor", visibility: "hidden" });
    const marca = s("circle", { r: 5, class: "ponto-cursor", visibility: "hidden" });
    const alvo = s("rect", { x: e, y: 0, width: w - e - d, height: h, fill: "transparent" });
    const vbr = new Map(serie(ind, "BR").map((p) => [p[0], p[3]]));
    let idx = sr.length - 1;
    const mostrar = (i, ev) => {
      idx = Math.max(0, Math.min(sr.length - 1, i));
      const p = sr[idx], x = X(meio(p));
      cursor.setAttribute("x1", x); cursor.setAttribute("x2", x); cursor.setAttribute("visibility", "visible");
      marca.setAttribute("cx", x); marca.setAttribute("cy", Y(p[3])); marca.setAttribute("visibility", "visible");
      const gov = quemGoverna(uf, meio(p));
      const html = `<span class="s">${esc(nomePeriodo(p[0]))} · ${esc(nomeUF(ind, uf))}${movel12(ind) ? " · soma de 12 meses" : ""}</span><br><b>${esc(fmtU(ind, p[3]))}</b>
        ${uf !== "BR" && !extensivo(ind) ? `<br><span class="s">Brasil: ${esc(fmtU(ind, vbr.get(p[0])))}</span>` : ""}
        ${gov ? `<br><span class="s">${esc(gov.nome)} (${esc(gov.partido)})</span>` : ""}`;
      if (ev) mostrarDica(ev, html);
      else { const r = svg.getBoundingClientRect(); mostrarDica({ clientX: r.left + x * r.width / w, clientY: r.top + Y(p[3]) * r.height / h }, html); }
    };
    const perto = (ev) => {
      const r = svg.getBoundingClientRect(), xs = (ev.clientX - r.left) * (w / r.width);
      let best = 0;
      sr.forEach((q, i) => { if (Math.abs(X(meio(q)) - xs) < Math.abs(X(meio(sr[best])) - xs)) best = i; });
      return best;
    };
    alvo.addEventListener("pointermove", (ev) => mostrar(perto(ev), ev));
    alvo.addEventListener("pointerdown", (ev) => mostrar(perto(ev), ev));
    const sair = () => { cursor.setAttribute("visibility", "hidden"); marca.setAttribute("visibility", "hidden"); esconderDica(); };
    alvo.addEventListener("pointerleave", sair);
    svg.setAttribute("tabindex", "0");
    svg.setAttribute("aria-label", `${cat(ind).nome}, ${D.ufs[uf]}. Use as setas para percorrer os períodos.`);
    svg.addEventListener("keydown", (ev) => {
      if (ev.key === "ArrowLeft" || ev.key === "ArrowRight") { ev.preventDefault(); mostrar(idx + (ev.key === "ArrowRight" ? 1 : -1)); }
      if (ev.key === "Home") mostrar(0);
      if (ev.key === "End") mostrar(sr.length - 1);
    });
    svg.addEventListener("focus", () => mostrar(idx));
    svg.addEventListener("blur", sair);
    svg.append(cursor, marca, alvo);
  }
  return svg;
}

// ---------------- régua de governos ----------------
function regua(uf, selecionado, aoEscolher) {
  const gs = gestoesDe(uf).filter((g) => !g.absorvida && (g.fim || HOJE) >= INICIO_REGUA);
  const pecas = D.mandatos.filter((m) => m.uf === uf && (m.fim || HOJE) >= INICIO_REGUA).sort((a, b) => a.inicio.localeCompare(b.inicio));
  const t0 = Date.parse(INICIO_REGUA), t1 = Date.parse(HOJE);
  const pc = (iso) => Math.max(0, (Date.parse(iso) - t0) / (t1 - t0) * 100);
  const wrap = document.createElement("div");
  const titulo = (g) => `${g.nome} (${g.partido}), ${dataBR(g.inicio)} a ${g.fim ? dataBR(g.fim) : "hoje"}${tipoTxt(g) ? ", " + tipoTxt(g) : ""}${g.afastamentos.length ? `, afastado por ${g.afastamentos.map((a) => `${Math.round(dias(a.inicio, a.fim))} dias (${a.nome} assumiu)`).join(", ")}` : ""}`;
  // foco: só o primeiro pedaço de cada gestão entra na ordem de tabulação
  if (ESTREITO()) {
    wrap.className = "regua-lista";
    wrap.setAttribute("role", "group"); wrap.setAttribute("aria-label", "Escolha um governo");
    for (const g of [...gs].reverse()) {
      const b = document.createElement("button");
      b.type = "button"; b.className = "chip-gov"; b.setAttribute("aria-pressed", g.id === selecionado); b.setAttribute("aria-label", titulo(g));
      b.innerHTML = `<span class="n">${esc(g.nome)}</span><span class="p">${esc(g.partido)} · ${periodoTxt(g)}${tipoTxt(g) ? " · " + tipoTxt(g) : ""}</span>`;
      b.addEventListener("click", () => aoEscolher(g.id));
      wrap.append(b);
    }
    requestAnimationFrame(() => { const sel = wrap.querySelector('[aria-pressed="true"]'); if (sel) wrap.scrollLeft = sel.offsetLeft - 16; });
    return wrap;
  }
  wrap.className = "regua";
  const trilho = document.createElement("div");
  trilho.className = "regua-trilho";
  trilho.setAttribute("role", "group"); trilho.setAttribute("aria-label", "Escolha um governo");
  for (const m of pecas) {
    const g = gestaoDoMandato(m);
    const a = pc(m.inicio < INICIO_REGUA ? INICIO_REGUA : m.inicio), z = pc(m.fim || HOJE);
    const b = document.createElement("button");
    const larg = (z - a) / 100 * Math.min(innerWidth, 1400);
    b.type = "button";
    b.className = "regua-gov" + (larg < 34 ? " fino" : larg < 110 ? " curto" : "") + (provisorio(m.tipo) || g.absorvida ? " interino" : "");
    b.style.left = a + "%"; b.style.width = (z - a) + "%";
    b.setAttribute("aria-pressed", g.id === selecionado);
    b.setAttribute("aria-label", titulo(g));
    b.dataset.g = g.id;
    const per = m.fim ? periodoTxt(m) : "desde " + m.inicio.slice(0, 4);
    const nomeCabe = m.nome.length * 8.2 + 16 < larg;
    b.innerHTML = larg < 34 ? "" : larg < 110 ? `<span class="n">${esc(nomeCurto(m.nome))}</span><span class="p">${m.fim ? periodoTxt(m) : "desde " + m.inicio.slice(0, 4)}</span>`
      : `<span class="n">${esc(nomeCabe ? m.nome : nomeCurto(m.nome))}</span><span class="p">${esc(m.partido)} · ${per}</span>`;
    b.addEventListener("pointerenter", (ev) => mostrarDica(ev, `<b>${esc(m.nome)}</b><br><span class="s">${esc(m.partido)} · ${dataBR(m.inicio)} a ${m.fim ? dataBR(m.fim) : "hoje"}${tipoTxt(m) ? "<br>" + tipoTxt(m) : ""}${g.absorvida ? "<br>substituiu o titular; não entra nas comparações" : g.afastamentos.length ? "<br>mandato com afastamento no meio" : ""}</span>`));
    b.addEventListener("pointerleave", esconderDica);
    b.addEventListener("focus", () => { const r = b.getBoundingClientRect(); b.dispatchEvent(new PointerEvent("pointerenter", { clientX: r.left + 8, clientY: r.bottom })); });
    b.addEventListener("blur", esconderDica);
    b.addEventListener("click", () => aoEscolher(g.id));
    trilho.append(b);
  }
  const anos = document.createElement("div");
  anos.className = "regua-anos";
  anos.setAttribute("aria-hidden", "true");
  for (let a = 2011; a <= +HOJE.slice(0, 4); a++) {
    const sp = document.createElement("span");
    sp.style.left = pc(`${a}-01-01`) + "%";
    sp.textContent = innerWidth > 1000 || a % 2 ? a : "";
    anos.append(sp);
  }
  // acessibilidade: só o primeiro pedaço visível de cada gestão é focável; setas navegam
  const vistos = new Set();
  const focaveis = [];
  for (const b of trilho.querySelectorAll(".regua-gov")) {
    const id = b.dataset.g;
    if (vistos.has(id) || b.classList.contains("fino")) { b.tabIndex = -1; b.setAttribute("aria-hidden", "true"); continue; }
    vistos.add(id); focaveis.push(b);
    b.tabIndex = b.getAttribute("aria-pressed") === "true" ? 0 : -1;
  }
  if (!focaveis.some((b) => b.tabIndex === 0) && focaveis.length) focaveis.at(-1).tabIndex = 0;
  trilho.addEventListener("keydown", (ev) => {
    const i = focaveis.indexOf(document.activeElement);
    if (i < 0 || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(ev.key)) return;
    ev.preventDefault();
    const j = ev.key === "Home" ? 0 : ev.key === "End" ? focaveis.length - 1 : Math.max(0, Math.min(focaveis.length - 1, i + (ev.key === "ArrowRight" ? 1 : -1)));
    focaveis[i].tabIndex = -1; focaveis[j].tabIndex = 0; focaveis[j].focus();
  });
  const leg = document.createElement("p");
  leg.className = "regua-leg";
  if (trilho.querySelector(".interino")) leg.innerHTML = `<i></i> interino, interventor ou afastamento — não é avaliado`;
  wrap.append(trilho, anos, leg);
  return wrap;
}

// ---------------- página: governos ----------------
const avaliacaoBase = (uf, r) => uf === "BR" ? r.d : r.rel;
// classifica um resultado: no Brasil, pela variação; nos estados, pelo progresso relativo ao Brasil
function veredito(ind, uf, r) {
  if (r.d == null || sentido(ind, 1) == null || r.prelim || r.semVeredito) return null;
  if (uf === "BR") { if (r.leitura) return null; const c = classe(ind, r.d, Math.max(limiar(ind), r.icD ?? 0)); return c === "igual-neutra" ? null : c; }
  if (r.leitura) return null;   // fluxos (crescimento, saldo de empregos): sem veredito, como diz o método
  return r.vBR;
}
function pagGovernos(params) {
  const uf = params.get("uf") && (params.get("uf") === "BR" || BLOCOS[params.get("uf")]) ? params.get("uf") : "BR";
  const gs = gestoesDe(uf).filter((x) => !x.absorvida);
  const inds = indicadoresDe(uf);
  let g = gestaoPorId(params.get("g"));
  if (!g || g.uf !== uf) {
    // padrão: o governo mais recente com pelo menos 5 indicadores comparáveis
    g = [...gs].reverse().find((x) => inds.filter((i) => avaliar(i, x).d != null).length >= 5) ?? gs.at(-1);
  }
  contexto.uf = uf; contexto.g = g.id;
  const ir = (nuf, gid) => { focarRegua = true; location.hash = `#/?uf=${nuf}${gid ? "&g=" + encodeURIComponent(gid) : ""}`; };
  const filtro = params.get("f") ?? "todos";

  const main = $("#conteudo");
  main.innerHTML = `
    <section class="abertura">
      <p class="sobretitulo">${inds.length} de ${Object.keys(D.catalogo).length} indicadores com dado ${uf === "BR" ? "nacional" : "para " + esc(D.ufs[uf])} · governos desde 2011</p>
      <h1>Quem governava, e o que <span class="grifado">mudou</span>.</h1>
      <p class="lead">Escolha um governo na régua. O período dele fica grifado em todos os números, com o valor que
        encontrou ao assumir, o último disponível e, nos estados, a comparação com o Brasil no mesmo intervalo.</p>
      <div class="escopo"><label for="escopo">Ver governos</label>
        <select id="escopo">${["BR", ...ORDEM_UF.slice().sort((a, b) => D.ufs[a].localeCompare(D.ufs[b]))]
          .map((u) => `<option value="${u}" ${u === uf ? "selected" : ""}>${u === "BR" ? "da Presidência da República" : esc(prep(u))}</option>`).join("")}</select></div>
    </section>`;
  main.append(regua(uf, g.id, (id) => ir(uf, id)));
  if (focarRegua) { focarRegua = false; main.querySelector('[aria-pressed="true"]')?.focus({ preventScroll: true }); }
  $("#escopo").onchange = (ev) => ir(ev.target.value);

  const res = new Map(inds.map((ind) => [ind, avaliar(ind, g)]));
  const conta = { melhor: 0, pior: 0, igual: 0 };
  for (const [ind, r] of res) { const c = veredito(ind, uf, r); if (c in conta) conta[c]++; }
  const comparaveis = conta.melhor + conta.pior + conta.igual;
  const sel = document.createElement("section");
  sel.className = "selecionado";
  const rotulos = uf === "BR" ? ["melhoraram", "pioraram", "estáveis"] : ["melhor que o Brasil", "pior que o Brasil", "igual ao Brasil"];
  const base = `#/?uf=${uf}&g=${encodeURIComponent(g.id)}`;
  const botao = (f, n, rot, cls) => `<a class="placar-item ${cls}" href="${base}&f=${f}" ${filtro === f ? 'aria-current="true"' : ""}><b>${n}</b>${rot}</a>`;
  sel.innerHTML = `<div><h2>${esc(g.nome)}</h2>
      <div class="meta">${esc(g.partido)} · ${cargo(g)} · ${dataBR(g.inicio)} a ${g.fim ? dataBR(g.fim) : "hoje"}${tipoTxt(g) ? " · " + tipoTxt(g) : ""}${g.afastamentos.length ? ` · afastado por ${g.afastamentos.map((a) => Math.round(dias(a.inicio, a.fim)) + " dias").join(", ")}` : ""}</div></div>
    ${comparaveis ? `<nav class="placar" aria-label="Filtrar indicadores">
      ${botao("melhor", conta.melhor, rotulos[0], "m")}${botao("pior", conta.pior, rotulos[1], "p")}${botao("igual", conta.igual, rotulos[2], "i")}
      ${filtro !== "todos" ? `<a class="placar-item limpar" href="${base}">mostrar todos</a>` : ""}</nav>` : ""}
    ${comparaveis ? `<p class="placar-nota">${comparaveis} de ${inds.length} indicadores entram na contagem; os demais descrevem sem julgar (gasto por área, população, comércio), têm dado preliminar ou não têm base.</p>` : ""}`;
  main.append(sel);

  if (!comparaveis) {
    main.insertAdjacentHTML("beforeend", `<p class="aviso"><b>Sem base de comparação para este governo.</b> ${provisorio(g.tipo) ? "Governos interinos e intervenções não entram na comparação." :
      "As séries reunidas aqui começam em 2012 (algumas depois), então falta o ano anterior à posse, ou o governo durou pouco."} Os gráficos abaixo ainda mostram o período grifado.</p>`);
  } else {
    main.insertAdjacentHTML("beforeend", `<div class="como-ler"><p><b>Como ler.</b> Cada cartão compara o ano anterior à posse com o último ano completo do governo (dados preliminares e anos de pandemia não servem de ponta).
      ${uf === "BR" ? "Atenção: alguns indicadores (internet, escolaridade, esgoto) melhoram há décadas em quase todo governo; a contagem não desconta essa tendência."
      : "“Melhor que o Brasil” quer dizer que o estado avançou mais que o país no mesmo intervalo: em taxas, pela parte do problema que cada um reduziu (por exemplo: um estado que cortou 36% da pobreza que tinha, contra 27% no Brasil, foi melhor); em ocupação e emprego, pelos pontos ganhos. Se as duas réguas discordam, ou se a diferença cabe na margem de erro da pesquisa, vale “igual ao Brasil”."}
      A contagem não pesa os indicadores nem prova causa: saúde, educação e segurança dependem de União, estados e municípios, e o primeiro ano roda com o orçamento do antecessor.
      <a href="#/metodo">Como a régua funciona</a>.</p>
      <p class="chave-mini"><span><i class="l"></i>${uf === "BR" ? "Brasil" : esc(D.ufs[uf])}</span>${uf !== "BR" ? '<span><i class="b"></i>Brasil</span>' : ""}<span><i class="g"></i>período do governo</span></p></div>`);
  }
  if (uf !== "BR") main.append(regrasFiscais(g));
  const areas = porArea(inds);
  if (areas.length > 3) {
    main.insertAdjacentHTML("beforeend", `<nav class="areas-nav" aria-label="Ir para a área"><span class="pilula"><i></i>${esc(nomeCurto(g.nome))} · ${periodoTxt(g)}</span>${areas.map(([a]) => `<a href="#" data-area="${esc(a)}">${esc(a)}</a>`).join("")}</nav>`);
    main.querySelectorAll(".areas-nav a").forEach((a) => a.addEventListener("click", (ev) => {
      ev.preventDefault();
      const sec = document.getElementById("area-" + a.dataset.area);
      sec?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
      const h3 = sec?.querySelector("h3"); if (h3) { h3.tabIndex = -1; h3.focus({ preventScroll: true }); }
    }));
  }
  let algum = false;
  for (const [area, is] of areas) {
    const visiveis = is.filter((ind) => filtro === "todos" || veredito(ind, uf, res.get(ind)) === filtro);
    if (!visiveis.length) continue;
    algum = true;
    const sec = document.createElement("section");
    sec.className = "area"; sec.id = "area-" + area;
    sec.innerHTML = `<h3>${esc(area)}</h3>`;
    const grade = document.createElement("div");
    grade.className = "cartoes";
    for (const ind of visiveis) {
      const c = cat(ind), u = ultimo(ind, uf), r = res.get(ind);
      const card = document.createElement("a");
      card.className = "cartao" + (r.d == null ? " sem" : "");
      card.href = `#/indicador/${ind}?uf=${uf}&g=${encodeURIComponent(g.id)}`;
      card.innerHTML = `<span class="nome">${esc(c.nome)}</span>
        ${provisorio(g.tipo) ? "" : `<span class="frase">${frase(ind, r)}</span>`}
        <span class="selos">${r.leitura ? "" : selo(ind, r.d, r)}${uf !== "BR" ? seloBR(ind, r) : ""}</span>`;
      card.append(grafico(ind, uf, { g, br: uf !== "BR", marcas: r.d != null && !r.leitura ? [[r.base, r.herdado], [r.final, r.atual]] : null }));
      card.insertAdjacentHTML("beforeend", `<span class="pe"><span>${esc(nota(r))}</span><span>${c.freq === "mensal" && c.agregacao === "soma" ? "último mês" : "último"}: <b>${esc(fmtU(ind, u[3]))}</b>, ${esc(nomePeriodo(u[0]))}</span></span>`);
      grade.append(card);
    }
    sec.append(grade);
    main.append(sec);
  }
  if (!algum) main.insertAdjacentHTML("beforeend", `<p class="aviso">Nenhum indicador nesta categoria. <a href="${base}">Mostrar todos</a>.</p>`);
}

// regras fiscais do governo estadual: limites da LRF e mínimos constitucionais, ano a ano
function regrasFiscais(g) {
  const regras = ["dcl_rcl", "pessoal_rcl", "aplic_saude_pct", "aplic_mde_pct"].filter((i) => D.catalogo[i] && serie(i, g.uf).length);
  const sec = document.createElement("section");
  if (!regras.length) return sec;
  const anos = anosDaGestao(g).filter((a) => regras.some((i) => anual(i, g.uf).has(a)));
  if (!anos.length) return sec;
  sec.className = "regras";
  let fora = 0;
  const linhas = regras.map((i) => {
    const c = cat(i), A = anual(i, g.uf), ref = c.limite ?? c.meta;
    const cel = anos.map((a) => {
      const v = A.get(a);
      if (v == null) return `<td class="vazio">—</td>`;
      const ruim = c.limite != null ? v > c.limite : v < c.meta;
      if (ruim) fora++;
      return `<td class="${ruim ? "fora" : ""}" title="${ruim ? (c.limite != null ? "acima do limite" : "abaixo do mínimo") : "dentro da regra"}">${esc(fmt(i, v))}${ruim ? " ⚑" : ""}</td>`;
    }).join("");
    return `<tr><th scope="row"><a href="#/indicador/${i}?uf=${g.uf}&g=${encodeURIComponent(g.id)}">${esc(c.nome.replace(/\s*\(.*\)$/, ""))}</a>
      <span class="detalhe">${c.limite != null ? "limite" : "mínimo"} ${esc(fmt(i, ref))}</span></th>${cel}</tr>`;
  }).join("");
  const transposta = ESTREITO() ? `<div class="tabela-wrap"><table class="tabela regras-tab"><thead><tr><th>Ano</th>${regras.map((i) => `<th>${esc({ dcl_rcl: "Dívida", pessoal_rcl: "Pessoal", aplic_saude_pct: "Saúde", aplic_mde_pct: "Educação" }[i])}</th>`).join("")}</tr></thead><tbody>${
    anos.map((a) => `<tr><th scope="row">${a}</th>${regras.map((i) => { const c = cat(i), v = anual(i, g.uf).get(a); if (v == null) return `<td class="vazio">—</td>`;
      const ruim = c.limite != null ? v > c.limite : v < c.meta; return `<td class="${ruim ? "fora" : ""}">${esc(fmt(i, v))}${ruim ? "⚑" : ""}</td>`; }).join("")}</tr>`).join("")}</tbody></table></div>
    <p class="fonte-bloco">Limites: dívida ${esc(fmt("dcl_rcl", 200))} e pessoal 49% da RCL; mínimos: saúde 12% e educação 25% da receita de impostos.</p>` : null;
  sec.innerHTML = `<h3>Regras fiscais no governo</h3>
    <p class="fonte-bloco">${fora ? `<b class="alerta">${fora} ${fora > 1 ? "registros" : "registro"} fora da regra</b> (⚑).` : "Dentro das regras em todos os anos com dado."}
      Dívida e pessoal: limites da Lei de Responsabilidade Fiscal e do Senado (pessoal: só o Executivo, limite de 49%). Saúde e educação: mínimos
      da Constituição (algumas constituições estaduais exigem mais, como SP em educação). Valores declarados pelo estado ao Tesouro (SICONFI).</p>
    ${transposta ?? `<div class="tabela-wrap"><table class="tabela regras-tab"><thead><tr><th></th>${anos.map((a) => `<th class="n">${a}</th>`).join("")}</tr></thead><tbody>${linhas}</tbody></table></div>`}`;
  return sec;
}

// ---------------- página: indicador ----------------
function pagIndicador(ind, params) {
  if (!D.catalogo[ind]) { location.hash = "#/"; return null; }
  const c = cat(ind);
  let uf = params.get("uf") && serie(ind, params.get("uf")).length ? params.get("uf") : "BR";
  if (uf === "BR" && (!serie(ind, "BR").length || SO_ESTADOS.has(ind))) {
    // indicador só estadual: o painel de estados vira a página
    const main = $("#conteudo");
    main.innerHTML = `<a class="voltar" href="#/">← governos</a><div class="ind-cab"><p class="sobretitulo">${esc(c.area)} · ${esc(c.origem)}</p><h1>${esc(c.nome)}</h1>
      <p>${esc(c.descricao.split(". ")[0])}.</p><p class="direcao">Este indicador existe por estado. Escolha um estado para ver a série e os governos.</p>
      <div class="escopo"><label for="uf-ind">Estado</label><select id="uf-ind"><option value="">Escolha…</option>${ORDEM_UF.filter((u) => serie(ind, u).length)
        .sort((a, b) => D.ufs[a].localeCompare(D.ufs[b])).map((u) => `<option value="${u}">${esc(D.ufs[u])}</option>`).join("")}</select></div></div>
      <div class="painel lado-grande" id="lado" style="margin-top:20px"></div>`;
    $("#uf-ind").addEventListener("change", (ev) => { if (ev.target.value) location.hash = `#/indicador/${ind}?uf=${ev.target.value}`; });
    painelEstados(ind, null, $("#lado"));
    document.title = `${c.nome} | Na Régua`;
    return null;
  }
  let g = gestaoPorId(params.get("g"));
  if (g && g.uf !== uf) g = null;
  if (!g) g = [...gestoesDe(uf)].reverse().find((x) => !x.absorvida && avaliar(ind, x).d != null) ?? null;
  const rg = g ? avaliar(ind, g) : null;
  const ufsComDado = ORDEM_UF.filter((u) => serie(ind, u).length);
  const main = $("#conteudo");
  const direcao = c.melhor === "menor" ? "Quanto menor, melhor." : c.melhor === "maior" ? "Quanto maior, melhor." : "Sem melhor ou pior: o número descreve, não avalia.";
  const ufOpts = ["BR", ...ufsComDado.slice().sort((a, b) => D.ufs[a].localeCompare(D.ufs[b]))];
  main.innerHTML = `<a class="voltar" href="#/?uf=${uf}${g ? "&g=" + encodeURIComponent(g.id) : ""}">← governos ${uf === "BR" ? "federais" : esc(prep(uf))}</a>
    <div class="ind-cab"><p class="sobretitulo">${esc(c.area)} · ${esc(c.origem)}</p><h1>${esc(c.nome)}</h1>
      ${(() => { const i = c.descricao.indexOf(". "); return i > 0 && c.descricao.length > 220
        ? `<p>${esc(c.descricao.slice(0, i + 1))}</p><details class="metodo-ind"><summary>Como este número é feito</summary><p>${esc(c.descricao.slice(i + 2))}</p></details>`
        : `<p>${esc(c.descricao)}</p>`; })()}<p class="direcao">${direcao} <span>Unidade: ${esc(c.unidade)} · ${esc(c.freq)}</span></p>
      ${rg && rg.d != null ? `<p class="manchete">Com <b>${esc(g.nome)}</b> (${periodoTxt(g)}): ${frase(ind, rg).replace(/^./, (x) => x.toLowerCase()).replace(/\.?(<\/b>)?$/, "$1")}.
        <span class="selos">${rg.leitura ? "" : selo(ind, rg.d, rg)}${uf !== "BR" ? seloBR(ind, rg) : ""}</span></p>
        ${rg.ressalva || rg.semVeredito || rg.motivoBR ? `<p class="ressalva">${esc([rg.semVeredito, rg.ressalva, rg.motivoBR ? "Comparação com o Brasil: " + rg.motivoBR + "." : ""].filter(Boolean).join(" "))}</p>` : ""}` : ""}
      ${ufOpts.length > 1 ? `<div class="escopo"><label for="uf-ind">Ver para</label><select id="uf-ind">${ufOpts.map((u) => `<option value="${u}" ${u === uf ? "selected" : ""}>${esc(D.ufs[u])}</option>`).join("")}</select></div>` : ""}</div>
    <div class="ind-grade">
      <div class="col-esq"><div class="painel"><h4 id="tit-graf"></h4><div id="graf" class="graf-grande"></div><div class="chave" id="chave"></div></div>
        <section class="painel" id="alinhados"></section></div>
      <div class="painel" id="lado"></div>
    </div>
    <section class="painel" id="ind-gestoes"></section>
    <section class="painel fonte-bloco" id="fonte-ind"><h4>De onde vem este número</h4>
      <p>${esc(c.origem)} · <a href="${esc(c.link)}" target="_blank" rel="noopener">ver na fonte oficial</a></p><div id="arquivos-ind"><p>Carregando a lista de arquivos…</p></div>
      <p>Última coleta: ${D.status[c.fonte]?.em ? new Date(D.status[c.fonte].em).toLocaleString("pt-BR") : "—"}.
        A fonte pode revisar valores; cada revisão fica registrada no histórico do repositório.</p></section>`;
  origemDe(ind).then((org) => {
    const o = org[uf] ?? org.BR, alvo = $("#arquivos-ind");
    if (!alvo) return;
    if (!o) { alvo.innerHTML = ""; return; }
    const lista = `<ul class="arquivos">${o.sha256.map((h, i) => `<li><a href="dados/${esc(o.arquivos?.[i] ?? "")}"><code>${esc(h)}</code></a>
      ${o.url[i] ? ` · <a href="${esc(o.url[i])}" target="_blank" rel="noopener">consulta</a>` : ""}</li>`).join("")}</ul>`;
    alvo.innerHTML = o.sha256.length > 3
      ? `<details><summary>${o.sha256.length} arquivos guardados exatamente como a fonte entregou · ver hashes (SHA-256)</summary>${lista}</details>`
      : `<p>Arquivo${o.sha256.length > 1 ? "s" : ""} guardado${o.sha256.length > 1 ? "s" : ""} exatamente como a fonte entregou (SHA-256):</p>${lista}`;
  });
  $("#uf-ind")?.addEventListener("change", (ev) => { location.hash = `#/indicador/${ind}?uf=${ev.target.value}`; });
  document.title = `${c.nome} — ${D.ufs[uf]} | Na Régua`;

  const ext = extensivo(ind), todas = uf === "BR" && ufsComDado.length > 1 && !ext;
  const temBR = uf !== "BR" && !ext && serie(ind, "BR").length > 0;
  $("#tit-graf").textContent = movel12(ind) ? `${nomeUF(ind, uf)} · saldo acumulado em 12 meses` : uf === "BR" ? (todas ? `${nomeUF(ind, "BR")} e cada estado` : nomeUF(ind, "BR")) : `${D.ufs[uf]}${temBR ? " e " + (ROTULO_TOTAL[ind] ? "a " + ROTULO_TOTAL[ind] : "o Brasil") : ""}`;
  $("#chave").innerHTML = `<span><i></i>${esc(nomeUF(ind, uf))}</span>${temBR ? `<span><i class='br'></i>${esc(nomeUF(ind, "BR"))}</span>` : ""}
    ${todas ? "<span><i class='ufs'></i>cada estado</span>" : ""}<span><i class='fx'></i>governos</span>${g ? "<span><i class='gr'></i>" + esc(g.nome) + "</span>" : ""}`;
  const desenharGrande = () => {
    const box = $("#graf"); if (!box) return;
    const w = Math.max(280, Math.round(box.clientWidth)), h = w < 520 ? 260 : 330;
    box.replaceChildren(grafico(ind, uf, { w, h, px: true, g, br: true, todasUF: todas, eixos: true, interativo: true, faixas: true }));
  };
  desenharGrande();

  governosAlinhados(ind, uf, g, $("#alinhados"));

  // tabela de governos
  const gs = gestoesDe(uf).filter((x) => !x.absorvida && anosDaGestao(x).length);
  const linhas = gs.map((x) => [x, avaliar(ind, x)]).filter(([, r]) => r.d != null).reverse();
  const colBR = uf !== "BR" && linhas.some(([, r]) => r.rel != null);
  $("#ind-gestoes").innerHTML = `<h4>Governo a governo</h4>` + (linhas.length ? `<div class="tabela-wrap"><table class="tabela">
    <thead><tr><th>Governo</th><th>O que aconteceu</th><th>Variação</th>${colBR ? "<th>Comparado ao Brasil</th>" : ""}</tr></thead>
    <tbody>${linhas.map(([x, r]) => `<tr class="${g && x.id === g.id ? "atual" : ""}"><td data-rot="Governo"><a href="#/indicador/${ind}?uf=${uf}&g=${encodeURIComponent(x.id)}">${esc(x.nome)}</a>
      <span class="detalhe">${esc(x.partido)} · ${periodoTxt(x)}${tipoTxt(x) ? " · " + tipoTxt(x) : ""}</span></td>
      <td data-rot="O que aconteceu">${frase(ind, r)}<span class="detalhe">${esc(nota(r))}</span></td>
      <td data-rot="Variação">${r.leitura ? "—" : selo(ind, r.d, r)}</td>${colBR ? `<td data-rot="Comparado ao Brasil">${seloBR(ind, r) || "—"}<span class="detalhe">${esc(explicaBR(ind, r))}</span></td>` : ""}</tr>`).join("")}</tbody></table></div>`
    : `<p class="fonte-bloco">Nenhum governo tem o ano anterior à posse e um ano completo de gestão dentro desta série.</p>`);

  painelEstados(ind, uf, $("#lado"));
  return desenharGrande;
}

// governos alinhados pela posse: mesma escala; o ponto vazio é o que o governo encontrou
function governosAlinhados(ind, uf, gSel, alvo) {
  if (cat(ind).leitura) { alvo.remove(); return; }
  const A = anual(ind, uf);
  const gs = gestoesDe(uf).filter((x) => !x.absorvida).map((x) => [x, avaliar(ind, x)]).filter(([, r]) => r.d != null);
  if (gs.length < 2) { alvo.remove(); return; }
  const trajet = gs.map(([x, r]) => [x, r, [r.base, ...r.anos.filter((a) => a <= r.final)].map((a, i) => [i, A.get(a), a]).filter((p) => p[1] != null)]);
  const vs = trajet.flatMap(([, , t]) => t.map((p) => p[1]));
  const tk = ticksBonitos(Math.min(...vs), Math.max(...vs), 3), lo = tk[0], hi = tk.at(-1);
  const maxN = Math.max(4, ...trajet.map(([, , t]) => t.at(-1)[0]));
  alvo.innerHTML = `<h4>Governos lado a lado</h4><p class="fonte-bloco">Cada quadro começa no ano anterior à posse (o ponto vazio: o que o governo
    encontrou) e segue ano a ano até o último dado. A escala é a mesma em todos.</p><div class="multiplos"></div>`;
  const grade = $(".multiplos", alvo);
  for (const [x, r, t] of trajet) {
    const w = 220, h = 118, e = 6, d = 12, topo = 8, base = 18;
    const X = (i) => e + i / maxN * (w - e - d), Y = (v) => topo + (hi - v) / (hi - lo || 1) * (h - topo - base);
    const svg = s("svg", { viewBox: `0 0 ${w} ${h}`, role: "img", "aria-label": `${x.nome}: ${frase(ind, r).replace(/<[^>]+>/g, "")}` });
    for (const v of tk) svg.append(s("line", { x1: e, x2: w - d, y1: Y(v), y2: Y(v), class: "eixo" }));
    const xa = (X(0) + X(1)) / 2, xz = Math.min(w - 2, X(t.at(-1)[0]) + (X(1) - X(0)) / 2);
    svg.append(s("rect", { x: xa, y: topo - 4, width: Math.max(2, xz - xa), height: h - topo - base + 8, class: "grifo" }));
    svg.append(s("path", { d: t.map((p, i) => `${i ? "L" : "M"}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join(""), class: "linha-serie" }));
    svg.append(s("circle", { cx: X(0), cy: Y(t[0][1]), r: 4, class: "ponto-ini" }));
    svg.append(s("circle", { cx: X(t.at(-1)[0]), cy: Y(t.at(-1)[1]), r: 4, class: "ponto-fim" }));
    svg.append(s("text", { x: X(0) + 6, y: Y(t[0][1]) - 6, class: "val", text: fmt(ind, t[0][1]) }));
    const perto = X(t.at(-1)[0]) - X(0) < 60;
    svg.append(s("text", { x: X(t.at(-1)[0]) + (perto ? 7 : -2), y: Y(t.at(-1)[1]) + (perto ? 16 : -8), "text-anchor": perto ? "start" : "end", class: "val forte", text: fmt(ind, t.at(-1)[1]) }));
    svg.append(s("text", { x: e, y: h - 4, text: String(r.base) }));
    svg.append(s("text", { x: X(t.at(-1)[0]), y: h - 4, "text-anchor": t.at(-1)[0] === maxN ? "end" : "middle", text: String(r.final) }));
    const fig = document.createElement("a");
    fig.className = "multiplo" + (gSel && gSel.id === x.id ? " atual" : "");
    fig.href = `#/indicador/${ind}?uf=${uf}&g=${encodeURIComponent(x.id)}`;
    fig.innerHTML = `<span class="mn">${esc(x.nome)}</span><span class="mp">${esc(x.partido)} · ${periodoTxt(x)}</span>`;
    fig.append(svg);
    fig.insertAdjacentHTML("beforeend", `<span class="mf">${selo(ind, r.d, r)}</span>`);
    grade.append(fig);
  }
}

// ---------------- mapa do Brasil em relevo ----------------
// Cada estado é um "ladrilho" com face (cor do dado) e lateral (a mesma cor, mais escura), num
// plano inclinado em perspectiva. Ao passar o mouse ou focar, o estado sobe e ganha sombra.
function escurecer(hex, f = 0.62) {
  const n = parseInt(hex.slice(1), 16);
  const c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((x) => Math.round(x * f));
  return "#" + c.map((x) => x.toString(16).padStart(2, "0")).join("");
}
const RELEVO = 7;      // espessura do ladrilho, em unidades do SVG
const ELEVACAO = 18;   // quanto o estado sobe ao passar o mouse
function montarMapa(caixa, aoClicar) {
  if (caixa._mapa) return caixa._mapa;
  const W = GEO.largura, H = GEO.altura;
  const svg = s("svg", { viewBox: `-10 -10 ${W + 20} ${H + 30}`, class: "mapa-br", role: "group", "aria-label": "Mapa do Brasil por estado" });
  const defs = s("defs");
  defs.innerHTML = `<filter id="sombra-uf" x="-20%" y="-20%" width="140%" height="160%"><feDropShadow dx="0" dy="14" stdDeviation="9" flood-color="#000" flood-opacity=".35"/></filter>`;
  svg.append(defs);
  const base = s("g", { class: "base" }), faces = s("g", { class: "faces" }), rotulos = s("g", { class: "rotulos", "aria-hidden": "true" }), topo = s("g", { class: "realce", "aria-hidden": "true" });
  const est = {};
  for (const [u, g] of Object.entries(GEO.ufs)) {
    base.append(s("path", { d: g.d, class: "lado", transform: `translate(0 ${RELEVO})`, "data-uf": u }));
    const grupo = s("g", { class: "uf", tabindex: "0", role: "button", "data-uf": u });
    const face = s("path", { d: g.d, class: "face" });
    grupo.append(face);
    faces.append(grupo);
    if (g.area >= 2500) rotulos.append(s("text", { x: g.c[0], y: g.c[1] + 6, "text-anchor": "middle", class: "sigla", text: u }));
    est[u] = { grupo, face, lado: base.querySelector(`[data-uf="${u}"]`) };
  }
  svg.append(base, faces, rotulos, topo);
  const caixa3d = document.createElement("div");
  caixa3d.className = "mapa3d";
  caixa3d.append(svg);
  caixa.replaceChildren(caixa3d);
  // realce: uma cópia do estado, elevada, desenhada por cima de todos
  let atual = null;
  const elevar = (u) => {
    if (atual === u) return;
    topo.replaceChildren();
    atual = u;
    if (!u) return;
    const g = GEO.ufs[u], cor = est[u].cor || (escuro() ? "#262b28" : "#e3e6e1");
    const cop = s("g", { class: "elevado" });
    const lateral = escurecer(cor);
    for (let dy = ELEVACAO + RELEVO; dy > 0; dy -= 3) cop.append(s("path", { d: g.d, class: "lado-alto", style: `fill:${lateral}`, transform: `translate(0 ${dy})` }));
    cop.append(s("path", { d: g.d, class: "face-alta", style: `fill:${cor}` }));
    if (g.area >= 900) cop.append(s("text", { x: g.c[0], y: g.c[1] + 6, "text-anchor": "middle", class: "sigla", style: `fill:${textoSobre(cor)}`, text: u }));
    topo.append(cop);
    cop.style.setProperty("--subida", `-${ELEVACAO}px`);
    requestAnimationFrame(() => requestAnimationFrame(() => cop.classList.add("subiu")));
  };
  for (const [u, e] of Object.entries(est)) {
    e.grupo.addEventListener("pointerenter", () => elevar(u));
    e.grupo.addEventListener("pointerleave", () => { elevar(null); esconderDica(); });
    e.grupo.addEventListener("focus", () => { elevar(u); const r = e.grupo.getBoundingClientRect(); e.grupo._dica?.({ clientX: r.right, clientY: r.top + r.height / 2 }); });
    e.grupo.addEventListener("blur", () => { elevar(null); esconderDica(); });
    e.grupo.addEventListener("click", () => aoClicar(u));
    e.grupo.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); aoClicar(u); } });
  }
  caixa._mapa = { svg, est, elevar, get atual() { return atual; } };
  return caixa._mapa;
}
function pintarMapa(caixa, { cor, rotulo, dica, selecionado, fora, aoClicar }) {
  const m = montarMapa(caixa, aoClicar);
  for (const [u, e] of Object.entries(m.est)) {
    const k = cor(u);
    e.cor = k || null;
    e.face.style.fill = k || ""; e.lado.style.fill = k ? escurecer(k) : "";
    e.grupo.classList.toggle("vazio", !k);
    e.grupo.classList.toggle("sel", u === selecionado);
    e.grupo.classList.toggle("fora", !!fora(u));
    e.grupo.setAttribute("aria-label", rotulo(u));
    e.grupo.setAttribute("aria-pressed", String(u === selecionado));
    e.grupo._dica = (ev) => dica(u, ev);
    e.grupo.onpointermove = e.grupo._dica;
  }
  // estado elevado durante a animação do tempo: refaz a cópia com a cor nova
  const elevadoAgora = m.atual;
  if (elevadoAgora) { m.elevar(null); m.elevar(elevadoAgora); }
  // texto das siglas acompanha a cor de cada estado
  for (const t of m.svg.querySelectorAll(".rotulos .sigla")) { const k = cor(t.textContent); t.style.fill = k ? textoSobre(k) : "var(--grafite)"; }
}

let modoMapaPreferido = "posse";
// mapa do Brasil + linha do tempo + ordem dos estados
function painelEstados(ind, uf, lado) {
  const c = cat(ind), ufsComDado = ORDEM_UF.filter((u) => serie(ind, u).length);
  if (ufsComDado.length < 2) { lado.innerHTML = `<h4>Só existe o número nacional</h4><p class="fonte-bloco">A fonte publica este indicador apenas para o Brasil.</p>`; return; }
  const pers = [...new Set(ufsComDado.flatMap((u) => serie(ind, u).map((p) => p[0])))].sort();
  const ref = new Map();
  for (const u of ["BR", ...ufsComDado]) for (const p of serie(ind, u)) if (!ref.has(p[0])) ref.set(p[0], p);
  const julga = c.melhor && c.melhor !== "neutro" && !extensivo(ind) && serie(ind, "BR").length > 0 && !SEM_VEREDITO[ind] && !c.leitura;
  // escala calculada uma vez para todos os períodos: cores comparáveis ao animar
  const difsTodas = [], valsTodos = [];
  for (const per of pers) {
    const br = serie(ind, "BR").find((x) => x[0] === per)?.[3];
    for (const u of ufsComDado) { const p = serie(ind, u).find((x) => x[0] === per); if (!p) continue;
      valsTodos.push(p[3]); if (br != null) difsTodas.push(Math.abs(sentido(ind, variacao(ind, br, p[3])) ?? 0)); }
  }
  difsTodas.sort((a, b) => a - b); valsTodos.sort((a, b) => a - b);
  const ESC90 = difsTodas[Math.floor(difsTodas.length * 0.9)] || 1;
  // modo "desde a posse": variação de cada estado desde o ano anterior à posse do governador da época,
  // no mesmo trimestre/mês; a cor segue a natureza do indicador (cair é bom na mortalidade, ruim no PIB)
  const direcional = c.melhor && c.melhor !== "neutro" && !SEM_VEREDITO[ind] && !c.leitura;
  const porUF = new Map(["BR", ...ufsComDado].map((u) => [u, new Map(serie(ind, u).map((p) => [p[0], p[3]]))]));
  const baseDaPosse = (u, per) => {
    const p = ref.get(per); if (!p) return null;
    const m = quemGoverna(u, meio(p)); if (!m) return null;
    let g = gestaoDoMandato(m);
    if (g?.absorvida) g = GESTOES.find((t) => t.afastamentos?.includes(g)) ?? g;
    if (!g) return null;
    const anoBase = (anosDaGestao(g)[0] ?? +g.inicio.slice(0, 4)) - 1;
    if (anoBase >= +per.slice(0, 4)) return null;
    for (const a of [anoBase, anoBase - 1]) {
      const rot = per.replace(/^\d{4}/, String(a)), v = porUF.get(u)?.get(rot);
      if (v != null) return { rot, v, g };
    }
    return null;
  };
  const varPosse = (u, per) => { const b = baseDaPosse(u, per), v = porUF.get(u)?.get(per);
    if (!b || v == null) return null; const d = variacao(ind, b.v, v); return d == null ? null : { ...b, d, sg: sentido(ind, d) }; };
  let ESC_POSSE = 1;
  if (direcional) {
    const xs = [];
    for (const per of pers) for (const u of ufsComDado) { const r = varPosse(u, per); if (r?.sg != null) xs.push(Math.abs(r.sg)); }
    xs.sort((a, b) => a - b); ESC_POSSE = xs[Math.floor(xs.length * 0.9)] || 1;
  }
  const modos = [direcional && ["posse", "Desde a posse"], julga && ["brasil", "Comparado ao Brasil"], ["valor", "Valor"]].filter(Boolean);
  let modo = modos.some(([k]) => k === modoMapaPreferido) ? modoMapaPreferido : modos[0][0];
  lado.innerHTML = `<h4>Estados · <span data-p="per"></span></h4>
    ${modos.length > 1 ? `<div class="modo-mapa" role="radiogroup" aria-label="O que a cor mostra" data-p="modos">${modos.map(([k, t]) =>
      `<button type="button" role="radio" data-modo="${k}" aria-checked="${k === modo}">${t}</button>`).join("")}</div>` : ""}
    <p class="fonte-bloco sub-mapa" data-p="sub"></p>
    <div class="blocos" data-p="blocos"></div>
    <div class="legenda" data-p="leg"></div>
    <div class="tempo"><button type="button" class="tocar" data-p="tocar" aria-label="Animar ao longo do tempo">▶</button>
      <input type="range" data-p="tempo" min="0" max="${pers.length - 1}" value="${pers.length - 1}" aria-label="Período"><output data-p="tempo-o"></output></div>
    <h4 class="tit-rank">${extensivo(ind) || c.melhor === "neutro" ? "Do maior para o menor" : `Ordem dos estados <span class="fonte-bloco">${c.melhor === "menor" ? "(menor primeiro)" : "(maior primeiro)"}</span>`}</h4>
    <ol class="ranking" data-p="rank"></ol><button type="button" class="expandir" data-p="mais" hidden>ver os ${ufsComDado.length} estados</button>`;
  const q = (k) => lado.querySelector(`[data-p="${k}"]`);
  let todosVisiveis = false;
  const desenhar = () => {
    const per = pers[+q("tempo").value], pRef = ref.get(per);
    q("per").textContent = nomePeriodo(per); q("tempo-o").textContent = nomePeriodo(per);
    const val = {};
    for (const u of [...ufsComDado, "BR"]) { const p = serie(ind, u).find((x) => x[0] === per); if (p) val[u] = p[3]; }
    const tema = escuro() ? "escuro" : "claro";
    const comVal = ufsComDado.filter((u) => val[u] != null);
    let cor, legenda;
    if (modo === "posse") {
      cor = (u) => { const r = varPosse(u, per); if (!r || r.sg == null) return SEQ[tema][0];
        if (Math.abs(r.d) < limiar(ind)) return DIV[tema][4];
        const k = Math.max(-4, Math.min(4, Math.round(r.sg / ESC_POSSE * 4) || Math.sign(r.sg))); return DIV[tema][k + 4]; };
      legenda = `<span>piorou</span><span class="rampa">${DIV[tema].map((x) => `<span style="background:${x}"></span>`).join("")}</span><span>melhorou</span>
        <span class="br-ref">${c.melhor === "menor" ? "aqui, cair é bom" : "aqui, subir é bom"} · tom mais forte: ${esc(fmtVarAbs(ind, ESC_POSSE))} ou mais · cinza claro: sem base</span>`;
    } else if (modo === "brasil" && val.BR != null) {
      const sg = (u) => sentido(ind, variacao(ind, val.BR, val[u]));
      cor = (u) => { const k = Math.max(-4, Math.min(4, Math.round(sg(u) / ESC90 * 4))); return DIV[tema][k + 4]; };
      legenda = `<span>pior que o Brasil</span><span class="rampa">${DIV[tema].map((x) => `<span style="background:${x}"></span>`).join("")}</span><span>melhor</span><span class="br-ref">tom mais forte: ${esc(fmtVar(ind, ESC90).replace("+", ""))} ou mais</span>
        <span class="br-ref">Brasil: <b>${esc(fmtU(ind, val.BR))}</b></span>`;
    } else if (c.limite != null || c.meta != null) {
      const ord = valsTodos, ref = c.limite ?? c.meta;
      const quebra = (v) => { let k = 0; while (k < 6 && v > ord[Math.min(ord.length - 1, Math.floor((k + 1) * ord.length / 7))]) k++; return k; };
      cor = (u) => SEQ[tema][quebra(val[u])];
      legenda = `<span>menor</span><span class="rampa">${SEQ[tema].map((x) => `<span style="background:${x}"></span>`).join("")}</span><span>maior</span>
        <span class="br-ref">⚑ = ${c.limite != null ? "acima do limite" : "abaixo do mínimo"} legal (${esc(fmtN(ref, 0))}%)</span>`;
    } else if (valsTodos[0] < 0 && valsTodos.at(-1) > 0) {
      // valores com sinal (saldo de empregos, dívida negativa): divergente centrado no zero
      const mx = Math.max(Math.abs(valsTodos[Math.floor(valsTodos.length * 0.05)]), Math.abs(valsTodos[Math.floor(valsTodos.length * 0.95)])) || 1;
      const inv = c.melhor === "menor" ? -1 : 1;
      cor = (u) => { const k = Math.max(-4, Math.min(4, Math.round(inv * val[u] / mx * 4))); return DIV[tema][k + 4]; };
      legenda = `<span>negativo</span><span class="rampa">${DIV[tema].map((x) => `<span style="background:${x}"></span>`).join("")}</span><span>positivo</span><span class="br-ref">cinza = perto de zero</span>`;
    } else {
      const ord = valsTodos;
      const quebra = (v) => { let k = 0; while (k < 6 && v > ord[Math.min(ord.length - 1, Math.floor((k + 1) * ord.length / 7))]) k++; return k; };
      cor = (u) => SEQ[tema][quebra(val[u])];
      legenda = `<span>${esc(fmtU(ind, ord[0]))}</span><span class="rampa">${SEQ[tema].map((x) => `<span style="background:${x}"></span>`).join("")}</span><span>${esc(fmtU(ind, ord.at(-1)))}</span>
        <span class="br-ref">cada tom reúne 1/7 dos valores</span>`;
    }
    const foraDe = (u) => val[u] != null && ((c.limite != null && val[u] > c.limite) || (c.meta != null && val[u] < c.meta));
    const htmlDica = (u) => {
      const gov = pRef ? quemGoverna(u, meio(pRef)) : null;
      const vp = modo === "posse" ? varPosse(u, per) : null;
      const linhaPosse = vp ? `<br><span class="s">desde a posse (${esc(nomePeriodo(vp.rot))} → ${esc(nomePeriodo(per))}): ${esc(fmtVar(ind, vp.d))} · ${Math.abs(vp.d) < limiar(ind) ? "estável" : vp.sg > 0 ? "melhorou" : "piorou"}</span>`
        : modo === "posse" ? `<br><span class="s">sem dado do ano anterior à posse</span>` : "";
      return `<span class="s">${esc(D.ufs[u])} · ${esc(nomePeriodo(per))}</span><br><b>${esc(fmtU(ind, val[u]))}</b>${linhaPosse}${foraDe(u) ? ` <span class="s">⚑ ${c.limite != null ? "acima do limite" : "abaixo do mínimo"}</span>` : ""}
        ${val.BR != null && !extensivo(ind) ? `<br><span class="s">${esc(nomeUF(ind, "BR"))}: ${esc(fmtU(ind, val.BR))}${modo === "brasil" && julga && val[u] != null ? ` · diferença: ${esc(fmtVar(ind, variacao(ind, val.BR, val[u])))}` : ""}</span>` : ""}${gov ? `<br><span class="s">${esc(gov.nome)} (${esc(gov.partido)})</span>` : ""}`;
    };
    const bl = q("blocos");
    if (GEO) {
      bl.className = "mapa-caixa";
      pintarMapa(bl, {
        cor: (u) => val[u] != null ? cor(u) : null,
        rotulo: (u) => { const gov = pRef ? quemGoverna(u, meio(pRef)) : null; return `${D.ufs[u]}: ${val[u] != null ? fmtU(ind, val[u]) : "sem dado"}${foraDe(u) ? ", fora da regra legal" : ""}${gov ? ", governo de " + gov.nome : ""}`; },
        dica: (u, ev) => mostrarDica(ev, htmlDica(u)),
        selecionado: uf, fora: foraDe,
        aoClicar: (u) => { location.hash = `#/indicador/${ind}?uf=${u}`; },
      });
    } else bl.innerHTML = "";
    if (!GEO) for (const [u, [r, col]] of Object.entries(BLOCOS)) {
      const b = document.createElement("button");
      b.type = "button"; b.className = "bloco"; b.style.gridRow = r + 1; b.style.gridColumn = col + 1; b.textContent = u;
      b.setAttribute("aria-pressed", u === uf);
      const gov = pRef ? quemGoverna(u, meio(pRef)) : null;
      b.setAttribute("aria-label", `${D.ufs[u]}: ${val[u] != null ? fmtU(ind, val[u]) : "sem dado"}${gov ? ", governo de " + gov.nome : ""}`);
      if (val[u] != null) {
        const k = cor(u); b.style.background = k; b.style.color = textoSobre(k);
        if ((c.limite != null && val[u] > c.limite) || (c.meta != null && val[u] < c.meta)) { b.textContent = u + "⚑"; b.classList.add("fora"); }
      }
      else b.classList.add("vazio");
      const dicaUF = (ev) => mostrarDica(ev, `<span class="s">${esc(D.ufs[u])} · ${esc(nomePeriodo(per))}</span><br><b>${esc(fmtU(ind, val[u]))}</b>
        ${val.BR != null && !extensivo(ind) ? `<br><span class="s">${esc(nomeUF(ind, "BR"))}: ${esc(fmtU(ind, val.BR))}${julga && val[u] != null ? ` · diferença: ${esc(fmtVar(ind, variacao(ind, val.BR, val[u])))}` : ""}</span>` : ""}${gov ? `<br><span class="s">${esc(gov.nome)} (${esc(gov.partido)})</span>` : ""}`);
      b.addEventListener("pointermove", dicaUF);
      b.addEventListener("focus", () => { const r2 = b.getBoundingClientRect(); dicaUF({ clientX: r2.right, clientY: r2.bottom }); });
      b.addEventListener("blur", esconderDica);
      b.addEventListener("pointerleave", esconderDica);
      b.addEventListener("click", () => { location.hash = `#/indicador/${ind}?uf=${u}`; });
      bl.append(b);
    }
    q("leg").innerHTML = legenda;
    q("sub").textContent = modo === "posse" ? "Cor: quanto o número melhorou ou piorou desde o ano anterior à posse do governador da época (mesmo trimestre ou mês)."
      : modo === "valor" && direcional ? "Cor: valor do estado (mais escuro, maior)."
      : modo === "brasil" && val.BR != null ? "Cor: diferença entre o estado e o Brasil neste período."
      : (c.limite != null || c.meta != null) ? "Cor: valor do estado (mais escuro, maior)."
      : (valsTodos[0] < 0 && valsTodos.at(-1) > 0) ? `Cor: valor do estado (azul ${c.melhor === "menor" ? "negativo" : "positivo"}, vermelho ${c.melhor === "menor" ? "positivo" : "negativo"}).` : "Cor: valor do estado (mais escuro, maior).";
    const merito = !(extensivo(ind) || c.melhor === "neutro");
    const ord = Object.entries(val).filter(([u]) => u !== "BR").sort((a, b) => merito && c.melhor === "menor" ? a[1] - b[1] : b[1] - a[1]);
    const mx = Math.max(...ord.map(([, v]) => Math.abs(v)), Math.abs(val.BR ?? 0)) || 1;
    const item = ([u, v], i) => `<li class="${u === uf ? "sel" : ""}"><span class="pos">${merito ? i + 1 + "º" : ""}</span>
      <span class="nm"><a href="#/indicador/${ind}?uf=${u}">${esc(D.ufs[u])}</a><span class="barra" style="width:${Math.abs(v) / mx * 100}%"></span></span><span class="vl">${esc(fmtU(ind, v))}</span></li>`;
    const corte = !todosVisiveis && ord.length > 12;
    let html = "";
    let ultimoMostrado = -1;
    ord.forEach((x, i) => {
      if (corte && !(i < 5 || i >= ord.length - 5 || x[0] === uf)) return;
      if (i - ultimoMostrado > 1) html += `<li class="reticencias" aria-hidden="true">⋯</li>`;
      html += item(x, i); ultimoMostrado = i;
    });
    if (val.BR != null) html += `<li class="br"><span class="pos"></span><span class="nm">${esc(nomeUF(ind, "BR"))}<span class="barra" style="width:${Math.abs(val.BR) / mx * 100}%"></span></span><span class="vl">${esc(fmtU(ind, val.BR))}</span></li>`;
    q("rank").innerHTML = html;
    q("mais").hidden = !corte;
  };
  q("tempo").addEventListener("input", desenhar);
  q("modos")?.addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-modo]"); if (!b) return;
    modo = modoMapaPreferido = b.dataset.modo;
    q("modos").querySelectorAll("[data-modo]").forEach((x) => x.setAttribute("aria-checked", String(x === b)));
    desenhar();
  });
  q("mais").addEventListener("click", () => { todosVisiveis = true; desenhar(); });
  let timer = null;
  q("tocar").addEventListener("click", () => {
    const bt = q("tocar");
    if (timer) { clearInterval(timer); timer = null; bt.textContent = "▶"; bt.setAttribute("aria-label", "Animar ao longo do tempo"); return; }
    const t = q("tempo"); if (+t.value >= pers.length - 1) t.value = 0;
    bt.textContent = "❚❚"; bt.setAttribute("aria-label", "Pausar animação");
    timer = setInterval(() => {
      if (!document.body.contains(t) || +t.value >= pers.length - 1) { clearInterval(timer); timer = null; bt.textContent = "▶"; bt.setAttribute("aria-label", "Animar ao longo do tempo"); return; }
      t.value = +t.value + 1; desenhar();
    }, pers.length > 60 ? 90 : pers.length > 20 ? 220 : 500);
  });
  desenhar();
}

// ---------------- página: comparar ----------------
function pagComparar(params) {
  const validas = (u) => gestoesDe(u).filter((x) => !x.absorvida && !provisorio(x.tipo) && anosDaGestao(x).length);
  const opcoes = (sel) => [["BR", "Presidência da República"], ...ORDEM_UF.slice().sort((a, b) => D.ufs[a].localeCompare(D.ufs[b])).map((u) => [u, D.ufs[u]])]
    .map(([u, rot]) => `<optgroup label="${esc(rot)}">${validas(u).reverse()
      .map((x) => `<option value="${esc(x.id)}" ${x.id === sel ? "selected" : ""}>${esc(x.nome)} · ${periodoTxt(x)}</option>`).join("")}</optgroup>`).join("");
  const fed = validas("BR");
  const a = gestaoPorId(params.get("a")) ?? fed.at(-1), b = gestaoPorId(params.get("b")) ?? fed.at(-2);
  const estadosDiferentes = a.uf !== b.uf && a.uf !== "BR" && b.uf !== "BR";
  const main = $("#conteudo");
  main.innerHTML = `<section class="abertura"><p class="sobretitulo">Comparar</p><h1>Dois governos, <span class="grifado">a mesma régua</span>.</h1>
    <p class="lead">Para checar frases como “no meu governo foi melhor”. Cada linha usa o mesmo indicador, a mesma fonte e a mesma regra:
      o ano anterior à posse contra o último ano completo do governo.</p></section>
    <div class="duelo"><label class="a"><span><i class="tag a"></i>Governo A</span><select id="ga">${opcoes(a.id)}</select></label><span class="vs" aria-hidden="true">×</span>
      <label class="b"><span><i class="tag b"></i>Governo B</span><select id="gb">${opcoes(b.id)}</select></label></div>
    ${estadosDiferentes ? `<p class="aviso"><b>Estados diferentes.</b> O destaque de cada linha é a comparação com o Brasil no mesmo período, que desconta o que aconteceu no país inteiro. A variação bruta vem logo depois.</p>` : ""}
    ${(a.uf === "BR") !== (b.uf === "BR") ? `<p class="aviso"><b>Presidência × governo estadual.</b> Os números são de escopos diferentes (país e estado). Compare com cuidado.</p>` : ""}
    <div class="duelo-placar" id="duelo-placar"></div>
    <div class="tabela-wrap fixa"><table class="tabela comparar" id="tab-comp"></table></div>`;
  const ir = () => { location.hash = `#/comparar?a=${encodeURIComponent($("#ga").value)}&b=${encodeURIComponent($("#gb").value)}`; };
  $("#ga").onchange = $("#gb").onchange = ir;
  const inds = [...new Set([...indicadoresDe(a.uf), ...indicadoresDe(b.uf)])];
  const cel = (ind, g, r, rot) => {
    if (r.d == null) return `<td data-rot="${esc(rot)}"><span class="detalhe">${esc(r.motivo ?? "Sem dado neste escopo.")}</span></td>`;
    const principal = estadosDiferentes && r.rel != null ? seloBR(ind, r) : r.leitura ? "" : selo(ind, r.d, r);
    const extra = estadosDiferentes ? (r.rel != null && !r.leitura ? selo(ind, r.d, r) : "") : (g.uf !== "BR" ? seloBR(ind, r) : "");
    return `<td data-rot="${esc(rot)}"><span class="frase-p">${frase(ind, r)}</span><span class="selos">${principal}${extra}</span><span class="detalhe">${esc(nota(r))}</span></td>`;
  };
  // só conta indicadores que têm veredito nos DOIS governos (mesmo denominador)
  const comuns = inds.filter((i) => veredito(i, a.uf, avaliar(i, a)) != null && veredito(i, b.uf, avaliar(i, b)) != null);
  const placarDe = (g) => { const k = { melhor: 0, pior: 0, igual: 0 };
    for (const i of comuns) { const v = veredito(i, g.uf, avaliar(i, g)); if (v in k) k[v]++; } return k; };
  const pa = placarDe(a), pb = placarDe(b);
  const rot = (g) => g.uf === "BR" ? ["melhoraram", "pioraram", "estáveis"] : ["melhor que o Brasil", "pior que o Brasil", "igual ao Brasil"];
  const bloco = (g, k, cls) => `<div class="dp ${cls}"><span class="dp-nome"><i class="tag ${cls}"></i>${esc(g.nome)} <small>${periodoTxt(g)}</small></span>
    <span class="dp-n"><b class="m">${k.melhor}</b> ${rot(g)[0]}</span><span class="dp-n"><b class="p">${k.pior}</b> ${rot(g)[1]}</span><span class="dp-n"><b>${k.igual}</b> ${rot(g)[2]}</span></div>`;
  $("#duelo-placar").innerHTML = bloco(a, pa, "a") + bloco(b, pb, "b") + `<p class="fonte-bloco">Contagem sobre os ${comuns.length} indicadores com veredito nos dois governos. Não pesa importância nem prova causa.</p>`
    + [a, b].filter((g) => !g.fim).map((g) => `<p class="aviso"><b>${esc(g.nome)}: governo em andamento.</b> ${((n) => `${n} ${n === 1 ? "ano completo" : "anos completos"}`)(anosDaGestao(g).filter((x) => x < +HOJE.slice(0, 4)).length)} até agora; os números ainda podem mudar.</p>`).join("");
  $("#tab-comp").innerHTML = `<thead><tr><th>Indicador</th><th><i class="tag a"></i>${esc(a.nome)} <span class="detalhe">${esc(cargo(a))} · ${periodoTxt(a)}</span></th>
    <th><i class="tag b"></i>${esc(b.nome)} <span class="detalhe">${esc(cargo(b))} · ${periodoTxt(b)}</span></th></tr></thead><tbody>${
    porArea(inds).map(([ar, is]) => `<tr class="area-linha"><td colspan="3">${esc(ar)}</td></tr>` + is.map((ind) =>
      `<tr><td class="ind-nome"><a href="#/indicador/${ind}?uf=${a.uf}&g=${encodeURIComponent(a.id)}">${esc(cat(ind).nome)}</a><span class="detalhe">${esc(cat(ind).origem)}</span></td>
        ${cel(ind, a, avaliar(ind, a), "A · " + a.nome)}${cel(ind, b, avaliar(ind, b), "B · " + b.nome)}</tr>`).join("")).join("")}</tbody>`;
}

// ---------------- página: mapa ----------------
function pagMapa(params) {
  const comUF = Object.keys(D.catalogo).filter((i) => ORDEM_UF.filter((u) => serie(i, u).length).length > 5);
  const ind = comUF.includes(params.get("i")) ? params.get("i") : comUF.includes("desocupacao") ? "desocupacao" : comUF[0];
  const main = $("#conteudo");
  main.innerHTML = `<section class="abertura"><p class="sobretitulo">Mapa</p><h1>O mesmo número, <span class="grifado">estado por estado</span>.</h1>
    <p class="lead">Escolha um indicador e arraste a linha do tempo, ou aperte ▶ para ver a evolução. Clique num estado para abrir a série completa com os governos.</p>
    <div class="escopo"><label for="ind-mapa">Indicador</label><select id="ind-mapa">${porArea(comUF).map(([a, is]) => `<optgroup label="${esc(a)}">${is.map((i) =>
      `<option value="${i}" ${i === ind ? "selected" : ""}>${esc(cat(i).nome)}</option>`).join("")}</optgroup>`).join("")}</select></div></section>
    <div class="painel lado-grande" id="mapa-painel"></div>
    <p class="fonte-bloco nota-mapa">${esc(cat(ind).descricao)} <a href="#/indicador/${ind}">Ver a série completa e a fonte</a>.</p>`;
  $("#ind-mapa").onchange = (ev) => { location.hash = `#/mapa?i=${ev.target.value}`; };
  painelEstados(ind, null, $("#mapa-painel"));
}

// ---------------- página: fontes ----------------
function pagFontes() {
  const porFonte = {};
  for (const [k, c] of Object.entries(D.catalogo)) (porFonte[c.fonte] ??= []).push([k, c]);
  const n = Object.keys(D.catalogo).length;
  const main = $("#conteudo");
  main.innerHTML = `<section class="abertura"><p class="sobretitulo">Fontes e auditoria</p><h1>De onde vem <span class="grifado">cada número</span>.</h1>
    <p class="lead">${n} indicadores de fontes públicas oficiais. Cada valor vem de um arquivo baixado da fonte e guardado sem alteração,
    com o nome igual ao seu hash SHA-256. O registro de cada download está em <a href="dados/proveniencia.csv">proveniencia.csv</a>, a tabela consolidada em
    <a href="dados/indicadores.csv">indicadores.csv</a>, e a lista de governantes, com a fonte de cada linha, em <a href="dados/mandatos.csv">mandatos.csv</a>.</p></section>
    <div class="como-ler"><p><b>Para refazer qualquer número:</b> abra o indicador, siga o link do arquivo guardado e rode o coletor correspondente
    em <code>etl/fontes/</code>. Arquivos grandes estão comprimidos (.gz); o hash é do conteúdo descomprimido.</p></div>
    <div class="fontes-lista">${Object.entries(D.status).sort().map(([f, st]) => {
      const inds = (porFonte[f] ?? []).sort((x, y) => x[1].nome.localeCompare(y[1].nome));
      const NOMES = { ibge: "IBGE", ibge_extra: "IBGE · Contas, educação e domicílios", bcb: "Banco Central do Brasil", ambiente: "INPE",
        comex: "Ministério do Desenvolvimento — Comex Stat", cultura: "Cultura — ANCINE e Lei Rouanet (SALIC)", mds: "Ministério do Desenvolvimento Social",
        inep: "INEP", caged: "Ministério do Trabalho — Novo CAGED", datasus: "Ministério da Saúde — DATASUS", siconfi: "Tesouro Nacional — SICONFI" };
      const origens = NOMES[f] ?? ([...new Set(inds.map(([, c]) => c.origem))].join(" · ") || f);
      return `<div class="fonte-cartao"><h3>${esc(origens)}</h3>
        ${st.ok ? `<span class="estado-ok">● Coleta em dia</span> <span class="fonte-bloco">${new Date(st.em).toLocaleString("pt-BR")} · ${st.linhas.toLocaleString("pt-BR")} valores</span>`
          : `<span class="estado-falha">▲ A última coleta falhou</span> <span class="fonte-bloco">(${new Date(st.em).toLocaleString("pt-BR")}): <code>${esc(st.erro)}</code>
             ${st.ultima_ok ? `Os números exibidos são da coleta de ${new Date(st.ultima_ok).toLocaleString("pt-BR")}.` : ""}</span>`}
        <ul>${inds.map(([k, c]) => {
          const sr = serie(k, "BR").length ? serie(k, "BR") : Object.values(D.series[k] ?? {})[0] ?? [];
          const nUF = ORDEM_UF.filter((u) => serie(k, u).length).length;
          return `<li><a href="#/indicador/${k}">${esc(c.nome)}</a> <span class="fonte-bloco">· ${esc(c.freq)} · ${esc(nomePeriodo(sr[0]?.[0] ?? "?"))} a ${esc(nomePeriodo(sr.at(-1)?.[0] ?? "?"))}
            · ${nUF ? nUF + " UFs" : "só Brasil"} · <a href="${esc(c.link)}" target="_blank" rel="noopener">fonte</a></span></li>`;
        }).join("")}</ul></div>`;
    }).join("")}</div>`;
}

// ---------------- página: método ----------------
function pagMetodo() {
  const lista = (o) => Object.entries(o).map(([k, t]) => `<li><a href="#/indicador/${k}">${esc(cat(k)?.nome ?? k)}</a>: ${esc(t)}</li>`).join("");
  $("#conteudo").innerHTML = `<section class="abertura"><p class="sobretitulo">Método</p><h1>Como a <span class="grifado">régua</span> funciona.</h1>
    <p class="lead">As mesmas regras valem para todos os governos e todos os partidos. Elas estão escritas aqui e no código público do site.</p></section>
    <div class="metodo-pg">
    <h2>O que é um governo</h2>
    <p>A mesma pessoa no mesmo mandato eleitoral, do primeiro ao último dia. Afastamentos no meio (licença, suspensão judicial) ficam dentro do mandato
      do titular e aparecem listados. Interinos e interventores federais não são avaliados. Um ano conta para o governo quando ele governou mais de seis meses nele.
      Quem governou e quando vem de <a href="dados/mandatos.csv">uma tabela com a fonte oficial de cada linha</a> (TSE, Diário Oficial, Assembleias, STF).</p>
    <h2>O que se compara</h2>
    <p>O <b>ano anterior à posse</b> (o que o governo encontrou) contra o <b>último ano completo</b> do governo com dado. Valores trimestrais e mensais viram média
      anual; estoques como dívida e juros usam dezembro. Séries a cada dois anos (IDEB) usam a última edição antes da posse.</p>
    <p><b>Fluxos</b>, como o saldo de empregos e o crescimento do PIB, não têm “antes e depois”: o site mostra a soma ou a média do período, sem veredito.</p>
    <h2>Quando dizer “melhorou” ou “piorou”</h2>
    <ul><li>Só quando o indicador tem direção clara (menos desemprego é melhor). Gasto por área, população, comércio exterior e similares descrevem, não julgam.</li>
      <li>Nas pesquisas por amostra (PNAD), variações dentro da margem de erro de 95% contam como <b>estáveis</b>.</li>
      <li>Dados que a fonte ainda vai revisar (preliminares) aparecem, mas a comparação usa o último ano definitivo.</li>
      <li>Anos atípicos não servem de ponta: ${Object.keys(ATIPICOS).map((k) => esc(cat(k)?.nome ?? k)).join("; ")} (pandemia).</li>
      <li>Em registros escolares e de vacinação (${[...VERIFICAR_SALTOS].map((k) => esc(cat(k)?.nome ?? k)).join("; ")}), saltos de mais de 60% de um ano para outro indicam provável mudança de registro: o número aparece sem veredito.</li>
      <li>IDEB (a cada dois anos): parte da edição anterior à posse, até dois anos antes; a edição do 1º ano do governo não serve de ponto final. Se a edição anterior foi atípica, parte da edição do 1º ano, e isso aparece escrito.</li>
      <li>Homicídios: se, somando as mortes de intenção indeterminada (possíveis homicídios não classificados), a tendência se inverte ou desaparece, não há veredito; se só a diferença para o Brasil desaparece, vale “igual ao Brasil”.</li>
      <li>Taxas de registros (mortes, crimes) levam margem de erro de contagem (Poisson): em estados pequenos, poucas mortes a mais ou a menos contam como “estável” ou “igual ao Brasil”.</li>
      <li>Ano de partida: o anterior à posse. Se ele não tem dado (a PNAD não tem 2020–2021, por exemplo), usa-se o ano anterior a ele, só para governos com pelo menos dois anos contados, e isso aparece escrito no cartão.</li>
      <li>Vacinação acima de 100% (erro de denominador ou campanha) não serve de ponta de comparação.</li></ul>
    <h2>Estados comparados ao Brasil</h2>
    <p>Para não confundir o que aconteceu no país inteiro com o que foi mérito ou culpa do estado, cada governo estadual é comparado ao Brasil nos mesmos anos:</p>
    <ul><li><b>Taxas com ideal claro</b> (pobreza, analfabetismo, jovens que não estudam nem trabalham, abandono escolar): a parte do problema que cada um reduziu. Assim um estado que já estava perto do ideal não é punido por ter menos espaço para melhorar.</li>
      <li><b>Ocupação, carteira assinada, creche, informalidade, vacinação</b>: pontos ganhos ou perdidos.</li>
      <li><b>Demais indicadores</b> (desemprego, renda, mortalidade, homicídios): variação percentual.</li>
      <li>Se pontos e proporção do problema discordam, ou se a diferença cabe na margem de erro dos dois, vale “igual ao Brasil”. A diferença mínima é de 3 pontos de progresso (ou o limiar do próprio indicador, quando a comparação é em pontos).</li>
      <li>Estado perto do teto: se oscilou dentro da margem de erro e segue em nível melhor que o Brasil, vale “igual”.</li>
      <li>Fluxos (crescimento do PIB estadual, saldo de empregos) mostram o número do Brasil ao lado, sem veredito.</li></ul>
    <h2>Indicadores sem veredito</h2><ul>${lista(SEM_VEREDITO)}</ul>
    <h2>O que a régua não diz</h2>
    <p>Não prova causa. Saúde, educação e segurança dependem de União, estados e municípios; a economia depende do mundo; o primeiro ano de governo roda com o
      orçamento aprovado pelo antecessor. A contagem de “melhoraram/pioraram” não pesa a importância de cada indicador, e alguns melhoram há décadas em quase todo governo.</p>
    <h2>Auditoria</h2>
    <p>Todo número vem de um arquivo baixado da fonte oficial e guardado sem alteração, identificado pelo hash SHA-256. Veja <a href="#/fontes">Fontes e auditoria</a>.</p>
    </div>`;
}

// ---------------- busca: "checar um número" ----------------
const SINONIMOS = { desocupacao: "desemprego emprego", cvli: "homicídio assassinato mortes violentas", mortes_intervencao_estado: "polícia letalidade policial", caged_saldo: "emprego vagas carteira empregos gerados", dcl_rcl: "dívida estado endividamento",
  divida_bruta: "dívida pública", ipca_12m: "inflação preços", pib_variacao_br: "crescimento economia pib", homicidios: "assassinatos violência",
  mvi: "assassinatos homicídio violência mortes violentas", desmatamento_amazonia: "desmatamento amazônia floresta", pobreza: "miséria pobres", extrema_pobreza: "fome miséria",
  bf_familias: "bolsa família auxílio", desp_saude_pct: "saúde gasto", aplic_saude_pct: "saúde mínimo constitucional",
  aplic_mde_pct: "educação mínimo constitucional", leitos_sus: "saúde hospital leitos", abandono_em: "escola evasão", ideb_em: "escola ensino médio educação qualidade", mortalidade_infantil: "bebês saúde",
  salario_minimo_real: "salário mínimo", rendimento: "salário renda", selic: "juros", cambio: "dólar" };
const norm = (x) => String(x).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
// em "dívida"/"pib" no escopo nacional, o indicador nacional vem antes do estadual
const PREFERIR_BR = { divida: "divida_bruta", pib: "pib_variacao_br", crescimento: "pib_variacao_br" };
function buscarIndicadores(txt) {
  let q = norm(txt).trim(), uf = null;
  // "homicídio rj", "pib minas": reconhece a UF por sigla ou nome
  const APELIDOS = { minas: "MG", "rio grande do sul": "RS", gaucho: "RS", "rio grande do norte": "RN", rio: "RJ", sampa: "SP", "santa catarina": "SC",
    "mato grosso do sul": "MS", "espirito santo": "ES", brasilia: "DF", "distrito federal": "DF", capixaba: "ES", paulista: "SP", carioca: "RJ", mineiro: "MG", baiano: "BA" };
  for (const [ap, u] of Object.entries(APELIDOS).sort((a, b) => b[0].length - a[0].length)) {
    const re = new RegExp(`(^|\\s)${ap}(\\s|$)`);
    if (re.test(q)) { uf = u; q = q.replace(re, " ").trim(); break; }
  }
  for (const u of uf ? [] : ORDEM_UF) {
    const nome = norm(D.ufs[u]);
    const re = new RegExp(`(^|\\s)(${u.toLowerCase()}|${nome})(\\s|$)`);
    if (re.test(q)) { uf = u; q = q.replace(re, " ").trim(); break; }
  }
  const escopo = uf ?? contexto.uf;
  const PARADAS = new Set(["no", "na", "nos", "nas", "em", "de", "do", "da", "dos", "das", "o", "a", "os", "as", "e", "por", "para", "com", "governo", "estado"]);
  const termos = q.split(/\s+/).filter((t) => t.length > 1 && !PARADAS.has(t));
  const res = [];
  for (const [k, c] of Object.entries(D.catalogo)) {
    // no escopo Brasil, indicadores só estaduais aparecem com "escolha um estado"
    if (!serie(k, escopo).length && !(escopo === "BR" && ORDEM_UF.some((u) => serie(k, u).length))) continue;
    const alvo = norm(c.nome + " " + (SINONIMOS[k] ?? "") + " " + c.area);
    if (termos.length ? !termos.every((t) => alvo.includes(t)) : !uf) continue;
    let p = 0;
    if (norm(c.nome).startsWith(q)) p += 5;
    if (termos.some((t) => norm(c.nome).includes(t))) p += 3;
    if (escopo === "BR" && Object.entries(PREFERIR_BR).some(([t, id]) => q.includes(t) && id === k)) p += 10;
    if (cat(k).melhor && cat(k).melhor !== "neutro") p += 1;
    res.push([p, k]);
  }
  const itens = res.sort((x, y) => y[0] - x[0] || cat(x[1]).nome.localeCompare(cat(y[1]).nome)).slice(0, 8).map((x) => x[1]);
  // só o nome do estado: oferece os governos dele
  return { uf: escopo, itens: !termos.length && uf ? ["@governos", ...itens.slice(0, 6)] : itens };
}
function montarBusca() {
  const f = document.createElement("form");
  f.className = "busca"; f.setAttribute("role", "search");
  f.innerHTML = `<label class="sr" for="busca-in">Checar um número</label>
    <input id="busca-in" role="combobox" aria-expanded="false" aria-controls="busca-lista" aria-autocomplete="list" placeholder="Checar um número: desemprego no RJ, dívida…" autocomplete="off">
    <ul id="busca-lista" role="listbox" hidden></ul><span id="busca-status" class="sr" aria-live="polite"></span>`;
  const inp = $("#busca-in", f), lista = $("#busca-lista", f);
  let itens = [], ufBusca = "BR", ativo = -1;
  const ir = (k) => { if (!k) return; inp.value = ""; fechar(); focarTitulo = true;
    if (k === "@governos") { location.hash = `#/?uf=${ufBusca}`; return; }
    const uf = serie(k, ufBusca).length ? ufBusca : "BR";
    location.hash = `#/indicador/${k}?uf=${uf}${contexto.g && contexto.uf === uf ? "&g=" + encodeURIComponent(contexto.g) : ""}`; };
  const fechar = () => { lista.hidden = true; inp.setAttribute("aria-expanded", "false"); ativo = -1; };
  const desenhar = () => {
    lista.innerHTML = itens.length ? itens.map((k, i) => k === "@governos"
      ? `<li role="option" id="op-${i}" aria-selected="${i === ativo}" data-k="${k}"><b>Governos ${esc(prep(ufBusca))}</b><span>régua de governadores e todos os indicadores</span></li>`
      : `<li role="option" id="op-${i}" aria-selected="${i === ativo}" data-k="${k}"><b>${esc(cat(k).nome)}</b><span>${esc(cat(k).area)} · ${serie(k, ufBusca).length && !(ufBusca === "BR" && SO_ESTADOS.has(k)) ? esc(D.ufs[ufBusca]) : "por estado — escolha um estado"}</span></li>`).join("")
      : `<li class="vazio">Nenhum indicador encontrado${ufBusca !== "BR" ? " para " + esc(D.ufs[ufBusca]) : ""}.</li>`;
    lista.hidden = !inp.value.trim(); inp.setAttribute("aria-expanded", String(!lista.hidden));
    $("#busca-status").textContent = inp.value.trim() ? `${itens.length} resultado${itens.length === 1 ? "" : "s"}` : "";
    if (ativo >= 0) inp.setAttribute("aria-activedescendant", "op-" + ativo); else inp.removeAttribute("aria-activedescendant");
  };
  inp.addEventListener("input", () => { const r = buscarIndicadores(inp.value); itens = r.itens; ufBusca = r.uf; ativo = itens.length ? 0 : -1; desenhar(); });
  inp.addEventListener("keydown", (ev) => {
    if (ev.key === "ArrowDown") { ev.preventDefault(); ativo = Math.min(itens.length - 1, ativo + 1); desenhar(); }
    else if (ev.key === "ArrowUp") { ev.preventDefault(); ativo = Math.max(0, ativo - 1); desenhar(); }
    else if (ev.key === "Escape") fechar();
  });
  lista.addEventListener("mousedown", (ev) => { const li = ev.target.closest("li[data-k]"); if (li) { ev.preventDefault(); ir(li.dataset.k); } });
  inp.addEventListener("blur", () => setTimeout(fechar, 120));
  f.addEventListener("submit", (ev) => { ev.preventDefault(); ir(itens[Math.max(0, ativo)]); });
  $(".menu").before(f);
}
const contexto = { uf: "BR", g: null };

// ---------------- roteador ----------------
let redesenhar = null, focarRegua = false, focarTitulo = false;
function rotear() {
  esconderDica();
  const [caminhoHash, q] = (location.hash.slice(1) || "/").split("?");
  const params = new URLSearchParams(q ?? "");
  const partes = caminhoHash.split("/").filter(Boolean);
  const rota = partes[0] ?? "inicio";
  document.querySelectorAll(".menu a").forEach((a) => {
    if (a.dataset.rota === rota) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  redesenhar = null;
  if (rota === "indicador") redesenhar = pagIndicador(partes[1], params);
  else if (rota === "comparar") pagComparar(params);
  else if (rota === "mapa") pagMapa(params);
  else if (rota === "fontes") pagFontes();
  else if (rota === "metodo") pagMetodo();
  else pagGovernos(params);
  if (rota !== "indicador") document.title = ({ comparar: "Comparar governos", mapa: "Mapa", fontes: "Fontes e auditoria", metodo: "Como a régua funciona" }[rota]
    ?? (contexto.uf === "BR" ? "Governos federais" : `Governos ${prep(contexto.uf)}`)) + " | Na Régua";
  if (!params.has("f")) scrollTo({ top: 0 });
  if (focarTitulo) { focarTitulo = false; const h = $("#conteudo h1"); if (h) { h.tabIndex = -1; h.focus({ preventScroll: true }); } }
}

let larguraAnterior = innerWidth, adiado = null;
addEventListener("resize", () => {
  clearTimeout(adiado);
  adiado = setTimeout(() => {
    if (Math.abs(innerWidth - larguraAnterior) < 40) return;
    const cruzou = (larguraAnterior < 700) !== (innerWidth < 700);
    larguraAnterior = innerWidth;
    if (redesenhar && !cruzou) redesenhar();
    else { const y = scrollY; rotear(); scrollTo({ top: y }); }
  }, 180);
});
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => D && rotear());

// expande o formato compacto do dados.json para [periodo, inicio, fim, valor, ic95, "p"]
function expandir(ind, p) {
  const [per, v, ic = null, st = ""] = p, ano = +per.slice(0, 4);
  let ini, fim, m;
  if ((m = /^\d{4}-T(\d)$/.exec(per))) { const t = +m[1]; ini = `${ano}-${String(3 * t - 2).padStart(2, "0")}-01`; fim = new Date(Date.UTC(ano, 3 * t, 0)).toISOString().slice(0, 10); }
  else if ((m = /^\d{4}-(\d{2})$/.exec(per))) { ini = `${per}-01`; fim = new Date(Date.UTC(ano, +m[1], 0)).toISOString().slice(0, 10); }
  else {
    const mi = D.catalogo[ind]?.mes_inicio;
    if (mi) { ini = `${ano - 1}-${String(mi).padStart(2, "0")}-01`; fim = new Date(Date.UTC(ano, mi - 1, 0)).toISOString().slice(0, 10); }
    else { ini = `${ano}-01-01`; fim = `${ano}-12-31`; }
  }
  return [per, ini, fim, v, ic, st];
}
const VERSAO_DADOS = document.querySelector("script[data-dados]")?.dataset.dados ?? "";
const ORIGEM = new Map();
function origemDe(ind) {
  if (!ORIGEM.has(ind)) ORIGEM.set(ind, fetch(`origem/${ind}.json?v=${VERSAO_DADOS}`).then((r) => r.ok ? r.json() : {}).catch(() => ({})));
  return ORIGEM.get(ind);
}
let GEO = null;   // contorno das UFs (site/brasil.json, malha oficial do IBGE)
const geoPronta = fetch(`brasil.json?v=${VERSAO_DADOS}`).then((r) => r.json()).then((g) => { GEO = g; }).catch(() => {});
Promise.all([fetch(`dados.json?v=${VERSAO_DADOS}`).then((r) => r.json()), geoPronta]).then(([dados]) => {
  D = dados;
  for (const [ind, porUF] of Object.entries(D.series)) for (const uf in porUF) porUF[uf] = porUF[uf].map((p) => expandir(ind, p));
  montarGestoes();
  montarBusca();
  // "pular para o conteúdo" sem mexer na rota
  $(".pular")?.addEventListener("click", (ev) => { ev.preventDefault(); $("#conteudo").focus(); });
  $("#gerado-em").textContent = new Date(D.gerado_em).toLocaleString("pt-BR");
  addEventListener("hashchange", rotear);
  rotear();
}).catch((e) => { $("#conteudo").innerHTML = `<p class="aviso"><b>Não foi possível carregar os dados</b> (${esc(e.message)}). Recarregue a página.</p>`; });
