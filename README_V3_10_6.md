# Skyttegrav V3.10.6 – Fiender i verkliga sidogångar

**Bas:** V3.10.5 (som i sin tur bygger på V3.10.4/V3.10.3). Fullständiga ersättningsfiler; inga patchskript.

## Implementerat

- Sparse seed-stabila sentries i sidogångar: index 7, 15, 23, 31...; första vid **568 meter**. Fiender står 2,8 m in i den redan uppgrävda och streamade sidogången. Fungerar i både öppna sidogångar och dugouts.
- `EnemySpec` bär valfri `branch_index`, `branch_side`, `branch_depth`. Stående sidofiender får en separat immutable identitet, en korrekt world-XYZ via befintlig `branch_point` och ett eget 3D-body pose; de syns i rendering och kan träffas av exakt samma frysta ray/sfär och world-mesh-skottsystem som övriga fiender.
- Deras FOV orienteras mot den riktiga öppningen. Upptäckt, spelarsikt och fiendens eldgivning valideras mot **renderade statiska triangelmesh** i stället för huvudruttens förenklade cylindermodell. Om world-mesh saknas räknas INTE fienden som synlig och skott från spelaren till honom godtas inte på chans.
- Spelarens faktiska, redan ritade skärmbild + öppen triangelbaserad siktlinje måste stödja en `seen_enemy`-rapport innan SoldierBrain får automatisk evidens att utforska sidogången. Ingen seeded magic knowledge.
- Sidofiender kan överraska/säkra sin sidoposition, skjuta genom den riktiga öppningen och dö individuellt. De får inte använda main-routens rush-FSM (skulle innebära att springa genom jordväggen), och får inte stoppa huvudvägens framryckningslås som en fiende rakt fram.

## Tester

149/149 Python offline-tester godkända inklusive 5 nya regressionsfall: seed/branch-side, mainline-vs-room-världsposition, 3D-frozen-hit-sfärer, visuell projektion, verkligt mesh-blockerad sikt och öppning, samt ingen huvudrutt-blockering.

Tydlig reproducerbar geometri i 80m-sektion 560: från 563–565m blockerar jordväggen för sentry vid 568m/branch-depth 2,8m; från 566–567m är en fri öppning möjlig. Detta är offline-replay av procedurgenererad 3D, INTE livevisuell verifiering på GTX 1070.

Shaderkoden är oförändrad sedan V3.10.4, där tidigare GLSL/EGL-kontroll passerade.

## Begränsningar / NEXT

Sidofiender är inledningsvis STATIONÄRA i rummet och har skydd genom den verkliga jordgeometrin. De vandrar ännu inte mellan flera rum, använder inte gren-navigation/pathfinding och kastar inga granater. Fiender ovanför vallen, synliga nedhopp, avancerad gruppkoordination, grenater och **äkta topologiska T-vägval** väntar fortfarande. Soldatens befintliga frivilliga rumssökningar från V3.10.5 är bevarade.

Skottgeometri använder faktiska trianglar; fiendens kropp har fortfarande GPU-pose-relaterade sfärproxy-volymer. Ingen förbättring av fysisk skjutdetektion är uppmätt.

## Testa

Installera genom att packa upp *samtliga* kompletta filer i roten till en V3.10.5-installation. Kör

```bash
cd ~/infinite_trench_3d_test
python3 -m unittest discover -s tests -p 'test_v*.py' -q
python3 trench_3d_test.py
```

För första sidofienden hoppa med F11 nära 563–565m och låt SoldierBrain närma sig korsningen vid 568m. Notera om han kan upptäcka fienden, bli beskjuten från sidan, och om skott genom öppningen fungerar. Testa även fiendepar vid 516–518m och rutingenomsökning vid 640m.

Ingen commit/push/merge är gjord.
