# AGENTS.md

Útmutató AI-ügynököknek (és embereknek), akik ezen a repón dolgoznak.

## Cél
Minimális, LEO-vetter-szerű kiszűrő program, ami a TESS QLP pipeline TCE-it
`PC` (Planet Candidate), `FP` (False Positive) vagy `FA` (False Alarm) címkével látja el.

## Fájlok
- `vetter.py` – a teljes logika: QLP letöltés (`load_qlp`), mérőszámok + döntés (`vet`), CLI.
- `validate.py` – ellenőrzés ismert TOI-kon (NASA Exoplanet Archive, TFOPWG diszpozíciók).
- `test_vetter.py` – offline pytest tesztek szintetikus fénygörbéken.
- `README.md` – felhasználói dokumentáció; `DEVELOPER.md` – fejlesztői dokumentáció;
  `FOLYAMAT.md` – a program lépéseinek lineáris leírása (logikai változásnál frissítsd).

## Szabályok
- **Kevés kód.** Ne vezess be új modult, osztályt vagy függőséget, ha egy függvény is elég.
- Minden küszöbérték a `vetter.py` `TH` szótárában van; ne szórd szét a kódban.
- Új teszt (flag) = egy új mérőszám a `vet()`-ben + egy sor a `fa` vagy `fp` szótárban
  + egy szintetikus teszt a `test_vetter.py`-ban + egy sor a `DEVELOPER.md` táblázatában.
- Kód és kommentek angolul, dokumentáció magyarul.

## Ellenőrzés változtatás után
```bash
python -m pytest -q             # gyors, offline
python validate.py -n 15        # lassú, internet kell (MAST + Exoplanet Archive)
```
A küszöbök hangolásakor a validációs pontosságot jelentsd a változtatással együtt,
és vigyázz a túlillesztésre (ugyanazon a kis mintán ne hangolj és értékelj is).
