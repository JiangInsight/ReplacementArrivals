import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--work', type=Path, default=ROOT/'.work-validation')
    args = cli.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    logs = work/'validation-logs'
    logs.mkdir(exist_ok=True)
    commands = [[str(ROOT/'build.cmd')]]
    jobs = [('check', []), ('prepare', []),
            ('benchmark', ['--suite','sessions']), ('benchmark', ['--suite','direct']),
            ('benchmark', ['--suite','ablation']), ('benchmark', ['--suite','constructors']),
            ('benchmark', ['--suite','reporters']), ('census', []),
            ('benchmark', ['--suite','conditioned']), ('benchmark', ['--suite','reporters-conditioned']),
            ('cache', ['--budgets','1MiB','unlimited']), ('summary', [])]
    for action, extra in jobs:
        commands.append([sys.executable,str(ROOT/'reproduce.py'),action,'--work',str(work),
                         '--graphs','otc','--repeats','1',*extra])
    commands.extend([[str(ROOT/'build/bridge_isolation.exe')],
        [sys.executable,str(ROOT/'supplement/scheduled_control.py'),str(ROOT),str(work/'cache'),
         'build',str(work/'scheduled-exact.json')],
        [sys.executable,str(ROOT/'supplement/scheduled_control.py'),str(ROOT),str(work/'cache'),
         'exact',str(work/'scheduled-exact.json')]])
    report = dict(start_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  platform=platform.platform(),python=sys.version,commands=[],
                  scope='Fresh builds, exhaustive/random correctness, complete OTC input and all short comparison arms; other full logs and seven-city performance are not rerun.')
    destination = work/'validation.json'
    for step, command in enumerate(commands):
        print(step, ' '.join(command), flush=True)
        begin = time.perf_counter()
        result = subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        log = logs/f'{step:02d}.txt'
        log.write_text(result.stdout+result.stderr,encoding='utf-8')
        report['commands'].append(dict(command=command,returncode=result.returncode,
                                       seconds=time.perf_counter()-begin,log=str(log.relative_to(work))))
        report['passed'] = result.returncode == 0
        destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        if result.returncode:
            print(result.stdout+result.stderr)
            raise SystemExit(result.returncode)
    report['finish_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    report['correctness'] = {p.stem:json.loads(p.read_text())['native_query_comparisons']
                             for p in (work/'checks').glob('*.json')}
    report['sources'] = {}
    for directory in ('src','study','supplement'):
        for path in sorted((ROOT/directory).rglob('*')):
            if path.suffix in ('.py','.hpp','.cpp','.bat'):
                report['sources'][str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    report['input'] = json.loads((work/'results/full/inputs/otc.json').read_text())
    for name in ('reproduce.py','validate_release.py','plot_reference.py','fetch_dependencies.py','build.cmd','requirements.txt'):
        report['sources'][name] = hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    report['run_records'] = sum(1 for _ in (work/'results').rglob('*.json'))
    destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(destination, flush=True)


if __name__ == '__main__':
    main()
