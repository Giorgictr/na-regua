# Na Régua

Os números de cada governo, com fonte. Indicadores oficiais de economia, trabalho, renda, contas públicas,
saúde, educação, segurança, meio ambiente, cultura e proteção social, para o Brasil e os 27 estados desde
2012, organizados por mandato de presidente e de governador, atualizados automaticamente e auditáveis até
o arquivo original da fonte.

## Indicadores (84)

- **Contas públicas**: Aplicação em educação – MDE (% da receita de impostos); Aplicação em saúde (% da receita de impostos); Despesa com Assistência Social (% da despesa); Despesa com Assistência Social por habitante; Despesa com Ciência e Tecnologia (% da despesa); Despesa com Ciência e Tecnologia por habitante; Despesa com Cultura (% da despesa); Despesa com Cultura por habitante; Despesa com Educação (% da despesa); Despesa com Educação por habitante; Despesa com Saneamento (% da despesa); Despesa com Saneamento por habitante; Despesa com Saúde (% da despesa); Despesa com Saúde por habitante; Despesa com Segurança Pública (% da despesa); Despesa com Segurança Pública por habitante; Despesa com pessoal do Executivo (% da RCL); Dívida bruta do governo geral; Dívida consolidada líquida (% da RCL); Dívida líquida do setor público; Investimentos (% da despesa); Resultado primário do setor público (12 meses)
- **Cultura**: Captação via Lei Rouanet; Projetos que captaram via Lei Rouanet; Salas de cinema em funcionamento
- **Demografia**: População residente
- **Economia**: Atividade econômica (IBC-Br / IBC-R); Crescimento real do PIB do Brasil; Endividamento das famílias; Exportações (US$ FOB); Importações (US$ FOB); Inadimplência das pessoas físicas; Inflação (IPCA acumulado em 12 meses); PIB per capita (a preços de hoje); Reservas internacionais; Saldo comercial (US$ FOB); Taxa Selic (meta); Taxa de câmbio (dólar PTAX)
- **Educação**: Distorção idade-série — ensino médio (rede estadual); IDEB — anos finais do fundamental (rede estadual); IDEB — anos iniciais do fundamental (rede estadual); IDEB — ensino médio (rede estadual); Jovens de 15 a 24 anos que não estudam nem trabalham; Média de anos de estudo (25 anos ou mais); Taxa ajustada de frequência escolar líquida no ensino médio (15 a 17 anos); Taxa de abandono — anos finais do fundamental (rede estadual); Taxa de abandono — ensino médio (rede estadual); Taxa de analfabetismo (15 anos ou mais); Taxa de escolarização de 0 a 3 anos (creche); Taxa de escolarização de 4 a 5 anos (pré-escola)
- **Meio ambiente**: Desmatamento na Amazônia Legal (PRODES); Desmatamento no Cerrado (PRODES); Focos de queimadas (satélite de referência)
- **Moradia**: Domicílios abastecidos pela rede geral de água; Domicílios com esgoto ligado à rede geral; Domicílios com uso de internet
- **Proteção social**: Famílias em situação de pobreza no CadÚnico; Famílias no Bolsa Família / Auxílio Brasil; Valor pago pelo Bolsa Família / Auxílio Brasil
- **Renda**: População abaixo da linha de extrema pobreza; População abaixo da linha de pobreza; Rendimento médio mensal real domiciliar per capita; Rendimento médio real do trabalho; Salário mínimo real; Índice de Gini da renda domiciliar per capita
- **Saúde**: Cobertura vacinal — tríplice viral (1ª dose); Esperança de vida ao nascer; Leitos de internação do SUS por mil habitantes; Mortes evitáveis de 5 a 74 anos (taxa padronizada); Razão de mortalidade materna; Taxa de mortalidade infantil
- **Segurança**: Crimes violentos letais intencionais (CVLI); Estupros registrados; Feminicídios; Mortes por intervenção de agentes do Estado; Mortes violentas intencionais (MVI); Roubos de veículo; Taxa de homicídios
- **Trabalho**: Empregados do setor privado com carteira assinada; Nível de ocupação; Saldo de empregos formais (Novo CAGED); Taxa composta de subutilização; Taxa de desocupação; Taxa de informalidade

Fontes: IBGE (SIDRA), Banco Central (SGS), Tesouro Nacional (SICONFI), Ministério da Saúde (DATASUS:
SIM, SINASC, CNES, PNI), INEP, Ministério do Trabalho (Novo CAGED via IPEADATA), Ministério da Justiça
(SINESP), INPE (PRODES, Queimadas), MDIC (Comex Stat), MDS (Bolsa Família/CadÚnico), ANCINE e SALIC.

## O que o portal mostra

- **Governos**: uma régua com todos os governos desde 2011; o escolhido fica grifado em todos os
  indicadores, com uma frase do que aconteceu ("caiu de 12,8% para 7,9%").
- **Indicador**: série completa com as faixas de cada governo, governos alinhados pela posse, mapa do
  Brasil em blocos, ordem dos estados e a lista de arquivos de origem.
- **Comparar**: dois governos lado a lado, mesma regra para todos.
- **Mapa** e **Fontes e auditoria**.

## Método

- **Valor herdado × último ano**: ano anterior à posse contra o último ano completo do governo (média
  dos trimestres/meses; estoques como dívida e Selic usam dezembro). Séries bienais (IDEB) usam a
  última edição antes da posse.
- **Fluxos** (saldo de empregos, crescimento do PIB): soma ou média do período, sem veredito.
- **Margem de erro**: nas pesquisas por amostra (PNAD), variações dentro do intervalo de 95% contam
  como estáveis.
- **Estados × Brasil**: compara o progresso relativo — quanto do "problema" inicial cada um reduziu —
  para não punir quem já estava perto do ideal.
- **Preliminares** (SIM do último ano, por exemplo) aparecem marcados e ficam fora da contagem.
- **Governos interinos e intervenções** não são avaliados; afastamentos curtos ficam dentro do mandato
  do titular. Gestão = mesma pessoa no mesmo mandato eleitoral.

## Como a auditoria funciona

1. Cada resposta das fontes oficiais é salva sem alteração em `dados/brutos/<fonte>/<sha256>.<ext>`.
   O nome do arquivo é o próprio hash: se a fonte não mudou, nada novo é gravado.
2. `dados/proveniencia.csv` registra cada download: data, URL, hash e se o conteúdo era novo.
3. `dados/indicadores.csv` é a tabela consolidada. Cada linha traz o hash do arquivo de origem e a URL.
4. `dados/mandatos.csv` lista quem governou cada UF e o país desde 2011, com a fonte de cada linha
   (TSE para os eleitos; Senado, governos estaduais e listas públicas para substituições).
   `etl/checar_mandatos.py` garante que não há buraco nem sobreposição.
5. Tudo fica em git. O histórico mostra quando cada número entrou ou foi revisto pela fonte (o IBGE,
   por exemplo, reajusta toda a série de rendimento a cada divulgação).

Para refazer um número: pegue o `sha256` da linha em `indicadores.csv`, abra o arquivo em
`dados/brutos/` e rode o coletor correspondente em `etl/fontes/`.

## Leitura responsável

- **Defasagem**: o valor é ligado ao período de referência, não à data de publicação. Um dado
  publicado em 2027 sobre 2026 conta para quem governava em 2026.
- **Responsabilidade dividida**: saúde, educação e segurança dependem de União, estado e
  municípios. A coluna "diferença para o Brasil" desconta o movimento nacional, mas não prova causa.
- **Primeiro ano**: quem assume governa o primeiro ano com o orçamento aprovado pelo antecessor.
- **Amostra**: indicadores da PNAD têm margem de erro maior em estados pequenos. Variações pequenas
  podem ser ruído.

## Rodar localmente

```bash
pip install -r requirements.txt
python -m etl.rodar            # coleta tudo e gera site/dados.json
python -m etl.rodar ibge       # só uma fonte
python -m etl.rodar --so-site  # só regera o site a partir do que já foi coletado
python3 -m http.server 8765 -d site
```

Para os links de auditoria funcionarem localmente: `ln -s ../dados site/dados`.

## Atualização automática

`.github/workflows/atualizar.yml` roda toda segunda às 06:00 (horário de Brasília) e também pelo botão
"Run workflow" no GitHub. Ele coleta, grava no repositório o que mudou e publica no GitHub Pages. Se
uma fonte estiver fora do ar, os dados dela da última coleta boa são mantidos e a falha aparece na aba
"Fontes e auditoria".

**Manutenção manual:** quando houver troca de governante (renúncia, cassação, posse), acrescente a
linha em `dados/mandatos.csv` com a fonte. O push já republica o site.

## Acrescentar um indicador

Crie `etl/fontes/<nome>.py` com duas funções:

- `coletar()` devolve linhas `{indicador, uf, periodo, inicio, fim, valor, sha256, url}`, baixando
  sempre por `etl.comum.baixar` (que guarda o bruto e registra a procedência).
- `catalogo()` devolve `{id: {nome, unidade, melhor ("menor"|"maior"), area, freq, descricao, origem, link}}`.

Depois acrescente o nome em `FONTES` em `etl/rodar.py`.
