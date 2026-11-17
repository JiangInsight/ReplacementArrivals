



import argparse
import itertools
import json
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

HERE = Path(__file__).resolve().parent
GRAPHS = ("otc","college","email","math","higgs","ubuntu","coin","comment","flight")
NAMES = ("Bitcoin OTC","CollegeMsg","email-Eu","MathOverflow","Higgs","Ask Ubuntu","Coin","Comment","Flight")
COLORS = ("#14716d", "#92431b", "#353c68")
plt.rcParams.update({"font.size":8,"font.family":"DejaVu Sans","pdf.fonttype":42,
                     "axes.labelsize":8,"axes.titlesize":8,"axes.linewidth":0.6,
                     "axes.spines.top":False,"axes.spines.right":False,
                     "xtick.major.width":0.55,"ytick.major.width":0.55,
                     "legend.frameon":False,"lines.linewidth":1.2})

def finish(fig,name):
    fig.savefig(HERE/(name+".pdf"),metadata={"CreationDate":None,"ModDate":None})
    plt.close(fig)

def service(results):
    data=pd.read_csv(results/"expansion/method-medians.csv").set_index(["key","method"])
    fig,axes=plt.subplots(1,2,figsize=(3.37,2.35),sharey=True)
    fig.subplots_adjust(left=.196,right=.982,top=.82,bottom=.20,wspace=.22)
    for ax,metric,title in zip(axes,("service_s","wall_s"),("Report + encode","Whole process")):
        for i,(method,label,marker) in enumerate((("decremental","Decremental","o"),("repair","Local repair","^"))):
            ratios=np.array([data.loc[("positive-"+g,method),metric]/
                             data.loc[("positive-"+g,"mix"),metric] for g in GRAPHS])
            assert np.isfinite(ratios).all()
            lo=[];hi=[]
            for g in GRAPHS:
                def repeats(m):
                    raw=pd.read_csv(results/"expansion/processes.csv"); rr=raw[(raw.key=="positive-"+g)&(raw.method==m)&(raw.status=="complete")].to_dict("records"); assert len(rr)==3
                    return [r["wall_s"] if metric=="wall_s" else r["query_s"]+r["encode_s"] for r in rr]
                a,b=repeats(method),repeats("mix")
                lo.append(min(a)/max(b));hi.append(max(a)/min(b))
            ax.hlines(np.arange(len(GRAPHS))+(i-.5)*.29,lo,hi,color=COLORS[i],lw=.65,alpha=.8)
            ax.scatter(ratios,np.arange(len(GRAPHS))+(i-.5)*.29,color=COLORS[i],marker=marker,
                       s=13,label=label,zorder=3)
        ax.set_xscale("log",base=2)
        ax.set_xlim(.33,4.9);ax.set_xticks([.5,1,2,4],labels=["0.5","1","2","4"])
        ax.axvline(1,color="#515151",linestyle=":",lw=.9)
        ax.set_title(title,pad=3);ax.grid(axis="x",alpha=.16);ax.tick_params(length=2,pad=2)
    axes[0].set_yticks(range(len(GRAPHS)),["OTC","College","email-Eu","Math","Higgs","Ubuntu","Coin","Comment","Flight"])
    axes[0].set_ylim(8.5,-.5)
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,ncols=2,loc="upper center",bbox_to_anchor=(.56,1.01),
               borderpad=0,columnspacing=1.1,handlelength=1.0)
    fig.supxlabel("Baseline time / index time  (>1: index faster)",fontsize=8,y=.018)
    finish(fig,"eval-service")

def construction(results):
    from publication_plots import construction as draw_construction
    draw_construction(results)


def clipping(results):
    d=pd.read_csv(results/"expansion/output-size-deadline.csv")
    d["us"]=d.query_ns/d.requests/1000
    labels=("1","2-3","4-15","16-63","64-255","256+")
    fig,axes=plt.subplots(1,2,figsize=(3.37,2.42),sharey=True)
    fig.subplots_adjust(left=.15,right=.984,bottom=.26,top=.72,wspace=.12)
    for ax,graph in zip(axes,("higgs","coin")):
        for (mode,m,title,marker,style,color) in [
                ("at-contact","mix","Early, skip","o","-",COLORS[0]),
                ("at-contact","without-prune","Early, no skip","s","--",COLORS[1]),
                ("end","mix","Final, skip","^",":",COLORS[2]),
                ("end","without-prune","Final, no skip","d","-.","#353535")]:
            z=d[(d.key=="size-"+graph)&(d.method==m)&(d.deadline_mode==mode)]
            y=z.groupby("full_roster_bin").us.median().reindex(labels)
            assert np.isfinite(y).all()
            ax.plot(range(6),y,marker=marker,ls=style,color=color,markersize=3,label=title)
        ax.set_yscale("log")
        ax.set_yticks([.3,.5,1,2,4,6],labels=["0.3","0.5","1","2","4","6"])
        ax.set_xticks(range(6),["1","2","4","16","64","256"],rotation=45,ha="right")
        ax.set_title(graph.title(),pad=2);ax.grid(axis="y",alpha=.16);ax.tick_params(length=2,pad=2)
    axes[0].set_ylabel("Generation (µs/request)",labelpad=1)
    handles,names=axes[0].get_legend_handles_labels()
    fig.legend(handles,names,ncols=2,loc="upper center",bbox_to_anchor=(.53,.995),
               handlelength=1.1,columnspacing=.6,fontsize=7.8)
    fig.supxlabel("Full-deadline roster bin (lower endpoint)",fontsize=7.8,y=.015)
    finish(fig,"eval-deadlines")
