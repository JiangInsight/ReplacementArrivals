import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
REVISION = 'e56c3ddb2b665455fb16aacca1044b99a62850f0'
SOURCE = 'https://gitlab.com/tgpublic/tglib.git'


def check(folder, manifest):
    for name, expected in manifest.items():
        path = folder/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError('TGLib source differs from the pinned release: ' + str(path))


def main():
    manifest = json.loads((ROOT/'dependencies/tglib-source-sha256.json').read_text())
    parent = (ROOT/'vendor').resolve()
    destination = parent/'tglib'
    if destination.exists():
        check(destination,manifest)
        print('TGLib:',REVISION,len(manifest),'verified source files')
        return
    parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='fetch-tglib-',dir=parent) as temporary:
        checkout = Path(temporary).resolve()/'source'
        subprocess.run(['git','init','-q',str(checkout)],check=True)
        subprocess.run(['git','-C',str(checkout),'config','core.autocrlf','true'],check=True)
        subprocess.run(['git','-C',str(checkout),'remote','add','origin',SOURCE],check=True)
        subprocess.run(['git','-C',str(checkout),'fetch','--depth','1','origin',REVISION],check=True)
        subprocess.run(['git','-C',str(checkout),'checkout','--detach',REVISION],check=True)
        actual = subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True).strip()
        if actual != REVISION:
            raise RuntimeError('Unexpected dependency revision')
        check(checkout,manifest)
        if not checkout.is_relative_to(parent) or destination.parent != parent:
            raise RuntimeError('Dependency path escaped its destination')
        shutil.move(str(checkout),str(destination))
    print('TGLib:',REVISION,len(manifest),'downloaded and verified source files')


if __name__ == '__main__':
    main()
