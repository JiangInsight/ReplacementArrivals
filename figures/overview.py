from pathlib import Path
import argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon, FancyArrowPatch, FancyBboxPatch

plt.rcParams.update({'font.family':'Times New Roman','mathtext.fontset':'stix','font.size':8.5,'pdf.fonttype':42})
INK='#26323B'
BLUE='#24769E'
TEAL='#2E817B'
ORANGE='#BB7029'
PALEBLUE='#E8F2F8'
PALETEAL='#EAF4EF'
PALEORANGE='#FBF1E1'
GRAY='#76828A'

def txt(ax,x,y,s,size=8.5,ha='center',color=INK,weight='normal',va='center'):
    return ax.text(x,y,s,fontsize=size,ha=ha,va=va,color=color,fontweight=weight,zorder=8)

def line(ax,a,b,color=INK,lw=.8,ls='-'):
    ax.plot([a[0],b[0]],[a[1],b[1]],color=color,lw=lw,ls=ls,zorder=2)

def arrow(ax,a,b,color=INK,lw=.85,ls='-',rad=0):
    ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=8,lw=lw,color=color,linestyle=ls,connectionstyle=f'arc3,rad={rad}',shrinkA=1,shrinkB=1,zorder=5))

def route(ax,points,color=INK,lw=.8,ls='-'):
    for a,b in zip(points[:-2],points[1:-1]):line(ax,a,b,color,lw,ls)
    arrow(ax,points[-2],points[-1],color,lw,ls)

def rect(ax,x,y,w,h,fill='white',edge=GRAY,lw=.6):
    ax.add_patch(Rectangle((x,y),w,h,facecolor=fill,edgecolor=edge,lw=lw,zorder=3))

def panel(ax,x,y,w,h,title,fill,color):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.015,rounding_size=.065',facecolor=fill,edgecolor=color,lw=.65,zorder=0))
    txt(ax,x+w/2,y+h-.13,title,9.0,weight='bold',color=color)

def node(ax,x,y,label,r=.06,fill='white',edge=INK,size=8):
    ax.add_patch(Circle((x,y),r,facecolor=fill,edgecolor=edge,lw=.75,zorder=6))
    if label:txt(ax,x,y,label,size,color=edge)

def cells(ax,x,y,values,w=.23,h=.16,fill='white',size=8):
    for j,v in enumerate(values):
        rect(ax,x+j*w,y,w,h,fill=fill)
        txt(ax,x+(j+.5)*w,y+h/2,v,size)

def smalltree(ax,x,y,scale=1,fill=PALEBLUE):
    pts=[(x,y),(x-.22*scale,y-.26*scale),(x+.22*scale,y-.26*scale),(x-.34*scale,y-.50*scale),(x-.10*scale,y-.50*scale)]
    for a,b in [(0,1),(0,2),(1,3),(1,4)]:line(ax,pts[a],pts[b],lw=.65)
    for k,(xx,yy) in enumerate(pts):node(ax,xx,yy,'' if k else r'$\rho$',.047*scale,fill=fill,size=6.5)

def build(out,preview=False):
    fig,ax=plt.subplots(figsize=(7.15,3.0))
    fig.subplots_adjust(0,0,1,1);ax.set(xlim=(0,7.15),ylim=(0,3),aspect='equal');ax.axis('off')
    txt(ax,.08,2.92,'BUILD ONCE',9.2,ha='left',color=BLUE,weight='bold')
    txt(ax,2.0,2.92,r'Fixed source $s$, release $\tau$, horizon $T$',8.6,ha='left')
    panel(ax,.08,1.67,1.04,1.07,'Contact stream',PALEBLUE,BLUE)
    pts=[(.28,2.28),(.61,2.43),(.91,2.23),(.58,2.12)]
    for a,b in [(0,1),(1,2),(0,3),(3,2)]:arrow(ax,pts[a],pts[b],color=BLUE,lw=.65)
    for j,(x,y) in enumerate(pts):node(ax,x,y,'s' if j==0 else '',.052,edge=BLUE)
    arrow(ax,(.23,1.98),(.98,1.98),BLUE,lw=.6)
    for x,s in [(.40,r'$t_{\rm dep}$'),(.77,r'$t_{\rm arr}$')]:
        line(ax,(x,1.95),(x,2.01),BLUE,lw=.7);txt(ax,x,1.87,s,8.5)
    txt(ax,.60,1.73,r'$(e,u,v)$',8.3)
    arrow(ax,(1.14,2.20),(1.37,2.20),BLUE,lw=1.1)
    panel(ax,1.40,1.67,1.51,1.07,'Frozen-head scan',PALEBLUE,BLUE)
    for j,label in enumerate([r'$h_u$',r'$h_w$',r'$h_z$']):
        cells(ax,1.66+j*.32,2.17,[label],w=.26,h=.18,fill='white',size=8.5)
    txt(ax,2.15,2.46,'freeze at departure',8.3)
    for xx in [1.79,2.11,2.43]:arrow(ax,(xx,2.15),(2.11,2.06),BLUE,lw=.6)
    node(ax,2.11,1.98,'',.065,fill=PALEBLUE,edge=BLUE)
    txt(ax,2.15,1.79,'group arrivals: new / LCA',8.0)
    arrow(ax,(2.93,2.20),(3.16,2.20),TEAL,lw=1.1)
    panel(ax,3.19,1.67,1.56,1.07,'Dependencies',PALETEAL,TEAL)
    txt(ax,3.58,2.46,'event tree',8.1)
    smalltree(ax,3.59,2.30,.62,fill=PALETEAL)
    ax.plot([4.00,4.00,4.15,4.15,4.30,4.30,4.48],[2.32,2.23,2.23,2.14,2.14,2.05,2.05],lw=1,color=TEAL)
    arrow(ax,(3.96,2.01),(4.55,2.01),GRAY,lw=.5)
    txt(ax,4.27,2.46,r'$H_v:(t,d)$',8.1)
    arrow(ax,(3.59,1.97),(3.59,1.88),TEAL,lw=.65)
    cells(ax,3.30,1.71,[r'$\tau_1$',r'$\tau_2$',r'$\cdots$'],w=.24,h=.16,fill='white',size=8.1)
    txt(ax,4.34,1.79,'birth order',8.0)
    arrow(ax,(4.77,2.20),(5.00,2.20),ORANGE,lw=1.1)
    panel(ax,5.03,1.67,2.03,1.07,'One encoding per component',PALEORANGE,ORANGE)
    txt(ax,5.17,2.43,'Rows',8.3,ha='left');cells(ax,5.78,2.35,['v','birth','new'],w=.37,h=.16,size=8.0)
    txt(ax,5.17,2.18,'Direct',8.3,ha='left');cells(ax,5.78,2.10,[r'$t_1$',r'$t_2$',r'$\cdots$'],w=.37,h=.16,size=8.3)
    txt(ax,5.17,1.93,'Catalog',8.3,ha='left');cells(ax,5.78,1.85,[r'$(t,d)$',r'$(t,d)$'],w=.46,h=.16,size=8.0)
    txt(ax,6.05,1.755,r'byte score: $\min\{E_c,D_c,\widehat C_c\}$',8.0)
    arrow(ax,(6.04,1.65),(6.04,1.59),ORANGE,lw=.9)
    rect(ax,1.34,1.22,5.72,.37,fill='#F2F4F6',edge='#7E8C97',lw=.75)
    txt(ax,1.46,1.40,'RETAINED INDEX',8.4,ha='left',weight='bold')
    txt(ax,3.52,1.515,'event dictionary',8.1)
    cells(ax,2.89,1.265,['e'],w=.24,h=.18,size=8.4)
    arrow(ax,(3.17,1.355),(3.34,1.355),GRAY,lw=.6)
    cells(ax,3.40,1.265,['enc, off'],w=.70,h=.18,size=8.2)
    for j,(s,fc) in enumerate([(r'$c_1$: rows',PALEORANGE),(r'$c_2$: direct',PALEBLUE),(r'$c_3$: catalog',PALETEAL)]):
        rect(ax,4.24+j*.89,1.305,.77,.19,fill=fc)
        txt(ax,4.625+j*.89,1.40,s,8.0)
    txt(ax,.08,1.10,'QUERY',9.2,ha='left',color=TEAL,weight='bold')
    txt(ax,.48,.87,'independent',8.1)
    txt(ax,.48,.59,r'$(e,H)$',11)
    arrow(ax,(.83,.59),(1.28,.59),TEAL,lw=1)
    rect(ax,1.31,.39,.93,.42,fill=PALETEAL,edge=TEAL,lw=.75)
    txt(ax,1.775,.60,'Event lookup',8.5)
    route(ax,[(3.01,1.21),(3.01,1.16),(1.775,1.16),(1.775,.83)],TEAL,lw=.7)
    txt(ax,2.13,1.03,'read only',8.0)
    route(ax,[(1.775,.37),(1.775,.13),(2.24,.13)],GRAY,lw=.7)
    txt(ax,2.31,.13,r'miss: $\varnothing$',8.1,ha='left')
    ax.add_patch(FancyBboxPatch((2.72,.19),2.52,.92,boxstyle='round,pad=.015,rounding_size=.05',facecolor='#F7FAFA',edgecolor='#A3BAB8',lw=.6,zorder=0))
    route(ax,[(2.26,.60),(2.47,.60),(2.47,.85),(2.82,.85)],TEAL)
    route(ax,[(2.26,.60),(2.47,.60),(2.47,.39),(2.82,.39)],TEAL)
    txt(ax,2.35,.72,'hit',8.0,color=TEAL)
    cells(ax,2.87,.77,['v','birth','new'],w=.32,h=.17,size=8.0)
    txt(ax,3.35,1.00,r'Rows: births $\leq H$',8.1)
    for a,b in [((2.98,.53),(2.88,.30)),((2.98,.53),(3.10,.30)),((3.30,.50),(3.30,.29))]:
        line(ax,a,b,TEAL,lw=.65)
    for x,y in [(2.98,.53),(2.88,.30),(3.10,.30),(3.30,.50),(3.30,.29)]:
        rect(ax,x-.026,y-.026,.052,.052,fill=PALETEAL,edge=TEAL,lw=.75)
    txt(ax,3.50,.50,'Birth forest',8.1,ha='left')
    txt(ax,3.50,.31,r'$A(v)\leq H$',8.1,ha='left')
    txt(ax,4.62,.62,'Direct / catalog',8.0)
    arrow(ax,(4.05,.40),(4.34,.40),TEAL,lw=.8)
    txt(ax,4.77,.41,r'first depth $<d_x$',8.1)
    txt(ax,4.77,.26,r'time $t^{\prime}$',8.1)
    route(ax,[(3.85,.855),(4.12,.855),(4.12,.94),(5.59,.94),(5.59,.83)],TEAL)
    route(ax,[(5.28,.40),(5.30,.40),(5.30,.60),(5.34,.60)],TEAL)
    ax.add_patch(Polygon([(5.34,.60),(5.59,.82),(5.84,.60),(5.59,.38)],facecolor=PALETEAL,edgecolor=TEAL,lw=.75,zorder=5))
    txt(ax,5.59,.60,r'$t^{\prime}\leq H$',8.7)
    arrow(ax,(5.86,.60),(6.22,.60),TEAL,lw=.9)
    txt(ax,6.04,.86,r'on time: $t^{\prime}$',8.1)
    route(ax,[(5.59,.37),(5.59,.06),(6.24,.06),(6.24,.42)],GRAY,lw=.7)
    txt(ax,5.91,.32,'late or',8.0)
    txt(ax,5.91,.18,r'absent: $\bot$',8.0)
    cells(ax,6.28,.58,['v','old','new'],w=.25,h=.17,size=8.0)
    cells(ax,6.28,.41,[r'$\vdots$',r'$\vdots$',r'$\vdots$'],w=.25,h=.17,size=9)
    txt(ax,6.655,1.00,'Delayed recipients',8.2)
    txt(ax,6.65,.27,r'$(v,A(v),b_H(v))$',8.5)
    fig.canvas.draw();renderer=fig.canvas.get_renderer()
    for t in ax.texts:
        b=t.get_window_extent(renderer)
        assert b.x0>=-.5 and b.x1<=fig.bbox.width+.5 and b.y0>=-.5 and b.y1<=fig.bbox.height+.5,(t.get_text(),b)
    out.mkdir(parents=True,exist_ok=True)
    fig.savefig(out/'overview.pdf',metadata={'CreationDate':None,'ModDate':None})
    if preview:fig.savefig(out/'overview.png',dpi=240)
    plt.close(fig)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--out','--output-dir',dest='out',type=Path,default=Path(__file__).resolve().parent)
    p.add_argument('--preview',action='store_true')
    args=p.parse_args();build(args.out,args.preview)
