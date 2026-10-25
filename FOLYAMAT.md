# Folyamatleírás

Ez a dokumentum lépésről lépésre, a végrehajtás sorrendjében írja le, mi történik a
programban egy TCE kiszűrése közben. A hivatkozott sorszámok a [vetter.py](vetter.py)
fájlra vonatkoznak. A küszöbök a `TH` szótárban vannak ([vetter.py:11](vetter.py:11)).

Jelölések: `t` idő [BTJD], `f` normált fluxus, `P` periódus [nap], `t0` epocha [BTJD],
`dur` tranzithossz [nap], `n` a tranzit sorszáma (epochaszám).

---

## A) Indítás és bemenet (`main`, [vetter.py:123](vetter.py:123))

1. **Parancssor beolvasása.** Kötelező argumentum a TCE-ket tartalmazó CSV útvonala.
   Opcionális: `-o/--output` (alapértelmezés: `results.csv`) és `--max-sectors`
   (alapértelmezés: mind).
2. **A TCE-táblázat beolvasása** pandasszal, majd soronként (egy sor egy TCE) feldolgozás.
   Elvárt oszlopok: `tic`, `period` [nap], `epoch` [BTJD vagy BJD], `duration` [óra],
   opcionálisan `rstar` [R☉].
3. **A csillagsugár kezelése.** Ha az `rstar` oszlop hiányzik vagy üres, `None` lesz,
   és később a sugár helyett a mélység alapján dől el a „túl nagy” teszt.
4. **Hibakezelés.** Ha egy TCE feldolgozása közben bármilyen kivétel történik
   (nincs QLP adat, hálózati hiba stb.), a TCE `ERROR` címkét kap, a hibaüzenet a
   `flags` oszlopba kerül, és a program a következő TCE-vel folytatja.

## B) Fénygörbe letöltése és előkészítése (`load_qlp`, [vetter.py:26](vetter.py:26))

5. **Keresés a MAST-on.** A lightkurve megkeresi a `TIC <szám>` célpont összes QLP
   fénygörbéjét (`author="QLP"`). Ha nincs találat, `ValueError` → a TCE `ERROR` lesz.
6. **Szektorok korlátozása.** Ha meg van adva a `--max-sectors N`, csak az első N
   szektort tölti le, a keresési lista sorrendjében (általában időrendben).
7. **Letöltés.** Az összes kiválasztott szektor fénygörbéje letöltődik (a lightkurve
   helyben gyorsítótárazza őket, így ismételt futtatáskor nem tölti le újra).
8. **Minőségszűrés szektoronként.** Csak a `quality == 0` pontok maradnak. Ez
   kritikus lépés: a QLP megjelölt pontjai között vannak extrém kiugrók is
   (pl. 0,36-os relatív fluxus), amelyek nélküle elrontanák a mélységbecslést.
9. **Oszlopok kiválasztása.** Három trendszűrt fluxusoszlopot vesz át, és egységes
   névre nevezi őket:
   - `flux` – a QLP által trendszűrt fluxus; ezen fut a legtöbb teszt;
   - `flux_sml` – ugyanez kis apertúrával;
   - `flux_lag` – ugyanez nagy apertúrával.

   A QLP-fájlban ezek neve szektorfüggő: a 1–55. szektorban `kspsap_flux`,
   `kspsap_flux_sml`, `kspsap_flux_lag`, az 56.-tól `det_flux`, `det_flux_sml`,
   `det_flux_lag`. A program mindkét változatot keresi. A lightkurve alapértelmezett
   `flux` oszlopát (a nyers, trendszűretlen `sap_flux`-ot) szándékosan nem használja.
   Ha egy oszlop egyik néven sincs meg, NaN értékekkel tölti fel; a fő fluxus nélküli
   pontokat a 11. lépés eldobja.
10. **Normálás szektoronként.** Minden oszlopot elosztja a saját szektorbeli
    mediánjával, így a fluxus minden szektorban 1 körül van, és a szektorok közötti
    szintkülönbség eltűnik. Csupa-NaN oszlopot érintetlenül hagy.
11. **Összefűzés.** A szektorokat egy táblázatba fűzi, eldobja azokat a sorokat,
    ahol az idő vagy a fő fluxus hiányzik, és idő szerint rendez.

## C) Előkészítés a vettinghez (`vet` eleje, [vetter.py:56](vetter.py:56))

12. **Mértékegységek.** A tranzithosszt órából napba váltja (`dur = duration / 24`).
13. **Epocha átváltása.** Ha az epocha 2 400 000-nél nagyobb, BJD-nek tekinti, és
    kivon belőle 2 457 000-et, így BTJD lesz, ugyanabban a rendszerben, mint a QLP ideje.
14. **Epochaszám minden pontra:** `n = round((t − t0) / P)`, vagyis melyik tranzithoz
    van a legközelebb az adott mérési pont.
15. **Tranziton kívüli maszk** (`oot`): azok a pontok, amelyek egy teljes tranzithossznál
    messzebb vannak a legközelebbi tranzit közepétől. (A tranzit maga ±dur/2 széles,
    így ez biztonsági sávot is hagy a be- és kilépés körül.)
16. **Fehérzaj becslése:** `sigma = 1,4826 · MAD(f[oot])`. A MAD (medián abszolút
    eltérés) a kiugrókra érzéketlen; az 1,4826-os szorzóval normális eloszlásnál a
    szórást adja.
17. **Vörös (korrelált) zaj becslése, β-faktor** (Pont et al. 2006):
    1. a tranziton kívüli pontokat tranzithossznyi időbinekbe sorolja;
    2. eldobja a 3 pontnál kevesebbet tartalmazó bineket;
    3. minden binnek veszi az átlagát és pontszámát;
    4. a binátlagok robusztus szórását a pontszám gyökével skálázva összeveti a
       fehérzajjal: `β = 1,4826 · median(|átlag − medián| · √pontszám) / sigma`.

    Tiszta fehér zajnál β ≈ 1; ha a zaj tranzithossznyi időskálán „csomósodik”
    (csillagaktivitás, maradék szisztematika), β > 1.
18. **Vörös zajjal felfújt szigma:** `sigma_r = sigma · max(β, 1)`. Ha β nem
    számolható (NaN), 1-nek veszi. A két szigma szerepe:
    - `sigma` (fehér) → az észlelési, azaz FA-tesztekhez (úgy, ahogy a QLP is észlel);
    - `sigma_r` (vörös) → az FP-tesztekhez, mert fehér zajjal ezek ismert bolygókon is
      gyakran hamisan jeleztek.

## D) Az alapművelet: doboz-mélység (`box`, [vetter.py:44](vetter.py:44))

Minden mérőszám ugyanazt a segédfüggvényt hívja, ezért itt egyszer leírjuk:

19. **Fázisba hajtogatás.** Minden pont időbeli távolságát (`x`, napban) kiszámolja a
    legközelebbi „esemény” közepétől. Az esemény a `phase` fázisnál van
    (0 = fő tranzit, 0,5 körül = másodlagos fedés).
20. **Részhalmaz kiválasztása.** Ha meg van adva `sel` maszk (pl. csak páratlan
    tranzitok), a bent- és a kintpontokat is erre szűkíti; a NaN fluxusú pontokat kihagyja.
21. **Bent és kint pontok.**
    - bent (`inn`): `|x| < dur/2`, azaz a tranzit ideje alatt;
    - kint (`out`): `dur < |x| < 3·dur`, azaz a tranzit két oldalán lévő **lokális
      alapvonal**. A közeli alapvonal csökkenti a maradék trendek hatását.
22. **Elégséges adat ellenőrzése.** Ha bármelyik csoportban 3-nál kevesebb pont van,
    az eredmény `(NaN, ∞)`, vagyis „nincs mérés”.
23. **Mélység:** `depth = medián(f[out]) − átlag(f[inn])`. Pozitív érték fényességcsökkenést
    jelent.
24. **Mélység hibája:** `err = sigma · √(1/N_bent + 1/N_kint)`, ahol a hívó dönti el,
    hogy `sigma` vagy `sigma_r` kerül bele.

## E) Mérőszámok kiszámítása (`vet`, [vetter.py:72](vetter.py:72)–[105](vetter.py:105))

25. **Fő tranzit mélysége és SNR-je.** `box(...)` a 0 fázisnál, az összes tranziton,
    fehér szigmával. Eredmény: `depth_ppm` (mélység ppm-ben) és `snr = depth / err`.
    Ez a Kepler/TESS pipeline-ok MES-ének (multiple event statistic) egyszerű megfelelője.
26. **Egyedi tranzitok végigjárása.** Minden olyan `n` epochaszámra, amelyhez tartozik
    tranzitközeli pont, külön `box(...)` hívás `sel = (n == k)` maszkkal. Ha az eredmény
    véges, az adott tranzit SNR-je (SES, single event statistic) bekerül a `ses` szótárba.
27. **Tranzitszám.** `n_transits` = azoknak a tranzitoknak a száma, amelyekhez elég
    (≥ 3 bent és ≥ 3 kint) pont volt.
28. **SNR a legerősebb esemény nélkül.** Kiválasztja a legnagyobb SES-ű tranzitot, és
    újraszámolja a teljes SNR-t nélküle (`sel = n != kmax`) → `snr_wo_max`. Ha a jelet
    egyetlen kiugró esemény (pl. egy szisztematikus ugrás) adja, ez drasztikusan leesik.
    Ha egyáltalán nem volt mérhető tranzit, `NaN`.
29. **Páros/páratlan mélység.** Két `box(...)` hívás `sigma_r`-rel: egy a páratlan
    (`n % 2 == 1`), egy a páros (`n % 2 == 0`) tranzitokra, mindkettő a saját lokális
    alapvonalával. A különbség szignifikanciája:
    `odd_even_sigma = |d_páratlan − d_páros| / √(e_páratlan² + e_páros²)`.
    Ha egy fedési kettőst fél periódussal észleltek, a fő- és mellékfedés felváltva
    következik, és ez az érték nagy lesz.
30. **Másodlagos fedés keresése.**
    1. A 0,15–0,85 fázistartományt végigpásztázza, `dur/P/3` lépésközzel (legalább 0,001),
       tehát egy tranzithosszon belül háromszor mintavételez;
    2. minden fázisnál `box(...)` hívás `sigma_r`-rel;
    3. kiválasztja a legszignifikánsabb (legnagyobb mélység/hiba) pontot.

    Eredmény: `sec_sigma` (szignifikancia) és `sec_ratio = d_másodlagos / d_fő`.
    A tág fázistartomány excentrikus pályák esetén is megtalálja a mellékfedést.
31. **Apertúra-összevetés.** Ugyanaz a fő tranzit `box(...)` hívás a kis
    (`flux_sml`) és a nagy (`flux_lag`) apertúrás fluxuson, `sigma_r`-rel.
    - `ap_ratio = d_nagy / d_kicsi`;
    - `ap_sigma = (d_nagy − d_kicsi) / √(e_kicsi² + e_nagy²)`.

    Ha a jelet a célcsillag okozza, a mélység a két apertúrában közel egyforma (vagy a
    nagyban kisebb, mert több szomszédos fény hígítja). Ha a nagyban mélyebb, a forrás
    valószínűleg egy közeli csillag, amelyet a nagy apertúra jobban lefed. Ha nincs
    apertúra-adat, mindkét érték NaN, és a teszt nem jelez.
32. **Bolygósugár.** Ha van `rstar`: `rp_rjup = √depth · rstar · 9,731`
    (R☉ → R_Jup átváltás). Negatív mélységnél 0-t vesz. Ha nincs `rstar`, NaN.

## F) Tesztek és döntés ([vetter.py:107](vetter.py:107)–[120](vetter.py:120))

33. **FA-tesztek (téves riasztás)**, mindegyik igaz/hamis:
    - `LOW_SNR`: `snr < 7.1` (NaN SNR esetén is igaz);
    - `FEW_TRANSITS`: `n_transits < 2`;
    - `SINGLE_EVENT`: `snr_wo_max < 5.0` (NaN esetén is igaz).
34. **FP-tesztek (nem bolygó)**:
    - `ODD_EVEN`: `odd_even_sigma > 4`;
    - `SECONDARY`: `sec_sigma > 4` **és** `sec_ratio > 0.1`. A második feltétel védi meg
      a forró Jupitereket (pl. WASP-18 b), amelyeknek valódi, de a fő tranzithoz képest
      kicsi (néhány %-os) másodlagos fedése van;
    - `TOO_LARGE`: ha van `rstar`, `rp_rjup > 2.5`; különben `depth > 0.05` (5%);
    - `APERTURE`: `ap_sigma > 4` **és** `ap_ratio > 1.3`.

    NaN mérőszám esetén ezek a tesztek nem jeleznek (a NaN-nal való összehasonlítás hamis).
35. **Flag-lista.** Az összes igaz teszt nevét összegyűjti, előbb az FA-, majd az
    FP-teszteket. Az FP-flag-ek akkor is bekerülnek, ha végül FA lesz a döntés, így
    látható, mi jelzett még.
36. **Végső besorolás, prioritási sorrendben:**
    1. ha bármelyik FA-teszt igaz → **FA** (nincs megbízható ismétlődő jel, ezért az
       alakjára vonatkozó FP-tesztek sem értelmezhetők);
    2. különben ha bármelyik FP-teszt igaz → **FP**;
    3. különben → **PC**.
37. **Visszatérési érték.** Egy szótár: `disposition`, `flags` (pontosvesszővel
    elválasztva) és minden mérőszám (`beta`, `depth_ppm`, `snr`, `n_transits`,
    `snr_wo_max`, `odd_even_sigma`, `sec_sigma`, `sec_ratio`, `ap_ratio`, `ap_sigma`,
    `rp_rjup`).

## G) Kimenet (`main` vége)

38. **Képernyőre írás.** Minden TCE után kiírja: `TIC  besorolás  flag-ek`.
39. **CSV mentése.** A bemeneti oszlopokat kiegészíti az eredményszótárral, és az
    összes TCE-t egy CSV-be írja (`-o` útvonal). Az `ERROR` soroknál a mérőszám-oszlopok
    üresek.

---

## Mellékág: validálás ismert objektumokon ([validate.py](validate.py))

40. **Argumentumok:** `-n` (TOI-szám osztályonként), `--max-sectors` (alapból 3),
    `--seed` (a véletlen mintavétel magja, alapból 42), `-o` (kimeneti CSV).
41. **TOI-katalógus lekérése** a NASA Exoplanet Archive TAP-felületéről: csak azok a
    TOI-k, amelyeknek van TFOPWG-diszpozíciójuk (CP, KP, FP, FA) és érvényes periódusuk.
42. **Elvárt címke hozzárendelése:** CP (megerősített bolygó) és KP (ismert bolygó) → PC,
    FP → FP, FA → FA.
43. **Mintavétel:** osztályonként `n` véletlen TOI, a megadott `seed`-del
    (reprodukálható; másik `seed` független ellenőrző mintát ad).
44. **Vetting minden mintabeli TOI-ra:** `load_qlp` + `vet`, a katalógus periódusával,
    epochájával, tranzithosszával és csillagsugarával. Hiba esetén `ERROR`.
45. **Kiírás és mentés:** soronként `TOI  valódi → vetter  flag-ek`, majd CSV.
46. **Kiértékelés:** tévesztési mátrix (sorok: valódi, oszlopok: vetter) és pontosság
    az `ERROR` sorok nélkül, valamint a hibás sorok száma.

## Mellékág: offline tesztek ([test_vetter.py](test_vetter.py))

47. **Szintetikus fénygörbe:** 27 napos, 30 perces mintavételű, Gauss-zajos (1000 ppm)
    sorozat, `P = 3 nap`, 3 órás doboz alakú tranzitokkal. Paraméterezhető: mélység,
    eltérő páratlan mélység, másodlagos fedés, és a nagy apertúrában felnagyított tranzit.
48. **Hat eset**, mindegyik egy elvárt kimenettel: bolygó → PC; csak zaj → FA;
    páros/páratlan eltérés, másodlagos fedés, túl nagy sugár (`rstar = 3`) és
    apertúra-eltérés → FP.
