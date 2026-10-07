"""Confere dados/mandatos.csv: cada UF coberta de 2011 até hoje, sem buraco nem sobreposição,
um único governante em exercício, mandato eleitoral coerente e fonte em toda linha."""
import csv,datetime as dt,collections
R=list(csv.DictReader(open(__import__('pathlib').Path(__file__).resolve().parent.parent/'dados'/'mandatos.csv',encoding='utf-8')))
D=lambda s:dt.date.fromisoformat(s)
START,TODAY=D('2011-01-01'),D('2026-10-07')
by=collections.defaultdict(list)
for r in R: by[r['uf']].append(r)
errs=0
ufs=set(by)
exp={'BR','AC','AL','AM','AP','BA','CE','DF','ES','GO','MA','MG','MS','MT','PA','PB','PE','PI','PR','RJ','RN','RO','RR','RS','SC','SE','SP','TO'}
if ufs!=exp: print('UF set mismatch',ufs^exp); errs+=1
for uf,L in sorted(by.items()):
    L.sort(key=lambda r:r['inicio'])
    if D(L[0]['inicio'])!=START: print(uf,'start',L[0]['inicio']); errs+=1
    for a,b in zip(L,L[1:]):
        if not a['fim']: print(uf,'open row not last',a['nome']); errs+=1; continue
        if D(a['fim'])+dt.timedelta(1)!=D(b['inicio']): print(uf,'gap/overlap',a['nome'],a['fim'],b['nome'],b['inicio']); errs+=1
    for r in L:
        if r['fim'] and D(r['fim'])<D(r['inicio']): print(uf,'neg',r); errs+=1
        y=int(r['inicio'][:4]); s=2011+((y-2011)//4)*4
        if r['mandato_eleitoral']!=f'{s}-{s+3}': print('mandato',r); errs+=1
        if r['fim'] and D(r['fim'])>TODAY: print('future',r); errs+=1
        if r['tipo'] not in('eleito','vice_assumiu','interino','reeleito','eleito_indireto','interventor'): print('tipo',r);errs+=1
        if not r['fonte'].startswith('http'): print('fonte',r); errs+=1
    if L[-1]['fim']: print(uf,'last row closed',L[-1]['fim']); errs+=1
    if sum(1 for r in L if not r['fim'])!=1: print(uf,'open rows != 1'); errs+=1
print('rows',len(R),'ufs',len(by),'errors',errs)
raise SystemExit(1 if errs else 0)
