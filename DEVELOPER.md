# Fejlesztői dokumentáció

## Felépítés
Az egész program a `vetter.py`-ban van:

| Függvény | Feladat |
|---|---|
| `load_qlp(tic, max_sectors)` | QLP fénygörbék letöltése (lightkurve/MAST), szektoronként 1-re normálva. Csak `quality == 0` pontok. Oszlopok: `time`, `flux` (trendszűrt), `flux_sml`, `flux_lag` (trendszűrt, kis/nagy apertúra). A QLP-fájlban ezek a 1–55. szektorban `kspsap_flux*`, az 56.-tól `det_flux*` néven szerepelnek; a függvény mindkettőt kezeli. A lightkurve alapértelmezett `flux` oszlopa a nyers `sap_flux`, ezért ezt szándékosan nem használjuk. |
| `box(t, f, P, t0, dur, sigma, phase, sel)` | Doboz-mélység a megadott fázisban, lokális alapvonallal (1–3 tranzithossznyira a középponttól), és a hibája. `sel` maszkkal részhalmaz (pl. páratlan tranzitok) választható. |
| `vet(lc, period, epoch, duration, rstar)` | Mérőszámok számítása és döntés. Bármilyen `time/flux/...` oszlopú DataFrame-mel hívható, így nem csak QLP adaton használható. |
| `main()` | CLI: CSV be, CSV ki. |

A zaj (`sigma`) a tranziton kívüli pontok robusztus szórása (1.4826·MAD). A vörös
(korrelált) zajt egy β-faktor méri (Pont et al. 2006): a tranzithossznyi binek szórása
osztva a fehérzaj-várakozással. Az FA-tesztek (észlelés) a fehérzaj-`sigma`-t használják,
ahogy a QLP is; az FP-tesztek (páros/páratlan, másodlagos, apertúra) a β-val felfújt
`sigma_r`-t, mert vörös zaj nélkül ezek gyakran hamisan jeleztek ismert bolygókon.

## Döntési logika
Előbb az FA-teszteket nézzük; ha bármelyik teljesül → `FA`. Különben ha bármelyik
FP-teszt teljesül → `FP`. Különben `PC`. A kiváltó flag-ek a `flags` oszlopba kerülnek
(akkor is, ha az FA felülírja az FP-t).

| Flag | Típus | Feltétel (`TH` kulcsok) | Ötlet |
|---|---|---|---|
| `LOW_SNR` | FA | `snr < snr` (7.1) | A teljes tranzit-SNR (MES-szerű) túl kicsi. |
| `FEW_TRANSITS` | FA | `n_transits < min_transits` (2) | Legalább két, adattal lefedett tranzit kell. |
| `SINGLE_EVENT` | FA | `snr_wo_max < snr_wo_max` (5) | A jelet egyetlen esemény (pl. szisztematika) dominálja. |
| `ODD_EVEN` | FP | `odd_even_sigma > odd_even` (4σ) | Eltérő páros/páratlan mélység → fedési kettős dupla periódussal. |
| `SECONDARY` | FP | `sec_sigma > sec_sigma` (4σ) és `sec_ratio > sec_ratio` (0.1) | Jelentős másodlagos fedés; a mélységarány-feltétel megvédi a forró Jupitereket (pl. WASP-18 b), akiknek kicsi, de mérhető a másodlagos fedése. |
| `TOO_LARGE` | FP | `rp_rjup > max_rp` (2.5 R_J), vagy `rstar` nélkül `depth > max_depth` (5%) | Túl nagy a test ahhoz, hogy bolygó legyen. |
| `APERTURE` | FP | `ap_sigma > ap_sigma` (4σ) és `ap_ratio > ap_ratio` (1.3) | A nagy apertúrában mélyebb a tranzit → a jel egy közeli csillagtól jön. |

Összevetés a LEO-vetterrel: a LEO-vetter (Kunimoto et al. 2025) sokkal több tesztet
használ (pl. alakteszt, MCMC-illesztés, chases/rubble, centroid, modellillesztésen alapuló
mélységek). Itt csak a legfontosabb, egyszerű doboz-modellel számolható teszteket tartottuk meg.

## Tesztelés
- `python -m pytest -q` – szintetikus fénygörbék: bolygó → PC, zaj → FA, páros/páratlan,
  másodlagos fedés, túl nagy sugár, apertúra → FP. Internet nem kell.
- `python validate.py -n 15 --max-sectors 3` – TOI-k a NASA Exoplanet Archive-ból
  ismert TFOPWG diszpozícióval (CP/KP → PC, FP → FP, FA → FA), fix véletlen mintával
  (`random_state=42`), tévesztési mátrixot ír ki.

## Bővítés
Lásd `AGENTS.md`. Új teszt: mérőszám a `vet()`-ben → flag a `fa`/`fp` szótárban →
küszöb a `TH`-ban → szintetikus teszt → sor a fenti táblázatban.
