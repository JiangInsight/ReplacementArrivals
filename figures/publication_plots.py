from pathlib import Path
import argparse
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import NullLocator

HERE = Path(__file__).resolve().parent
TEAL, ORANGE, BLUE = '#087F8C', '#C36A32', '#526B98'
INK, GRID = '#263744', '#DDE4E8'


def style():
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8,
        'pdf.fonttype': 42, 'axes.labelsize': 8.3, 'axes.titlesize': 9,
        'axes.titleweight': 'bold', 'axes.linewidth': .6,
        'axes.spines.top': False, 'axes.spines.right': False,
        'axes.edgecolor': '#9CAAB3', 'text.color': INK,
        'axes.labelcolor': INK, 'xtick.color': INK, 'ytick.color': INK,
        'xtick.major.width': .6, 'ytick.major.width': .6,
        'legend.frameon': False, 'lines.linewidth': 1.4})


def save(fig, name, preview=None):
    fig.savefig(HERE / (name + '.pdf'), metadata={'CreationDate': None, 'ModDate': None})
    if preview:
        fig.savefig(Path(preview) / (name + '.png'), dpi=220)
    plt.close(fig)


def construction(results, preview=None):
    style()
    cells = pd.read_csv(results / 'full/summary/source-settings.csv')
    settings = pd.read_csv(results / 'expansion/settings.csv')
    medians = pd.read_csv(results / 'expansion/method-medians.csv')
    samples = settings[settings.group == 'scale'].merge(
        medians[medians.method == 'mix'][['key', 'build_s']], on='key')
    fig = plt.figure(figsize=(7.15, 2.28))
    grid = fig.add_gridspec(1, 3, width_ratios=[1.55, 1, 1],
        left=.075, right=.982, bottom=.235, top=.72, wspace=.39)
    axes = [fig.add_subplot(grid[0, j]) for j in range(3)]
    a = axes[0]
    for j in range(3):
        if j % 2 == 0:
            a.axvspan(j-.48, j+.48, facecolor='#F3F6F8', zorder=0)
    methods = [('frontier', 'Stream (ours)', 'o', TEAL),
               ('dom', 'Pruned DAG', 's', ORANGE),
               ('domfull', 'Full DAG', '^', BLUE)]
    for k, (method, label, marker, color) in enumerate(methods):
        for j, graph in enumerate(['coin', 'comment', 'flight']):
            z = cells[(cells.graph == graph) & (cells.method == method)].sort_values('cohort')
            assert z.cohort.tolist() == [0, 1, 2, 3]
            vals = z.build_s.to_numpy()
            x = j + (k-1)*.24
            a.vlines(x, vals.min(), vals.max(), color=color, lw=.8, alpha=.5, zorder=2)
            a.scatter(x + np.array([-.04, -.013, .013, .04]), vals,
                s=9, color=color, marker=marker, alpha=.48, linewidths=0, zorder=3)
            a.scatter([x], [np.median(vals)], s=31, color=color,
                marker=marker, edgecolor='white', linewidth=.65, zorder=4)
    a.set(yscale='log', ylim=(.06, 4.5), xlim=(-.5, 2.5), ylabel='Construction time (s)')
    a.set_xticks([0, 1, 2], ['Coin', 'Comment', 'Flight'])
    a.set_yticks([.1, .3, 1, 3], ['0.1', '0.3', '1', '3'])
    a.set_title('(a) Three constructors', loc='left', pad=7)
    a.legend(handles=[Line2D([], [], color=c, marker=m, ls='', markersize=4.5, label=l)
        for _, l, m, c in methods], loc='lower left', bbox_to_anchor=(-.08, 1.23),
        ncols=3, fontsize=7.1, handletextpad=.35, columnspacing=.8, borderaxespad=0)
    for ax, graph, title, ticks, labels, ylim in [
        (axes[1], 'math', '(b) MathOverflow', [.04, .1, .2, .5], ['.04', '.1', '.2', '.5'], (.002, .024)),
        (axes[2], 'coin', '(c) Coin', [1, 2, 5, 10, 20], ['1', '2', '5', '10', '20'], (.04, .9))]:
        for axis, marker, ls, color in [('contacts', 'o', '-', TEAL), ('vertices', 's', '--', ORANGE)]:
            z = samples[(samples.graph == graph) & (samples.axis == axis)].sort_values('target_pct')
            assert z.target_pct.tolist() == [20, 40, 60, 80, 100]
            ax.plot(z.events/1e6, z.build_s, marker=marker, ls=ls,
                color=color, mfc='white' if axis == 'vertices' else color,
                markersize=4, markeredgewidth=.9)
        ax.set(xscale='log', yscale='log', ylim=ylim, xlabel='Retained contacts (M)')
        ax.set_xticks(ticks, labels)
        if graph == 'math':
            ax.set_yticks([.003, .01, .02], ['.003', '.01', '.02'])
        else:
            ax.set_yticks([.05, .1, .3, .6], ['.05', '.1', '.3', '.6'])
        ax.set_title(title, loc='left', pad=7)
    fig.legend(handles=[Line2D([], [], color=TEAL, marker='o', ms=4, label='Contact samples'),
                        Line2D([], [], color=ORANGE, marker='s', mfc='white', ls='--', ms=4, label='Vertex samples')],
        loc='upper center', bbox_to_anchor=(.73, .985), ncols=2, fontsize=7.8,
        handlelength=1.7, columnspacing=1)
    for ax in axes:
        ax.grid(axis='y', color=GRID, linewidth=.55, zorder=0)
        ax.tick_params(length=2.5, pad=3)
        ax.xaxis.set_minor_locator(NullLocator())
        ax.yaxis.set_minor_locator(NullLocator())
    save(fig, 'eval-construction', preview)


def census(summary, preview=None):
    style()
    data = pd.read_csv(summary / 'all-withdrawals.csv')
    data = data[data.horizon == 'end'].copy()
    data['pct'] = 100 * data.positive / data.eligible
    graphs = ['otc', 'college', 'email', 'math', 'higgs', 'ubuntu', 'coin', 'comment', 'flight']
    names = ['Bitcoin OTC', 'CollegeMsg', 'email-Eu', 'MathOverflow', 'Higgs', 'Ask Ubuntu', 'Coin', 'Comment', 'Flight']
    fig = plt.figure(figsize=(7.15, 2.65))
    a = fig.add_axes([.155, .17, .315, .66])
    b = fig.add_axes([.625, .17, .315, .66])
    for ax, metric, title, limits, ticks, labels in [
        (a, 'pct', '(a) Withdrawals that delay anyone', (8e-7, 120), [1e-6, 1e-4, .01, 1, 100],
            [r'$10^{-6}$', r'$10^{-4}$', '0.01', '1', '100']),
        (b, 'max_rows', '(b) Largest affected recipient set', (.65, 3e5), [1, 10, 100, 1000, 10000, 100000],
            ['1', '10', '100', '1k', '10k', '100k'])]:
        for j, graph in enumerate(graphs):
            if j % 2 == 0:
                ax.axhspan(j-.46, j+.46, color='#F1F5F7', zorder=0)
            z = data[data.graph == graph].set_index('cohort')
            assert sorted(z.index) == [0, 2]
            x, y = float(z.loc[0, metric]), float(z.loc[2, metric])
            ax.plot([x, y], [j-.12, j+.12], color='#A6B3BC', lw=.8, zorder=2)
            ax.scatter([x], [j-.12], marker='o', color=TEAL, edgecolor='white', lw=.45, s=23, zorder=3)
            ax.scatter([y], [j+.12], marker='D', color=ORANGE, edgecolor='white', lw=.4, s=19, zorder=3)
        ax.set(xscale='log', xlim=limits, ylim=(8.6, -.6))
        ax.set_xticks(ticks, labels)
        ax.set_yticks(range(9), names if ax is a else [])
        ax.tick_params(axis='y', length=0, pad=7, labelsize=8.2)
        ax.tick_params(axis='x', length=2.5, pad=3)
        ax.xaxis.set_minor_locator(NullLocator())
        ax.spines['left'].set_visible(False)
        ax.set_title(title, fontsize=8.8, loc='left', pad=10)
        ax.grid(axis='x', color=GRID, lw=.5, zorder=0)
    a.set_xlabel('Share of eligible withdrawals (%)', labelpad=4)
    b.set_xlabel('Number of recipients', labelpad=4)
    fig.legend(handles=[Line2D([], [], marker='o', ls='', color=TEAL, label='Most active source', markersize=5),
                        Line2D([], [], marker='D', ls='', color=ORANGE, label='Lower-quartile source', markersize=4.5)],
        loc='upper center', bbox_to_anchor=(.55, 1.02), ncols=2, fontsize=8.4,
        handletextpad=.4, columnspacing=2.1)
    save(fig, 'eval-census', preview)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--preview', type=Path)
    opts = parser.parse_args()
    if opts.preview:
        opts.preview.mkdir(parents=True, exist_ok=True)
    construction(opts.results, opts.preview)
    census(opts.results / 'full/summary', opts.preview)
