import argparse
import csv
import hashlib
import importlib
import json
import os
from pathlib import Path
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
GRAPHS = 'otc college email math ubuntu higgs coin comment flight'.split()
METHODS = 'tglib incident calendar decremental repair mix dag equations allpairs global'.split()


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def configure(work):
    work = work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    cache = work / 'cache'
    cache.mkdir(exist_ok=True)
    os.environ['PAPER3_WORKSPACE'] = str(work)
    os.environ['PAPER3_CACHE'] = str(cache)
    sys.path.insert(0, str(ROOT / 'study'))
    sys.path.insert(0, str(ROOT / 'study/expansion'))
    return work, cache


def bind(cache):
    names = {'study': 'study', 'expanded': 'study', 'release':'study','component':'study','dom':'study','census': 'census',
             'all-events': 'census', 'timetable': 'timetable', 'batch': 'batch'}
    for target, source in names.items():
        src = ROOT / 'build' / (source + '.exe')
        if not src.is_file():
            raise FileNotFoundError('Run build.cmd first: ' + str(src))
        dest = cache / (target + '.exe')
        if dest.exists() and digest(dest) != digest(src):
            raise ValueError('Executable changed; choose a fresh --work directory: ' + str(dest))
        if not dest.exists():
            shutil.copy2(src, dest)


def prepare(graphs):
    import prepare as p
    import workloads as w
    for graph in graphs:
        if not (p.BASE / 'results/full/inputs' / (graph + '.json')).exists():
            p.prepare(graph)
        spec = json.loads((p.BASE / 'results/full/inputs' / (graph + '.json')).read_text())
        if digest(p.CACHE / (graph + '.bin')) != spec['packed_sha256']:
            raise ValueError('Packed input differs from manifest: ' + graph)
        frozen_input = json.loads((ROOT/'reference/inputs'/(graph+'.json')).read_text())
        if spec['packed_sha256'] != frozen_input['packed_sha256']:
            raise ValueError('Preprocessing differs from archived packed input: ' + graph)
        w.make(graph)
        if graph in ('math', 'coin', 'flight'):
            w.make(graph, extended=True)
        for cohort in range(4):
            generated = p.BASE / 'results/full/workloads' / f'{graph}-{cohort}.txt'
            frozen = ROOT / 'reference/workloads' / generated.name
            if frozen.exists() and generated.read_bytes() != frozen.read_bytes():
                raise ValueError('Workload differs from the published seed: ' + str(generated))
        print('verified input and four seeded workloads:', graph, flush=True)


def oracle(graph, cohort, cache, work):
    query = work / 'results/full/workloads' / f'{graph}-{cohort}.txt'
    spec = json.loads(query.with_suffix('.json').read_text())
    ref = cache / 'answers' / f'{graph}-{cohort}-{digest(query)[:16]}.rows'
    if not ref.exists():
        ref.parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as temporary:
            stem = Path(temporary) / 'oracle'
            subprocess.run([cache/'study.exe', cache/(graph+'.bin'), str(spec['vertices']),
                            str(spec['source']), str(spec['release_row']), query, 'scan', stem,
                            Path(temporary)/'metrics.json'], check=True)
            shutil.copy2(stem.with_suffix('.rows'), ref)
    with (ROOT / 'data/session-space.csv').open(newline='') as stream:
        recorded = [r for r in csv.DictReader(stream)
                    if r['graph'] == graph and int(r['cohort']) == cohort]
    if recorded and digest(query) == recorded[0]['query_sha256']:
        if digest(ref) != recorded[0]['answer_sha256']:
            raise ValueError('Chronological replay differs from archived answers: ' + graph)
    return spec, query, ref


def correctness(cache, work):
    import audit_native as a
    a.METHODS = tuple('scan tglib incident calendar decremental repair dag equations mix '
                      'without-explicit without-direct without-catalog without-uniform '
                      'without-prune without-links'.split())
    for suite in ('base', 'cascade', 'component', 'dom'):
        print('checking', suite, flush=True)
        result = a.execute(cache / 'study.exe', suite)
        save(work/'checks'/f'{suite}.json', result)
        print(suite, result['native_query_comparisons'], 'checked query answers', flush=True)
    import timetables
    timetables.exact()
    subprocess.run([sys.executable, ROOT/'run_example.py'], check=True)


def census(graphs, cache, work, cohorts=(0, 2)):
    import numpy as np
    for graph in graphs:
        data = np.memmap(cache/(graph+'.bin'), dtype='<i4', mode='r').reshape(-1, 3)
        for cohort in cohorts:
            spec, _, _ = oracle(graph, cohort, cache, work)
            for label, end in [('mid', len(data)//2), ('end', len(data)-1)]:
                target = cache/'census-answers'/f'{graph}-{cohort}-{label}.rows'
                target.parent.mkdir(exist_ok=True)
                identity = {'input': digest(cache/(graph+'.bin')), 'source': spec['source'],
                            'end_record': end, 'binary': digest(cache/'census.exe')}
                record = work/'results/census'/f'{graph}-{cohort}-{label}.json'
                if record.exists():
                    prior = json.loads(record.read_text())
                    if prior['identity'] != identity or digest(target) != prior['answer_sha256']:
                        raise ValueError('Stale census: ' + str(record))
                    continue
                reports = {}
                with tempfile.TemporaryDirectory(dir=cache) as temporary:
                    wire = Path(temporary)/'answers.rows'
                    expected = None
                    for method in ('mix', 'repair'):
                        cmd = [cache/'census.exe', cache/(graph+'.bin'), str(spec['vertices']),
                               str(spec['source']), str(end), method, wire]
                        start = time.perf_counter()
                        report = json.loads(subprocess.check_output(cmd, text=True))
                        report['wall_s'] = time.perf_counter()-start
                        actual = digest(wire)
                        if expected is not None and actual != expected:
                            raise ValueError('Census mismatch: ' + graph)
                        expected = actual
                        reports[method] = report
                        save(work/'results/full/census'/f'{graph}-{cohort}-{label}-{method}.json',
                             dict(report, graph=graph, cohort=cohort, source=spec['source'], method=method,
                                  sha256=actual, status='complete', identity=identity))
                    shutil.copy2(wire, target)
                save(record, {'identity': identity, 'answer_sha256': expected, 'methods': reports})
                print('census', graph, cohort, label, reports['mix']['eligible'], flush=True)


def reporters(graphs, cache, work, repeats, conditioned=False):
    for graph in graphs:
        for cohort in ([0] if conditioned else range(4)):
            if conditioned:
                query = work/'results/expansion/workloads'/f'positive-{graph}.txt'
                spec = json.loads(query.with_suffix('.json').read_text())
                ref = cache/'expansion-answers'/f'positive-{graph}.rows'
            else:
                spec, query, ref = oracle(graph, cohort, cache, work)
            for rep in range(repeats):
                arms = ['mixed', 'point']
                random.Random(f'reporters/{graph}/{cohort}/{rep}').shuffle(arms)
                for mode in arms:
                    dest = work/'results/reporters'/f'{graph}-{cohort}'/f'{rep}-{mode}.json'
                    if conditioned:
                        dest = work/'results/reporters-conditioned'/graph/f'{rep}-{mode}.json'
                    identity = dict(input_sha256=digest(cache/(graph+'.bin')),query_sha256=digest(query),
                                    answer_sha256=digest(ref),binary_sha256=digest(ROOT/'build/arrivals.exe'))
                    if dest.exists():
                        recorded = json.loads(dest.read_text())
                        if any(recorded.get(k) != v for k,v in identity.items()):
                            raise ValueError('Stale reporter record: ' + str(dest))
                        continue
                    with tempfile.TemporaryDirectory(dir=cache) as temporary:
                        wire = Path(temporary)/'answers.rows'
                        cmd = [ROOT/'build/arrivals.exe', cache/(graph+'.bin'), str(spec['vertices']),
                               str(spec['source']), str(spec['release_row']), query, wire, mode]
                        start = time.perf_counter()
                        count, rows, size, build, service = subprocess.check_output(cmd, text=True).split()
                        elapsed = time.perf_counter()-start
                        if digest(wire) != digest(ref):
                            raise ValueError('Independent reporter differs: ' + graph + '/' + mode)
                    save(dest, dict(graph=graph, cohort=cohort, rep=rep, method=mode, status='complete',
                                    requests=int(count), rows=int(rows), index_bytes=int(size),
                                    build_s=float(build), service_s=float(service), wall_s=elapsed,
                                    **identity))


def benchmark(graphs, cache, work, suite, repeats, fixtures=None):
    import run as r
    if suite in ('direct', 'ablation', 'conditioned', 'scale', 'size', 'sources'):
        import experiment as x
        x.EXSHA = digest(x.EX)
        original_run = x.run
        def run(*args, **kwargs):
            kwargs.setdefault('repeats', repeats)
            return original_run(*args, **kwargs)
        x.run = run
        x.G = graphs
        for graph in graphs:
            for cohort in range(4):
                oracle(graph, cohort, cache, work)
        if suite in ('conditioned', 'size'):
            census(graphs, cache, work, cohorts=(0,))
        if suite == 'scale':
            for graph in graphs:
                for axis in ('contacts', 'vertices'):
                    x.scale(graph, axis)
        elif suite == 'size':
            import output_size
            output_size.main()
        elif suite == 'sources':
            if set(graphs) != {'college', 'email', 'math'}:
                raise ValueError('Source variation uses --graphs college email math')
            import sources
            sources.main()
        else:
            for graph in graphs:
                x.contact(graph, suite)
        return
    if suite in ('reporters', 'reporters-conditioned'):
        return reporters(graphs, cache, work, repeats, suite.endswith('conditioned'))
    if suite == 'long':
        if any(g not in ('math', 'coin', 'flight') for g in graphs):
            raise ValueError('Long sessions use math, coin, flight')
        cohorts, methods = (4, 5, 6), ['mix', 'repair', 'allpairs']
    elif suite == 'constructors':
        cohorts, methods = range(4), ['mix', 'dom', 'domfull']
    elif suite == 'synthetic':
        import stress
        (work/'results/full/inputs').mkdir(parents=True, exist_ok=True)
        (work/'results/full/workloads').mkdir(parents=True, exist_ok=True)
        graphs = stress.fixtures()
        if fixtures:
            if any(g not in graphs for g in fixtures):
                raise ValueError('Unknown synthetic fixture')
            graphs = fixtures
        cohorts, methods = (0,), ['mix', 'global', 'allpairs', 'adaptive', 'flatpairs', 'repair', 'dag',
                                 *('without-'+x for x in ('explicit','direct','catalog','uniform','prune','links'))]
    else:
        cohorts, methods = range(4), METHODS
    with tempfile.TemporaryDirectory(dir=cache) as temporary:
        for graph in graphs:
            for cohort in cohorts:
                oracle(graph, cohort, cache, work)
                for rep in range(repeats):
                    arms = methods[:]
                    random.Random(f'temporal/711/{graph}/{cohort}/{rep}').shuffle(arms)
                    for method in arms:
                        r.trial(graph, cohort, rep, method, cache/'study.exe', digest(cache/'study.exe'), Path(temporary))
                if suite == 'sessions':
                    spec, query, ref = oracle(graph, cohort, cache, work)
                    wire = Path(temporary)/'batch.rows'
                    start = time.perf_counter()
                    stdout = subprocess.check_output([cache/'batch.exe', cache/(graph+'.bin'),
                        str(spec['vertices']), str(spec['source']), str(spec['release_row']), query, wire], text=True)
                    elapsed = time.perf_counter()-start
                    if digest(wire) != digest(ref):
                        raise ValueError('Offline batch mismatch')
                    save(work/'results/batch'/f'{graph}-{cohort}.json', dict(graph=graph, cohort=cohort,
                         status='complete', method='batch64', wall_s=elapsed, native_metrics=stdout,
                         answer_sha256=digest(ref), input_sha256=digest(cache/(graph+'.bin')),
                         query_sha256=digest(query), binary_sha256=digest(cache/'batch.exe')))


def cache_replay(graphs, cache, work, repeats, budgets):
    limits = {'256KiB': 2**18, '1MiB': 2**20, '4MiB': 2**22, '16MiB': 2**24, 'unlimited': 2**63-1}
    if any(g not in ('otc','college','email','math','higgs','ubuntu') for g in graphs):
        raise ValueError('Cache experiment uses otc college email math higgs ubuntu')
    if any(b not in limits for b in budgets):
        raise ValueError('Unknown retention budget')
    from experiment import unpack
    out = work/'results/cache'
    out.mkdir(parents=True, exist_ok=True)
    with ZipFile(ROOT/'reference/source-cache/schedules.zip') as archive:
        for graph in graphs:
            streams, specifications, queries = [], [], []
            for cohort in range(4):
                spec, query, ref = oracle(graph, cohort, cache, work)
                specifications.append(spec)
                queries.append(query.read_text().splitlines())
                streams.append(list(unpack(ref.read_bytes())))
            for order in ('grouped','shuffled'):
                schedule = out/f'{graph}-{order}.txt'
                schedule.write_bytes(archive.read(schedule.name))
                lines = schedule.read_text().splitlines()
                offset = 0
                for cohort, spec in enumerate(specifications):
                    source, release, count, *sizes = map(int, lines[offset].split())
                    assert (source,release,count) == (spec['source'],spec['release_row'],128)
                    assert lines[offset+1:offset+129] == queries[cohort]
                    measured = list(map(int, subprocess.check_output([ROOT/'build/cache_sizes.exe',
                        cache/(graph+'.bin'), str(spec['vertices']), str(source), str(release)], text=True).split()))
                    if measured != sizes:
                        raise ValueError('Retained layout differs from archived schedule: ' + graph)
                    offset += 129
                expected = hashlib.sha256()
                for line in lines[offset:]:
                    source, begin, count = map(int, line.split())
                    for answer in streams[source][begin:begin+count]:
                        expected.update(answer)
                identity = dict(input=digest(cache/(graph+'.bin')), schedule=digest(schedule),
                                answer=expected.hexdigest(), binary=digest(ROOT/'build/source_cache.exe'))
                for budget in budgets:
                    for rep in range(repeats):
                        arms = ['component','expanded','repair']
                        rot = rep % 3
                        for method in arms[rot:]+arms[:rot]:
                            dest = out/f'{graph}-{order}-{budget}-{rep}-{method}.json'
                            if dest.exists():
                                if json.loads(dest.read_text())['identity'] != identity:
                                    raise ValueError('Stale cache record: ' + str(dest))
                                continue
                            with tempfile.TemporaryDirectory(dir=cache) as temporary:
                                wire = Path(temporary)/'answers.rows'
                                with (cache/(graph+'.bin')).open('rb') as warm:
                                    while warm.read(4<<20):
                                        pass
                                start = time.perf_counter()
                                raw = subprocess.check_output([ROOT/'build/source_cache.exe',cache/(graph+'.bin'),
                                    str(specifications[0]['vertices']),schedule,str(limits[budget]),method,wire], text=True)
                                elapsed = time.perf_counter()-start
                                requests,hits,builds,evictions,peak,build,service = raw.split()
                                assert digest(wire) == identity['answer'] and int(requests) == 512
                                assert int(hits)+int(builds) == 32 and int(peak) <= limits[budget]
                                if budget == 'unlimited':
                                    assert int(builds) == 4
                            save(dest,dict(graph=graph,order=order,budget=budget,rep=rep,method=method,
                                status='complete',requests=int(requests),hits=int(hits),builds=int(builds),
                                evictions=int(evictions),peak_retained_bytes=int(peak),build_s=float(build),
                                service_s=float(service),wall_s=elapsed,identity=identity))
                print('cache', graph, order, 'verified', flush=True)


def summary(work):
    import pandas as pd
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    records = []
    for path in sorted((work/'results').rglob('*.json')):
        row = json.loads(path.read_text())
        if 'method' not in row or 'status' not in row:
            continue
        row = {k: v for k, v in row.items() if not isinstance(v, (dict, list))}
        row['record'] = str(path.relative_to(work))
        parts = path.relative_to(work/'results').parts
        fallback_suite = '/'.join(parts[:2]) if parts[0] == 'full' else parts[0]
        row['suite'] = row.get('group', row.get('suite', fallback_suite))
        row['workload'] = row.get('key', '/'.join(str(row.get(k,'')) for k in
                             ('graph','city','cohort','case','order','budget','deadline')))
        if 'key' in row:
            meta = work/'results/expansion/workloads'/(row['key']+'.json')
            if meta.exists():
                row['graph'] = json.loads(meta.read_text()).get('graph','')
        if 'service_s' not in row and 'query_s' in row:
            row['service_s'] = row['query_s'] + row.get('encode_s', 0)
        records.append(row)
    if not records:
        raise ValueError('No measured runs to summarize')
    out = work/'summary'
    out.mkdir(exist_ok=True)
    data = pd.DataFrame(records)
    data.to_csv(out/'runs.csv', index=False)
    ok = data[data.status == 'complete']
    fields = [f for f in ('wall_s','build_s','query_s','encode_s','service_s','index_bytes','peak_bytes','rows') if f in data]
    groups = ['suite','workload','method']
    stats = ok.groupby(groups)[fields].agg(['count', 'median', 'min', 'max'])
    stats.columns = ['_'.join(x) for x in stats.columns]
    stats.reset_index().to_csv(out/'medians-and-ranges.csv',index=False)
    plots = out/'plots'
    plots.mkdir(exist_ok=True)
    for (suite, workload), subset in ok.groupby(['suite','workload']):
        med = subset.groupby('method')['wall_s'].median().dropna().sort_values()
        if not len(med):
            continue
        fig, ax = plt.subplots(figsize=(max(6, len(med)*.5), 3.5))
        ax.bar(range(len(med)), med, color='#237D87')
        ax.set_xticks(range(len(med)), med.index, rotation=40, ha='right')
        ax.set_ylabel('Median process time (s)')
        ax.set_title(suite+' / '+workload)
        ax.set_yscale('log')
        fig.tight_layout()
        name = ''.join(c if c.isalnum() or c in '-_' else '-' for c in suite+'-'+workload)
        fig.savefig(plots/(name+'.pdf'))
        fig.savefig(plots/(name+'.png'), dpi=180)
        plt.close(fig)
    print(out, len(records), 'run records', flush=True)


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('action', choices=['build','prepare','check','benchmark','census','timetables','cache','summary'])
    cli.add_argument('--work', type=Path, default=ROOT/'.work')
    cli.add_argument('--graphs', nargs='+', default=['otc'])
    cli.add_argument('--suite', choices=['sessions','direct','conditioned','reporters','reporters-conditioned',
                     'constructors','ablation','scale','size','sources','synthetic','long'], default='direct')
    cli.add_argument('--repeats', type=int, default=3)
    cli.add_argument('--fixtures', nargs='+')
    cli.add_argument('--budgets', nargs='+', default=['256KiB','1MiB','4MiB','16MiB','unlimited'])
    cli.add_argument('--cities', nargs='+', default=['kuopio','berlin','paris','sydney','winnipeg','detroit','bordeaux'])
    args = cli.parse_args()
    if args.action == 'build':
        subprocess.run([ROOT/'build.cmd'], cwd=ROOT, check=True)
        return
    if args.repeats < 1:
        cli.error('--repeats must be positive')
    graphs = GRAPHS if args.graphs == ['all'] else args.graphs
    if any(g not in GRAPHS for g in graphs):
        cli.error('unknown graph; use all or ' + ' '.join(GRAPHS))
    work, cache = configure(args.work)
    if args.action == 'summary':
        return summary(work)
    bind(cache)
    if args.action == 'check':
        return correctness(cache, work)
    if args.action == 'timetables':
        import timetables as t
        t.CITIES.update({'sydney':'52dd19bb73678e55b84989d8a9158106','winnipeg':'85428d211b563c8ff18f78e040d034f7',
                         'detroit':'a82b8f0beaa8ef1c8200ed8feacc6a73','bordeaux':'8c81985c63773797960768f73530386b'})
        for city in args.cities:
            if city not in t.CITIES:
                cli.error('unknown city ' + city)
            t.prepare(city)
            t.run(city)
        return
    if args.suite != 'synthetic' or args.action != 'benchmark':
        prepare(graphs)
    if args.action == 'prepare':
        return
    if args.action == 'cache':
        return cache_replay(graphs, cache, work, args.repeats, args.budgets)
    if args.action == 'census':
        return census(graphs, cache, work)
    benchmark(graphs, cache, work, args.suite, args.repeats, args.fixtures)


if __name__ == '__main__':
    main()
