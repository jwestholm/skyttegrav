# Skyttegrav V3.9.5 – rörelse och första filmiska materialpasset

**Bas:** V3.9.4 (inklusive V3.9.1 atomic streaming, V3.9.2 sol/måne/lamp-skuggor, V3.9.3 GPU-skelett, V3.9.4 dödsanimation). Alla levererade Pythonfiler är **kompletta ersättningsfiler**. Ingen installer/patcher, ingen commit eller push.

## Praktiskt – vad blev bättre?

- **F1 `stand` = levande idle.** Andning, små tyngdförskjutningar i bålen och diskret huvudspaning; fötterna står kvar.
- **F1 `walk` och `run` är olika.** Gången har lägre stegfrekvens, kortare steglängd, mindre knälyft/vertikal studsrörelse och mindre motpendling i armarna. Spring har snabbare/längre steg och mer framåtlutad överkropp. Labbsoldaten går/springer **på stället** för att demonstrera rörelsecykeln utan att flytta kameran eller kringgå världens navigation.
- **F1 `fire`:** upprepad kort rekyl som för händerna och geväret bakåt; en demonstrativ mynningsflamma var 1,05 sekunder. Detta är *endast visuellt*; inga osynliga skott eller extra spelträffar skapas.
- **Vanliga fiender:** GPU-riggen reagerar också på det riktiga `EnemyAgent.state == firing` med en mjukare axel-/gevärsrekyl. Gångintensitet utgår fortsatt från faktiskt färdade meter; separat utjämnad verklig hastighet ger en hastighetsberoende motpendling utan root motion.
- **Första miljömaterialpass:** försiktig, världskontinuerlig glans på *våta fläckar på jordgolvet* beroende på solriktning, ytans normal och skugga. Den är begränsad till golvshadermaterialet; inga nya per-frame texturer, VBO-uppladdningar eller nya skuggpass tillkommer.
- Varje ny F1-gest börjar från startfasen, så demonstrationen inte hoppar in i mitten av första rörelsen.

## Installation

Packa upp hela ZIP-filen direkt **i roten av ditt befintliga Skyttegrav-repo** och skriv över medföljande filer. Behåll andra `assets/` och dina egna inställningar.

```bash
python3 trench_3d_test.py
```

Kontrollera i terminalen att **`V3.9.5: GPU-skelett`** visas. Om GPU-riggen inte startar ska spelet använda äldre renderare, men det nya F1-animationsutseendet kräver GPU-riggen.

## Test på GTX 1070

1. **F1 `stand`:** låt figuren stå i minst 5 sekunder. Leta efter andning, subtil sidovikt, huvudspaning. Figuren ska inte glida längs golvet.
2. **F1 `walk` och `run`:** växla mellan dem och vänta 3–4 sekunder i vardera. **Löpning ska tydligt ha längre och snabbare steg** och mer armrörelse. Båda står kvar på samma världsposition i labbet.
3. **F1 `aim` och `fire`:** sikte ska hållas stabilt; `fire` ska rycka tillbaka geväret varje ~1 sekund och visa en kort mynningsflamma.
4. **Normalt spel:** en vanlig fiende ska röra sig i den verkliga korridoren, skjuta och dö som i V3.9.4. Ingen skillnad i hur du registrerar musklick/träffar.
5. **F12 och F11:** kontrollera att skuggorna följer fienden och att frametimes/FPS förblir rimliga. FPS måste mätas på din maskin – offline shader- och enhetstester bevisar inte 60 FPS.
6. **Piltangent till 450 m, sedan R:** V3.9.1:s streamade landning och omstart ska bete sig som tidigare.

## Verifiering och avgränsningar

- 69/69 offline-regressionstester inklusive nya F1-poses, verklig firing-state, shaderavgränsning till golvet och AI-/terrängregressioner.
- 9/9 OpenGL 3.3 shaderprogram kompilerade/länkade i Mesa/EGL.
- Ingen riktig GTX 1070- eller fysisk projektor-FPS-verifiering här.
- **Ännu inte fotorealistiskt:** detta är en procedurbyggd 16-bens single-influence-modell, inte en filmkvalitetsfigur med muskler, fingrar, mjuk skinning, IK och färdiga motion-capture-klipp. Liggande, spade och död är fortfarande konstnärligt begränsade.
- Solglansen på våt jord är en **liten ljusapproximation**, inte full metall/roughness/occlusion-PBR eller global illumination.
- **Viktigt:** ingen ombyggnad av spelvärldens hitboxes, LoS, fysisk Skjutbana-träffdetektion, score, svårighet eller AI-beslutsregler. Rörelseanimationen ger ingen osynlig root motion och påverkar inte spelarkaraktärens koordinater.

## Nästa stora realismlyft – efter visuell GTX-kontroll

1. **Riktigt licensierat och kontrollerat glTF/GLB-asset** med människotrogen soldatgeometri och mjuk 4-bensviktning per vertex, samt glTF-klipp för idle, walk/run, kneel, prone, reload, firing och dying. Bygg på befintliga EnemyAgent och GPU-skelettet.
2. **Blend trees, additive aim/recoil, IK-fotplantering.** Strikta regler för att animation inte går genom väggar och en invariant koppling mellan renderat mål och fryst skottögonblick.
3. **Fotobaserade PBR-material** för jord, trä, sten, tyg och rost (CC0/öppen licens med dokumenterad källa), följt av färg-/exponeringspass och bättre kontaktsskuggor. Välj och kontrollera GPU/VRAM-budget innan större upplösningar används.
4. **Förfinad näratmosfär:** vatten, jordstänk, rök, dova nedslag, riktat ljud – mät först CPU/GPU frame-time på GTX 1070.

**Git:** inget push, merge eller commit har gjorts. S03 och Skjutbanans fysiska data påverkas inte.
