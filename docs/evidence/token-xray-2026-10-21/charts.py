import json,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge,Rectangle,FancyBboxPatch
d=json.load(open('exp/results.json'));S=d['summary'];ser=d['series']
ORDER=[('trip','Plan a family trip','Drip-feed details\nover 6 messages','One complete\nmessage'),
('reply','Reply to an unhappy customer','Vague ask +\n3 "fix it" rounds','One clear brief'),
('doc','Long document question','Paste the whole\n30-page-style terms','Paste only the\nrelevant section'),
('suppliers','Compare 3 supplier offers','"Tell me everything",\nthen "summarise"','Ask for the short\ntable directly'),
('formula','Fix a spreadsheet formula','Biggest model,\nmaximum thinking','Small model,\nlow effort'),
('longchat','10 small tasks in one day','All 10 in one\nnever-ending chat','A fresh chat\nper task')]
RED='#c0392b';GRN='#27ae60';GRY='#555'
plt.rcParams.update({'font.size':13,'font.family':'DejaVu Sans'})
FOOT='Real measurements, 21 Oct 2026: Claude Sonnet 5.5 via Claude Code CLI (formula: Opus 5.5 vs Haiku 5.5), median of 3 runs. Tokens = all input + output tokens.'
# 1 bars
fig,ax=plt.subplots(figsize=(13,7.5))
y=range(len(ORDER))
for i,(k,t,w,r) in enumerate(ORDER):
    a=S[k]['wrong']['proc'];b=S[k]['right']['proc']
    ax.barh(i+0.2,a,0.38,color=RED);ax.barh(i-0.2,b,0.38,color=GRN)
    ax.text(a+150,i+0.2,f"{a:,.0f}",va='center',color=RED,fontsize=12)
    ax.text(b+150,i-0.2,f"{b:,.0f}",va='center',color=GRN,fontsize=12)
    ax.text(19500,i,f"{S[k]['x_tokens']:.1f}x",va='center',ha='right',fontsize=20,fontweight='bold',color=GRY)
ax.set_yticks(list(y));ax.set_yticklabels([o[1] for o in ORDER],fontsize=14);ax.invert_yaxis()
ax.set_xlim(0,19800);ax.set_xticks([])
from matplotlib.patches import Patch;ax.legend(handles=[Patch(color=RED,label='Wrong way'),Patch(color=GRN,label='Right way')],loc='upper center',bbox_to_anchor=(0.5,-0.08),ncol=2,fontsize=13,frameon=False)
for s in ['top','right']: ax.spines[s].set_visible(False)
ax.set_title('Same answer, more tokens (tokens used per task)',fontsize=20,fontweight='bold',loc='left')
fig.text(0.01,0.01,FOOT,fontsize=9,color=GRY);plt.tight_layout(rect=(0,0.03,1,1));plt.savefig('1_wrong_vs_right_tokens.png',dpi=150);plt.close()
# 2 growing chat
w=ser['longchat_wrong'];r=ser['longchat_right'];n=len(w)
fig,(a1,a2)=plt.subplots(1,2,figsize=(14,6.2))
x=range(1,n+1)
a1.bar([i-0.2 for i in x],w,0.4,color=RED,label='One never-ending chat');a1.bar([i+0.2 for i in x],r,0.4,color=GRN,label='Fresh chat per task')
a1.set_xticks(list(x));a1.set_xlabel('Task number (same 10 small tasks)');a1.set_ylabel('Tokens for this one message')
a1.set_title('Each new message carries the whole chat',fontweight='bold',loc='left');a1.legend(fontsize=11)
import itertools
cw=list(itertools.accumulate(w));cr=list(itertools.accumulate(r))
# projection: linear fit of per-turn growth (estimate)
g=(w[-1]-w[0])/(n-1);base=sum(r)/n
N=40;pw=[w[0]+g*k for k in range(N)];pc=list(itertools.accumulate(pw));pr=[base*(k+1) for k in range(N)]
a2.plot(range(1,N+1),pc,'--',color=RED,alpha=.5,label='One chat (estimate beyond 10)');a2.plot(range(1,N+1),pr,'--',color=GRN,alpha=.5,label='Fresh chats (estimate)')
a2.plot(list(x),cw,'o-',color=RED,lw=3,label='One chat (measured)');a2.plot(list(x),cr,'o-',color=GRN,lw=3,label='Fresh chats (measured)')
a2.annotate(f"10 tasks: {cw[-1]/cr[-1]:.1f}x",(10,cw[-1]),(12,cw[-1]+12000),arrowprops=dict(arrowstyle='->'),fontsize=13,fontweight='bold')
a2.annotate(f"40 tasks: about {pc[-1]/pr[-1]:.0f}x (estimate)",(N,pc[-1]),(15,pc[-1]*0.9),arrowprops=dict(arrowstyle='->'),fontsize=13,fontweight='bold')
a2.set_xlabel('Number of tasks done');a2.set_ylabel('Total tokens so far');a2.set_title('The bill grows faster and faster',fontweight='bold',loc='left');a2.legend(fontsize=10,loc='center left')
for a in(a1,a2):
    for s in ['top','right']: a.spines[s].set_visible(False)
fig.text(0.01,0.01,'Tasks 1-10 measured (median of 3 runs, Claude Sonnet 5.5). Tasks 11-40: straight-line projection of the measured growth per message, an estimate, not measured.',fontsize=9,color=GRY)
plt.tight_layout(rect=(0,0.04,1,1));plt.savefig('2_growing_chat.png',dpi=150);plt.close()
# 3 headline
TW=sum(S[k]['wrong']['proc'] for k,*_ in ORDER);TR=sum(S[k]['right']['proc'] for k,*_ in ORDER)
CW=sum(S[k]['wrong']['nocache'] for k,*_ in ORDER);CR=sum(S[k]['right']['nocache'] for k,*_ in ORDER)
fig=plt.figure(figsize=(12,6.75));fig.patch.set_facecolor('#1f2d3d');ax=fig.add_axes([0,0,1,1]);ax.axis('off')
ax.text(0.5,0.84,'Same answers.',ha='center',fontsize=44,color='white',fontweight='bold')
ax.text(0.5,0.58,f'{TW/TR:.1f}x the tokens.',ha='center',fontsize=72,color='#ff6b5b',fontweight='bold')
ax.text(0.5,0.42,f'{CW/CR:.1f}x the cost.',ha='center',fontsize=48,color='#ffb35b',fontweight='bold')
ax.text(0.5,0.27,f'6 everyday tasks done the wrong way: {TW:,.0f} tokens.  Done the right way: {TR:,.0f} tokens.',ha='center',fontsize=16,color='white')
ax.text(0.5,0.06,'Measured live on 21 Oct 2026 with Claude (median of 3 runs). Cost at Anthropic list prices without caching: claude.com/pricing',ha='center',fontsize=11,color='#aab')
plt.savefig('3_headline.png',dpi=150,facecolor=fig.get_facecolor());plt.close()
# 4 fuel gauges: share of a fixed allowance (illustrative: right-way total = 1 'tank' quarter)
fig,axs=plt.subplots(1,2,figsize=(13,6.2))
for ax,(lab,val,col) in zip(axs,[('Wrong way',TW,RED),('Right way',TR,GRN)]):
    ax.set_aspect('equal');ax.axis('off');ax.set_xlim(-1.2,1.2);ax.set_ylim(-0.5,1.25)
    frac=val/TW  # wrong way = full tank used
    ax.add_patch(Wedge((0,0),1,0,180,width=0.25,color='#ddd'))
    ax.add_patch(Wedge((0,0),1,180-180*frac,180,width=0.25,color=col))
    import math
    ang=math.radians(180-180*frac);ax.plot([0,0.75*math.cos(ang)],[0,0.75*math.sin(ang)],color='#222',lw=4);ax.add_patch(plt.Circle((0,0),0.06,color='#222'))
    ax.text(-1,-0.12,'E',fontsize=16,ha='center');ax.text(1,-0.12,'F',fontsize=16,ha='center')
    ax.text(0,-0.3,f'{lab}\n{val:,.0f} tokens used',ha='center',fontsize=17,fontweight='bold',color=col)
fig.suptitle('Your AI allowance is like a fuel tank: same 6 trips, very different fuel',fontsize=18,fontweight='bold')
fig.text(0.01,0.01,'Gauge shows tokens used out of the wrong-way total (wrong way = whole tank). Measured 21 Oct 2026, Claude Sonnet 5.5 (formula task Opus vs Haiku), median of 3 runs.',fontsize=9,color=GRY)
plt.savefig('4_fuel_gauge.png',dpi=150);plt.close()
# 5 receipt
def receipt(ax,title,way,col):
    ax.axis('off');ax.set_xlim(0,1);ax.set_ylim(0,1)
    ax.add_patch(FancyBboxPatch((0.03,0.02),0.94,0.95,boxstyle='round,pad=0.01',fc='#fffef6',ec='#bbb'))
    ax.text(0.5,0.91,title,ha='center',fontsize=17,fontweight='bold',family='monospace',color=col)
    ax.text(0.5,0.86,'- - - - - - - - - - - - - - - - - -',ha='center',family='monospace',color='#999')
    yy=0.79;tot=0;tt=0
    for k,t,*_ in ORDER:
        v=S[k][way];tot+=v['nocache'];tt+=v['proc']
        ax.text(0.07,yy,t,family='monospace',fontsize=11);ax.text(0.93,yy,f"{v['proc']:>7,.0f} tok",ha='right',family='monospace',fontsize=11);yy-=0.085
    ax.text(0.5,yy+0.02,'- - - - - - - - - - - - - - - - - -',ha='center',family='monospace',color='#999')
    ax.text(0.07,yy-0.05,'TOTAL TOKENS',family='monospace',fontsize=13,fontweight='bold');ax.text(0.93,yy-0.05,f'{tt:,.0f}',ha='right',family='monospace',fontsize=13,fontweight='bold')
    ax.text(0.07,yy-0.13,'COST (list price)',family='monospace',fontsize=13,fontweight='bold');ax.text(0.93,yy-0.13,f'${tot:.3f}',ha='right',family='monospace',fontsize=13,fontweight='bold',color=col)
    ax.text(0.07,yy-0.21,'x 20 tasks/day x 22 days',family='monospace',fontsize=11,color=GRY);ax.text(0.93,yy-0.21,f'${tot/6*20*22:.2f}*',ha='right',family='monospace',fontsize=12,color=GRY)
fig,axs=plt.subplots(1,2,figsize=(13,7.5))
receipt(axs[0],'RECEIPT: WRONG WAY','wrong',RED);receipt(axs[1],'RECEIPT: RIGHT WAY','right',GRN)
fig.text(0.01,0.01,'Tokens measured 21 Oct 2026 (Claude, median of 3 runs). Cost = Anthropic list price without caching (claude.com/pricing). *Monthly line is an estimate: average task cost x 20 tasks x 22 working days.',fontsize=9,color=GRY)
plt.tight_layout(rect=(0,0.03,1,1));plt.savefig('5_receipt.png',dpi=150);plt.close()
# 6 big model: cost bars
f=S['formula'];fig,ax=plt.subplots(figsize=(11,5.5))
ax.bar(['Biggest model, max thinking\n(Opus 5.5)','Small model, low effort\n(Haiku 5.5)'],[f['wrong']['nocache']*1000,f['right']['nocache']*1000],color=[RED,GRN])
ax.set_ylabel('Cost in tenths of a cent');ax.set_title(f"Same formula, {f['x_nocache']:.0f}x the cost: =IFERROR(SUM(B2:B10)/C1,0)",fontweight='bold',loc='left')
for i,v in enumerate([f['wrong'],f['right']]): ax.text(i,v['nocache']*1000,f"${v['nocache']:.5f}\n{v['out']:.0f} output tokens ({v['think']:.0f} hidden thinking)",ha='center',va='bottom',fontsize=12)
ax.set_ylim(0,f['wrong']['nocache']*1000*1.35)
for s in ['top','right']: ax.spines[s].set_visible(False)
fig.text(0.01,0.01,'Measured 21 Oct 2026, median of 3 runs, list prices without caching (claude.com/pricing). Both answers identical.',fontsize=9,color=GRY)
plt.tight_layout(rect=(0,0.04,1,1));plt.savefig('6_big_model_small_task.png',dpi=150);plt.close()
json.dump(dict(TW=TW,TR=TR,CW=CW,CR=CR,xt=TW/TR,xc=CW/CR,proj40=pc[-1]/pr[-1],proj40_w=pc[-1],proj40_r=pr[-1]),open('exp/headline.json','w'),indent=1)
print(TW,TR,TW/TR,CW,CR,CW/CR,pc[-1]/pr[-1])
