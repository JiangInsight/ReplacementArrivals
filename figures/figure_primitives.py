from pathlib import Path
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon, FancyArrowPatch

plt.rcParams.update({'font.family':'Times New Roman','font.size':8.2,'mathtext.fontset':'stix','pdf.fonttype':42})
BLACK='#222222'
BLUE='#2166AC'
RED='#B33B32'
TEAL='#287C68'
GRAY='#777777'
LIGHT='#E9EEF3'

def canvas(width,height):
    fig,ax=plt.subplots(figsize=(width,height))
    fig.subplots_adjust(0,0,1,1)
    ax.set(xlim=(0,width),ylim=(0,height),aspect='equal')
    ax.axis('off')
    return fig,ax

def text(ax,x,y,s,size=8.2,ha='center',color=BLACK,weight='normal',va='center',**kw):
    return ax.text(x,y,s,fontsize=size,ha=ha,va=va,color=color,fontweight=weight,**kw)

def rect(ax,x,y,w,h,fill='white',edge=BLACK,lw=.65,ls='-'):
    p=Rectangle((x,y),w,h,facecolor=fill,edgecolor=edge,lw=lw,ls=ls)
    ax.add_patch(p);return p

def arrow(ax,a,b,color=BLACK,lw=.7,style='-',rad=0):
    p=FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=7,lw=lw,color=color,linestyle=style,connectionstyle=f'arc3,rad={rad}',shrinkA=1,shrinkB=1)
    ax.add_patch(p);return p

def route(ax,pts,color=BLACK,ls='-',lw=.7):
    ax.plot([p[0] for p in pts[:-1]],[p[1] for p in pts[:-1]],color=color,lw=lw,ls=ls)
    arrow(ax,pts[-2],pts[-1],color=color,lw=lw,style=ls)

def box(ax,x,y,w,h,s,size=8.2,fill='white',edge=BLACK):
    rect(ax,x,y,w,h,fill,edge);text(ax,x+w/2,y+h/2,s,size)

def node(ax,x,y,s,r=.085,fill='white',edge=BLACK,size=8.2):
    ax.add_patch(Circle((x,y),r,facecolor=fill,edgecolor=edge,lw=.75,zorder=5))
    text(ax,x,y,s,size,color=edge,zorder=6)

def table(ax,x,y,rows,widths,h=.18,colors=None,size=8.2,header=True):
    yy=y
    for i,row in enumerate(rows):
        xx=x
        for j,(cell,w) in enumerate(zip(row,widths)):
            fill=(colors or {}).get((i,j),'#F0F0F0' if header and i==0 else 'white')
            rect(ax,xx,yy-h,w,h,fill,edge='#7B7B7B',lw=.45)
            text(ax,xx+w/2,yy-h/2,cell,size)
            xx+=w
        yy-=h

def save(fig,path,preview):
    fig.canvas.draw()
    bbox=fig.bbox
    for ax in fig.axes:
        for t in ax.texts:
            r=t.get_window_extent(fig.canvas.get_renderer())
            assert r.x0>=bbox.x0-.5 and r.x1<=bbox.x1+.5 and r.y0>=bbox.y0-.5 and r.y1<=bbox.y1+.5,(str(path),t.get_text(),r)
    fig.savefig(path,metadata={'CreationDate':None,'ModDate':None})
    if preview:fig.savefig(preview,dpi=230)
    plt.close(fig)
