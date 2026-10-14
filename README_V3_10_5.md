# Skyttegrav V3.10.5 – Rutinavsökning av skyddsrum

Bas: V3.10.4. Inga ändringar i träffgeometri, fiendens siktmodell, shaders, laddning eller Skjutbanan.

## Implementerat

- Vissa seed-stabila **dugouts** undersöks av SoldierBrain utan upptäckt fiende. Första planerade rutingenomsökning är vid junction index 8 (ca 640m), sedan bland annat ca 1072m, 1504m, 1936m.
- Återanvänder *befintlig* väg in genom portalen, `turn_in`, `dash`, `kneel_scan`, `explore`, `dugout_clear`, `turn_back`, `backtrack`, `turn_main`, `rejoin`.
- SoldierBrain gör sin försiktiga blickkontroll FÖRST, beslutar sedan att avsöka. En verklig rapport om fiendeaktivitet tar alltid företräde över rutingenomsökning. Rutinen skapar ingen falsk `branch_evidence`.
- De första sex korsningarna lämnas oförändrade för att skydda kända fall. Rutingenomsökning är sällsynt så speltempot bevaras.
- Räknaren `routine_rooms_cleared` ökar bara när soldaten faktiskt har nått avsökningspunkten, inte när rutinen beslutades.

## Avsiktlig avgränsning

- Det finns **ännu inga fiender på sidogångarnas faktiska världspunkter**. Det vore ohederligt att placera dem där med gamla huvudruttens siktmodell och hävda att de kan skjutas korrekt.
- Granater, patruller ovanför vallen och verkliga T-vägval återstår också. Rum utan fiender är ett första, fristående arkadsteg.

## Tester

- 144/144 Python-unittest offline godkända inklusive tre nya tester för seed-policy, faktisk komplett in/ut-navigation och evidensprioritet.
- GLSL/Material/shaders oförändrade jämfört med V3.10.4; den tidigare körda Mesa/EGL-kontrollen passerade.
- INTE verifierat visuellt på GTX 1070.

## Installation

Packa upp fullständiga filer direkt ovanpå V3.10.4. Utgå inte från annan modifierad version utan att först jämföra.

```bash
cd ~/infinite_trench_3d_test
python3 -m unittest discover -s tests -p 'test_v*.py' -q
python3 trench_3d_test.py
```

Testa gärna F11-hopp till ca 634 m: soldaten ska titta in, gå runt hörnet, nå cirka 7–8m in, söka av och återvända till huvudgången före ca 645 m.
