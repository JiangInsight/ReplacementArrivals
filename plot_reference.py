import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'figures'))
import evaluation
import publication_plots

cli = argparse.ArgumentParser()
cli.add_argument('--reference', type=Path, default=ROOT/'reference')
cli.add_argument('--out', type=Path, default=ROOT/'.work/reference-plots')
args = cli.parse_args()
args.out.mkdir(parents=True,exist_ok=True)
evaluation.HERE = args.out
publication_plots.HERE = args.out
publication_plots.construction(args.reference,args.out)
publication_plots.census(args.reference/'full/summary',args.out)
evaluation.service(args.reference)
evaluation.clipping(args.reference)
print(args.out)
