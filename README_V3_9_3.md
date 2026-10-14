# Skyttegrav V3.9.3 – GPU-skelett + animationslaboratorium

**Bas: V3.9.1.** Den här ZIP-filen innehåller **kompletta ersättningsfiler** inklusive de tidigare förberedda V3.9.2-materialen/skuggorna. Packa upp **i repots rot** och skriv över befintliga filer. **Inga installations-/patchskript. Ingen push, merge eller commit har gjorts.** Behåll befintliga `assets/` och alla övriga speldata.

## Vad är faktiskt nytt?

- **Skelettstyrd GPU-animation:** 16 ben (bäcken, bröstkorg, huvud, över-/underarmar, händer, lår, underben, fötter och vapen). Tre färdigbyggda utrustningsvarianter ligger **statiskt på GPU:n**; endast en liten matrispalett ändras per figur/bildruta. Modellens ruttposition och träffsystem ligger fortsatt i `EnemyAgent` och den befintliga banan.
- **En draw call per synlig fiendesoldat i huvudpasset** och en per relevant skuggpass (i stället för cirka 58–59 separata delar per pass). Cirka **3,5 MB** bind-mesh-data för samtliga tre varianter. Inga per-frame GPU-meshuppladdningar för animation.
- **Samma skelettposition i ljus- och skuggpass.** V3.9.2:s sol-/mån-/lamp-skuggor, befintliga material/normal maps och de nya 1024×1024-soldattexturerna ingår.
- **F1 animationslaboratorium:** Titta på en soldat ungefär 5 m framför kameran, växla framåt mellan 12 ställningar. Spelets AI/tidsfrister pausas i demonstrationsläget och demonstrationen kan inte beskjutas; efter sista ställningen stängs läget. Koden är förberedd för många fler animationer.
- **Animationsställningar i F1:** `stand` → `walk` → `run` → `crouch` → `kneel` → `prone` → `supine_sleep` → `fear_curl` → `aim` → `fire` → `spade_attack` → `dead` → av. Dessa är **test-/presentationsställningar**, inte alla AI-val i normal gameplay ännu.
- **Fysisk position ägs av rutten, inte animationens steg.** Rörelsen använder faktisk förflyttad sträcka, och fiendens världsläge återanvänder skyttegravens existerande hinderstyrning. Lådor/bråte får en mjuk kroppsbreddsanpassad undanmanöver med bibehållen banbegränsning. Det är inte en full 3D-fysikmotor.
- **Fall och död** blendas tidsmässigt. Den tidigare death screen/poängen/AI-reglerna är kvar.
- **Fallback:** Om GPU-riggens shader-/resursinitiering misslyckas startar den äldre V3.9.2-renderaren automatiskt, och spelet ska fortfarande vara körbart. Kontrollera loggen `GPU-skelett ...` för att veta vilken renderer som faktiskt kör.

### Varför inte en nedladdad riggad GLB i samma version?

Det gick att identifiera lovande modeller och över 120 fria animationer hos Quaternius (CC0), men själva modellarkivet kunde inte laddas ned och valideras i leveransmiljön. Vi levererar därför **inte en påstådd fotorealistisk GLB som saknas** eller en tveksamt licensierad asset. Detta är ett verkligt GPU-baserat, **single-influence** skelett med samma befintliga skulpterade figur som V3.9.2. Kontinuerlig multi-weight-huddeformation, full GLB-import, IK-fotplantering och riktig fysikkollision är **inte färdiga**. Framför allt liggande, sovande, rädda och spadanfall behöver framtida konstnärligt gjorda animationsklipp för att bli fullt naturtrogna.

För nästa steg: Quaternius **Universal Base Characters** + **Universal Animation Library** (CC0; GLB/glTF, animationsbibliotek för gång, spring, krypning, sittande, gevär m.m.). Lämplig verklighetstrogen soldat och rigg måste utvärderas för klädsel, licens, skalning och gemensamma ben innan byte.

## Installation / start

1. Spara gärna en kopia av fungerande V3.9.1.
2. Packa upp ZIP:en i ditt befintliga Skyttegrav-repo. Skriv över filer med samma namn.
3. Starta spelet:

```bash
python3 trench_3d_test.py
```

Inga förändringar på Skjutbanans träffdetektionskod. Python-beroendena är oförändrade (Pygame, ModernGL, NumPy, Pillow).

## Snabbtest på GTX 1070

| ID | Gör så här | Förväntat |
|---|---|---|
| S1 | Starta och läs terminalen | `V3.9.3: GPU-skelett 16 ben` syns, inte fallback till legacy. |
| S2 | Tryck `F1` upprepade gånger | En demosoldat visas framför dig; ställningar går framåt och slutar i AV. |
| S3 | Prova F1 `walk` och `run` | Benen växlar/fötterna lyfts; figuren står kvar på samma plats i demonstrationsläget. |
| S4 | Prova F1 `kneel`, `prone`, `supine_sleep` och `fear_curl` | Bål/armar/ben ändrar ställning; inga kroppsdelar tydligt genom golvet. |
| S5 | Prova F1 `spade_attack` och `fire` | Spade visas i attackställning; normal beväpning finns i övriga lägen. F1 `fire` är en **ställning**, inte en faktiskt avfyrad fiendebullet. |
| S6 | Låt F1 gå till AV, spela första fienden runt 32 m | Fienden kan fortfarande skjutas med musen, AI och game-over fungerar. |
| S7 | `F12` skuggor AV/PÅ med F1 soldat synlig | Skuggan följer aktuell kroppsställning, ingen avskild gammal kroppsform. |
| S8 | `F11` normalgång och flera fiender | Jämför `draw`/`total` frametime, särskilt p95/max, med V3.9.1. Skriv ned resultat. |
| S9 | Debughoppa med `↑` till 450 m | Vänta på komplett streamad terräng; tidigare V3.9.1-hopp ska fortfarande fungera. |
| S10 | Fiende nära låda runt 509/665 m | Ingen tydlig genomgång genom lådans mitt, rimlig rörelse i faktiskt navigerbar korridor. |

**OBS** F1 är en diagnostisk animationsvisare, inte ett kommando som ger spelaren kontroll över den egna soldaten. Spelaren styr fortfarande endast skyttet i normalt arkadläge. `F12` skuggor och `F11` profilering finns kvar.

## Verifierat här

- **60/60 medlevererade regressionstester** godkända, inklusive 10 nya skelett-/skuggsamplings-/markkontakt-/GPU-draw-/hindertester.
- Shaderkompilering och programlänkning i **Mesa/EGL OpenGL 3.3**, inklusive båda nya GPU-benshaders och befintliga skuggmaterial: **9 program** länkade.
- GPU-riggen har byggts med fake-GL-kontext för att kontrollera resident data, VBO-struktur, en draw call per fiende, benuniformer och resursfrisläppning. **Verklig rendering på GTX 1070 är ännu inte verifierad.**
- Isolerat CPU-test med **tre figurer**, samma process/samma dator som testerna: gammal procedurtransformering cirka **8.3 ms/bildruta**, ny benpalett cirka **0.7 ms/bildruta**. Dessa siffror omfattar INTE OpenGL-teckning, hela spelets frame, eller GTX 1070. De utgör **inte en verifierad FPS-vinst**.
- Den faktiska V3.9.1 snabbhopps- och streamingtestsviten fortsatt godkänd.

## Nästa utvecklingsordning

1. **NOW: Testa V3.9.3 i den faktiska OpenGL-/GTX 1070-miljön.** Videofil eller skärmbilder av F1-poser, F11 + F12. Fixa huvud-/benvinklar och renderingsfel utifrån den verkliga bilden; ingen gissad realism.
2. **NEXT: Äkta konstnärsriggad GLB med animationer.** Inför glTF 2.0-parser, inverse bind matrices, 4 weights/vertex, klippinterpolation/retargeting, anim-layer-masker, och enkla fotplantnings-/IK-justeringar. Importera lagligt/licensmässigt verifierat assetpar och kvalitetstesta mot skjutbanans perspektiv. Bygg vidare på benpaletten, ersätt inte EnemyAgent.
3. **NEXT: Animation-state och fysisk rutt.** Ställning, vapenpose, känsla (rädd/trött) och huvudspaning som separata blandbara kanaler; faktiska positioner, sikt/penetration, objektvolymer och fotsteg måste använda samma världstillstånd.
4. **NEXT: Verkliga skydd/skyl och AI-val.** Jord/sten stoppar kulor, duk skymmer men stoppar inte, lådor delskydd; soldaten väljer skydd och skjutvinkel efter den faktiska layouten. Testa skott mot synliga renderade fiender från skottfrysta snapshots.
5. **LATER: Grafisk finishing.** När modellen är anatomiskt rätt och GPU stabil: PBR roughness, smuts, slitage, förbättrade skuggkartor, dynamiskt explosionsljus, dimma, ljud och våta miljöer. Mät CPU/GPU och undvik FPS-regression.

**Git:** ingen commit, push eller merge. **Skjutbanan:** ingen fysisk accuracy-förändring.
