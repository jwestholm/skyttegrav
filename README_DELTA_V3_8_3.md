# Skyttegrav V3.8.3 – streaming och omstart (granskningsfix)

**Bas:** V3.8.2. **Filer i deltat:** `trench_3d_test.py`, `tests/test_v383_streaming_restart.py`, denna README och uppdaterad testplan.

## Tre verkliga problem i V3.8.2

1. En färdig CPU-genererad chunk kunde **kastas bort** när `ready`-kön var full efter 0,5 sekunder, men dess ID låg kvar i `pending` och beställdes aldrig igen. V3.8.3 väntar med backpressure och släpper endast resultat vid stopp eller generationsbyte.
2. `R` kunde lämna redan beställda fjärrchunkar i arbets-/resultatköerna. En generationsräknare och köinvalidering prioriterar den nya startpositionen. Gamla svar ignoreras och får inte ta bort aktuella `pending`-ID:n.
3. `R` återställde inte fullt ut kameravinkel, kroppshöjd, manuell/auto, pausläge och visuella indikatorer. En ny omstart börjar konsekvent på 0 m, stående, AUTO, opausad. Startchunkens CPU-mesh behålls (~några MB) för att återställa synlig mark utan att behöva bygga den på nytt synkront.

## Avgränsning

- **Ingen ändring** av `make_chunk`, utomhusterrängen, SoldierBrain, fiendesystemet, 3D-träffzonerna, explosionshändelserna, material eller GLSL.
- Inga nya beroenden.
- Inga ändringar i Skjutbanan eller dess fysiska träffdetektion.
- V3.8.3 är **inte** verifierad visuellt på GTX 1070. Senast användarprovad version är ungefär V3.4.

## Verifiering

- **103 av 103** offline-tester passerade i fem separata körningar (98 befintliga och 5 nya).
- Nya tester pressar en **full resultatkö > 0,5 sekunder**, omstart med kvarvarande gamla chunkjobb, en gammal genereringsrespons som delar ID med en ny, samt gammalt paus-/huvud-/kameratillstånd.
- Fem shaderprogram kompilerade och länkade via Mesa/OpenGL 3.3 (oförändrade källor).
- Python-syntaxkontroller.
- CPU/worker-systemet testat utan riktig GPU. Verkliga frametimes måste mätas hemma.

## Installation

På V3.8.2 i din fungerande Skyttegrav-testkatalog: packa upp `DELTA_skyttegrav_v3_8_3_streaming_restart_fix.zip`, skriv över filerna och kör `python3 trench_3d_test.py`.

Alternativt: lägg `UPGRADE_skyttegrav_v2_4_to_v3_8_3.zip` direkt ovanpå **V2.4** (med befintliga 13 bastexturer). Installera då **inte** V2.5–V3.8.2-deltona först.

## Nästa risker att hålla ögonen på

- Python-chunkgenerering tar sekunder och kör i en CPU-tråd under GIL; 400 FPS i genomsnitt utesluter inte enskilda frametime-spikar.
- Skottens skyddskontroll för fiender använder fortfarande en konservativ 2D-proxy, inte ett exakt raycast mot den visade 3D-meshen.
- SoldierBrains siktbedömning vid hörn/dugouts är ännu delvis heuristisk, inte faktisk 3D-siktanalys.

Inget är committat/pushat till `dev` eller `main`.
