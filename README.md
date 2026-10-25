# QLP TCE vetter

Egyszerű, LEO-vetter-szerű kiszűrő program a TESS **QLP** (Quick Look Pipeline)
TCE-ihez. Minden TCE-t a következők egyikével címkéz:

- **PC** – Planet Candidate (bolygójelölt)
- **FP** – False Positive (valódi asztrofizikai jel, de nem bolygó: fedési kettős, szennyező szomszéd)
- **FA** – False Alarm (nincs valódi, ismétlődő tranzit: zaj, szisztematika)

## Telepítés
```bash
pip install -r requirements.txt
```
Python ≥ 3.9. A fénygörbéket a program a MAST-ról tölti le (internet kell).

## Használat
Készíts egy CSV-t a TCE-kkel:

```csv
tic,period,epoch,duration,rstar
100100827,0.94145223,2458375.169883,2.19,1.23
```

| oszlop | jelentés |
|---|---|
| `tic` | TIC azonosító |
| `period` | periódus [nap] |
| `epoch` | tranzitközép [BTJD vagy BJD – a BJD-t automatikusan átváltja] |
| `duration` | tranzithossz [óra] |
| `rstar` | (opcionális) csillagsugár [R☉], a bolygósugár-teszthez |

Futtatás (példa bemenet: `example_tces.csv`):
```bash
python vetter.py example_tces.csv -o results.csv
```
Opció: `--max-sectors N` – csak az első N szektort tölti le (gyorsabb, de kisebb SNR).

A kimenet a bemeneti oszlopokon túl tartalmazza a `disposition` (PC/FP/FA/ERROR),
a `flags` (a kiváltó tesztek) és az összes mérőszám oszlopot.

Pythonból:
```python
from vetter import load_qlp, vet
lc = load_qlp(100100827, max_sectors=2)
print(vet(lc, period=0.94145223, epoch=2458375.169883, duration=2.19, rstar=1.23))
```
A `vet()` bármilyen `time`, `flux` (és opcionálisan `flux_sml`, `flux_lag`)
oszlopú, 1-re normált, trendszűrt DataFrame-mel működik.

## Flag-ek
| Flag | Eredmény | Jelentés |
|---|---|---|
| `LOW_SNR` | FA | túl gyenge jel (SNR < 7.1) |
| `FEW_TRANSITS` | FA | kevesebb mint 2 tranzit esik adatra |
| `SINGLE_EVENT` | FA | a jelet egyetlen esemény okozza |
| `ODD_EVEN` | FP | eltérő páros/páratlan mélység |
| `SECONDARY` | FP | erős másodlagos fedés |
| `TOO_LARGE` | FP | túl nagy test (> 2.5 R_J, vagy > 5% mélység) |
| `APERTURE` | FP | nagyobb apertúrában mélyebb → szomszédos csillag a forrás |

Részletek és küszöbök: [DEVELOPER.md](DEVELOPER.md). Lépésről lépésre leírt
működés: [FOLYAMAT.md](FOLYAMAT.md).

## Ellenőrzés ismert objektumokon
`python validate.py -n 20` a NASA Exoplanet Archive TOI-katalógusából véletlenszerűen
kiválaszt osztályonként 20 TOI-t ismert TFOPWG-diszpozícióval (CP/KP = megerősített/ismert
bolygó → PC, FP → FP, FA → FA), és a QLP fénygörbék első 3 szektorán futtatja a vettert.

Eredmény (2026-10-24, trendszűrt QLP-fluxussal), a küszöbök hangolására használt mintán (`--seed 42`) és egy független mintán (`--seed 7`):

| Valódi \ Vetter | FA | FP | PC | | FA | FP | PC |
|---|---|---|---|---|---|---|---|
| **FA** | 16 | 1 | 3 | | 13 | 2 | 5 |
| **FP** | 10 | 5 | 5 | | 6 | 8 | 5 |
| **ismert bolygó** | 3 | 6 | 10 | | 0 | 8 | 12 |
| **Pontosság** | | | **53%** | | | | **56%** |

Mindkét mintában egy-egy TOI-hoz nem volt QLP-adat (`ERROR`), ezek kimaradtak.

Egy konkrét példa: WASP-18 b → **PC** (a mérhető, 41σ-s másodlagos fedése ellenére, mert annak
mélysége csak ~5%-a a fő tranzitnak).

Értelmezés, korlátok:
- Az ismert bolygók ~55–60%-a PC. A tévesztések többsége hamis `SECONDARY` vagy `APERTURE`
  jelzés: a másodlagos fedés keresése ~100 fázist próbál végig, és ennyi próbálkozásból
  a zaj is gyakran ad 4σ körüli csúcsot; az apertúra-mélységarány pedig több ismert bolygónál
  is ~2. Ez a két küszöb újrahangolásra (vagy a próbálkozások számával való korrekcióra) szorul.
- Az FP-k kb. harmadát ismeri fel: sok TOI-FP-t földi follow-up vagy centroid-elemzés
  alapján soroltak be, amit egy pusztán fotometriai, doboz-modelles vetter nem lát.
- A program szándékosan egyszerű; nem helyettesíti a LEO-vettert vagy az emberi vizsgálatot.
  Előszűrésre és rangsorolásra használd.
