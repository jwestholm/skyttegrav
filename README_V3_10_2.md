# SKYTTEGRAV V3.10.2 – Trees, Fallen Timber & Frame Pacing

**Bas:** V3.10.1 (fristående Python/Pygame/ModernGL). Fast seed 1944. Ingen Godot och ingen Skjutbanan-integration.

## Praktiskt

- Mer varierade yttre träd: barrträd med nivåindelade, ojämna grenkransar, lövträd med spruckna asymmetriska kronor och kala krigsskadade stammar. Stammarna står mot den **faktiska** ute-terrängens höjd, inte en separat gissad yta.
- Nedfallna korta stockar, avbrutna grenar och kvistgrupper längs skyttegravens **kanter**, deterministiskt ur seed. De ligger lågt, undviker korsningar och schemalagda hinder, och skapar ingen ny osynlig kollision mitt på gångvägen. Gamla rutt- och hinderregler förblir oförändrade.
- Foliage-material har subtil världsbaserad färgvariation i befintlig shader, utan ytterligare texturer, transparens eller draw calls. Blad har material-id 6 och är fortsatt **icke-ballistikblockerande**.
- Terränggenereringen går normalt i en **separat spawned Python-process**, inte i en tråd som slåss med renderloopen om GIL. Worker-tråden koordinerar befintliga `todo`/`ready`-köer och förbereder ballistic triangles. Bara Pygame/GL-huvudtråden laddar upp GPU-buffertar. Inga ändringar av 450m-safe-jump, snapshot/collision eller AI.
- Trådvarianten finns kvar som fallback för miljöer där processen inte kan starta samt för direkt jämförelse via `SKYTTEGRAV_MESH_WORKER=thread`.
- `F11` rapporterar nu både terrängbyggarens läge och jämför CPU-ramtid under **rörelsebyte** mot stadig rörelse. Den redovisar **inte** GPU-tid; jämför gärna `F12` skuggor på/av för att isolera GPU-kostnad.

## Installation

Packa upp ZIP-filen i roten av `~/infinite_trench_3d_test/` och skriv över. Alla medföljande Python-filer är kompletta (inga install/patch-script). Egna tidigare Poly Haven-texturer och traces berörs inte. Kör:

```bash
cd ~/infinite_trench_3d_test
python3 -m unittest discover -s tests -p 'test_v*.py' -q
python3 trench_3d_test.py
```

För kontroll mot den tidigare GIL-baserade byggtråden, på samma seed och samma maskin:

```bash
cd ~/infinite_trench_3d_test
SKYTTEGRAV_MESH_WORKER=thread python3 trench_3d_test.py
```

Standard är process. Den gamla varianten bör bara användas för felsökning eller om process-starten inte fungerar.

## Prestandaundersökning

Isolerat benchmark, samma riktiga chunk 0 med fake rendering och en 5ms väntande huvudloop:

| Byggmetod | Tid första chunk | p99 huvudloopintervall | värsta intervall |
|---|---:|---:|---:|
| Gammal tråd | 3.64 s | 145 ms | 228 ms |
| Spawned separat process | 3.56 s | 5.18 ms | 21.56 ms |

Detta är **inte** FPS på GTX 1070, utan reproducerad Python-scheduling och dataleverans. Chunkmesh-storlek vid 0m: V3.10.1 207 624 vertices (7.13 MiB), V3.10.2 204 738 vertices (7.03 MiB). Vid 400m: 186 216 → 179 928 vertices; vid 960m: 165 744 → 167 184 vertices. Terränggenereringen i sig tar fortfarande flera sekunder/chunk. Den separata processen prioriterar **jämn FPS**, inte kortare total laddningstid.

## Regressioner och status

- 127/127 automatiska offline-tester passerar (121 tidigare + sex nya).
- Alla elva befintliga OpenGL 3.3-program kompilerar och länkar mot Mesa/EGL.
- En riktig 80m-terrängmesh och WorldShotMesh verifierades i nya tester.
- En riktig separat worker-process och queueleverans benchmarkades med samma generering. Processen delar inte SDL/OpenGL-kontext med huvudprogrammet.
- **Ej verifierat ännu:** Visuell trädrealism, FPS/frametimes och processlivscykel på användarens GTX 1070. Offline-tester verifierar inte spelupplevelse.
- **Oförändrat:** SoldierBrain-beslut, fiendestrider, träffsfärer, triangelbaserad skottocklusion, 450m-hoppet och Skjutbanans separata träffdetektion.

## Testa på GTX 1070

1. Starta. Terminalen ska visa `Terrängbygge: separat process (spawn)`. Spela och tryck F11. Notera särskilt p95/max under ett rörelsebyte samt `gpu_upload=...ms`.
2. Kör gärna en andra gång med `SKYTTEGRAV_MESH_WORKER=thread` och samma seed och sträcka. Jämför upplevt hack och F11-output.
3. Prova 450–1000m debughopp och återbesök. Inga tomma områden får visas, även om laddning tar tid.
4. Bedöm träd ovanför skyddsvallarna och nedfallna kvistar längs golvkanter. De får inte sväva, flyta över gångvägen eller dölja soldater orimligt.
5. Prova fiendeskott genom öppningar och första dugouten vid 64m. V3.10.1-beteende och skottgeometri ska vara oförändrade.
6. Med F12 skuggor av/på: om hack kvarstår i `draw`, är GPU/skuggpass en möjlig separat flaskhals som behöver verkliga frametimes.

**Nästa steg:** utvärdera faktisk GTX 1070-prestanda och bestäm om vi behöver GPU-instansiering/LOD för träd, samt verkliga licensierade skogs-/barkmaterial. V3.10.2:s procedurträd är ett steg mot trovärdigare siluetter – inte fotorealistiska 3D-skanningar.

Ingen commit, push eller merge utförd.
