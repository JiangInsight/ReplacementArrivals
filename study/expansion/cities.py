import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import timetables as t
t.OUT=t.BASE/'results/expansion/timetables'
t.CITIES={'sydney':'52dd19bb73678e55b84989d8a9158106','winnipeg':'85428d211b563c8ff18f78e040d034f7','detroit':'a82b8f0beaa8ef1c8200ed8feacc6a73','bordeaux':'8c81985c63773797960768f73530386b'}
if __name__=='__main__':
    for city in t.CITIES:t.prepare(city);t.run(city)

