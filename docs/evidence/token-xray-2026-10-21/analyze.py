import json,glob,statistics as st,collections
P={'claude-sonnet-5-5':(2.0,10.0),'claude-opus-5-5':(4.0,20.0),'claude-haiku-5-5':(0.10,0.50)}
R=[json.loads(l) for f in sorted(glob.glob('calls_run*.jsonl')) for l in open(f)]
S=collections.defaultdict(lambda:collections.defaultdict(dict))
for r in R:
    d=S[r['scen']][r['way']].setdefault(r['run'],dict(proc=0,inp=0,out=0,think=0,calls=0,nocache=0,sess={}))
    d['proc']+=r['processed'];d['inp']+=r['input']+r['cache_write']+r['cache_read'];d['out']+=r['output'];d['think']+=r['thinking'] or 0;d['calls']+=1
    pi,po=P[r['model']];d['nocache']+=((r['input']+r['cache_write']+r['cache_read'])*pi+r['output']*po)/1e6
    d['sess'][r['sid']]=max(d['sess'].get(r['sid'],0),r['cost'])
    d['model']=r['model']
out={}
for sc,ways in S.items():
    o={}
    for w,runs in ways.items():
        runs={k:v for k,v in runs.items() if v['calls']==max(x['calls'] for x in runs.values())}
        vals=list(runs.values())
        for v in vals: v['cli']=sum(v['sess'].values())
        med=lambda k: st.median(v[k] for v in vals)
        o[w]=dict(n=len(vals),proc=med('proc'),inp=med('inp'),out=med('out'),think=med('think'),calls=vals[0]['calls'],cli=med('cli'),nocache=med('nocache'),
                  proc_range=[min(v['proc'] for v in vals),max(v['proc'] for v in vals)],model=vals[0]['model'])
    if 'wrong' in o and 'right' in o:
        o['x_tokens']=o['wrong']['proc']/o['right']['proc'];o['x_cli']=o['wrong']['cli']/o['right']['cli'];o['x_nocache']=o['wrong']['nocache']/o['right']['nocache']
    out[sc]=o
# per-turn series for longchat and trip (run medians)
ser={}
for sc in ['longchat','trip','reply']:
    for w in ['wrong','right']:
        by=collections.defaultdict(list)
        for r in R:
            if r['scen']==sc and r['way']==w: by[r['step']].append(r['processed'])
        ser[f'{sc}_{w}']=[st.median(by[k]) for k in sorted(by)]
json.dump(dict(summary=out,series=ser,runs=sorted({r['run'] for r in R}),ncalls=len(R),total_cli_cost=None),open('results.json','w'),indent=1)
for sc,o in out.items():
    if 'x_tokens' in o: print(f"{sc:10s} n={o['wrong']['n']}/{o['right']['n']} wrong {o['wrong']['proc']:>7.0f} right {o['right']['proc']:>6.0f} x{o['x_tokens']:.1f} | cli ${o['wrong']['cli']:.4f} vs ${o['right']['cli']:.4f} x{o['x_cli']:.1f} | nocache x{o['x_nocache']:.1f} | out {o['wrong']['out']:.0f}/{o['right']['out']:.0f} think {o['wrong']['think']:.0f}/{o['right']['think']:.0f}")
print(ser)
