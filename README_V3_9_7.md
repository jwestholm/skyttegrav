# SKYTTEGRAV V3.9.7 – Observera sidogångar + GLB-skelettpreview

**Bas:** befintlig Skyttegrav V3.9.6 (i sin tur baserad på `dev`, commit `59eca659d1bba2389eb231b9672f883383dd5e9b` / "Old model"). Inget Godot. Ingen Skjutbanan-koppling. Ingen Git-commit/push/merge.

## Installation – kompletta filer

Packa upp ZIP:en **i roten av** ditt befintliga `~/infinite_trench_3d_test/` och skriv över befintliga filer. Den innehåller fullständiga Pythonfiler, kompletta tidigare materialtexturer samt tester – **inga patchskript eller installers**.

```bash
cd ~/infinite_trench_3d_test
python3 -m unittest discover -s tests -p 'test_*.py' -q
python3 trench_3d_test.py
```

**Provkörning**

1. Starta normalt, autoaktiverat. När SoldierBrain närmar sig en okänd sidogång ska han bromsa, kika fram, dra sig undan, bedöma läget, lyssna/hämta andan en kort stund och sedan **fortsätta på huvudvägen**. Han ska **inte automatiskt gå in i varenda dugout**.
2. Samma gamla fiender vid huvudvägen, skott, animationer, F1-labb, R-omstart, F12-skuggor och `↑`/`↓` snabbspolning fungerar som tidigare. Testa gärna några av de senare korsningarna och dugouts med `↑`.
3. `F11` visar FPS och frametimes; notera särskilt om långsam generering följs av GPU-upload-spikar. Inget nytt FPS-mått har tagits på GTX 1070.
4. Det finns fyra deterministiska sidoutrymmen: **bunk/sovplats**, **förråd**, **improviserad sjukvård** och **sambandsplats**. Lokal T/Y/X-skyltning och tre olika inredningsvarianter i takförsedda huvudtunnlar. Samma seed = samma detaljer.

## SoldierBrain: observation respektive genomsökning

V3.9.6 hade en sannolikhetsstyrd `_depth_to_check()`, där soldaten kunde marschera in i sidogångar **utan observerad fiende**. V3.9.7 skiljer mellan:

- **Observera:** approach → edge → peek → retract → assess → `branch_rest` → huvudvägen. Detta är standard när inga konkreta observationer finns.
- **Genomsök:** den befintliga, fysiskt sammanhängande navigationen in i sidogången används endast när SoldierBrain fått en explicit lokaliserad indikation: `report_branch_evidence(index, kind, confidence)`. `kind` måste vara `seen_enemy`, `localized_sound`, `movement` eller `friendly_report`; konfidens minst **0,65** krävs.

**Avgörande begränsning:** EnemyDirector spawnar fortfarande fiender på **huvudvägen**, inte inne i dugouts. Ingen automatiserad sidogångsdetektor har byggts. Med de nuvarande gameplay-data kommer alltså alla sidogångar att **observeras utifrån**. Kommandot är en krok för verkliga framtida händelser; random seed skapar inte imaginära fiender. Vi har inte byggt en parallell AI eller ett nytt globalt navigationssystem.

## GLB: riktig GPU-skinning som frivillig F1-preview

Ny modul `gltf_actor.py` innehåller en begränsad glTF 2.0 GLB-läsare och ett nytt ModernGL-renderpass med:

- GPU-skinning av ett enda riggat mesh-node, upp till **4 benvikter per vertex**, **1–128 ben** via liten RGBA32F joint-palett på GPU:n (inte CPU-skinning av varje vertex).
- Inläst mesh/indices/normals/UV samt inbakad PNG/JPEG basfärg; animationer via glTF `translation`, `rotation`, `scale` och kvaternion-SLERP. Klippövergångar blandas över cirka 0,38 sekunder; vid avbrott utgår de från sista visade ställningen. `dead` är inte looping.
- **Samma sol-, mån- och lamp-skuggresurser som den befintliga renderaren**, så F12 fungerar även i preview.
- **Avsiktlig avgränsning:** Ny GLB används **bara i F1-demot**, inte i riktig strid. Hitboxarna är fortfarande kalibrerade för den gamla procedursoldaten. De får inte sluta motsvara det renderade målet.

Ingen professionell soldatmodell ingår i denna ZIP. Det vore fel att kalla det en ny fotorealistisk soldat utan asset. För att prova en egen licensierad riggad GLB med **inbäddade animationsklipp**:

```bash
mkdir -p ~/infinite_trench_3d_test/assets/characters
cp /sökväg/till/din/riggade_modell.glb ~/infinite_trench_3d_test/assets/characters/soldier.glb
```

Starta därefter normalt och tryck `F1`. Om modellen stöds visas den **bara i labbet**. Vid filfel faller spelet tillbaka till vår gamla GPU-soldat och skriver ut orsaken i terminalen. Utan fil används gamla soldaten som förut. Tänk på att en GLB utan rätt animationsklipp kan visa samma idle-rörelse för flera F1-kommandon.

**CC0-alternativ för egna tester:**

- Kenney Animated Characters 3: <https://kenney-assets.itch.io/animated-characters-3> – CC0-karaktärer med idle/run/jump enligt utgivaren. Kontrollera exportformat och att animationerna ligger i samma GLB.
- Quaternius Universal Base Characters: <https://quaternius.com/packs/universalbasecharacters.html> – CC0 med humanoidrigg, men glTF-filer behöver normalt konverteras/packas till GLB.
- Quaternius Universal Animation Library: <https://quaternius.itch.io/universal-animation-library> – separat CC0-animationsbibliotek. Dess animations-GLB behöver **retargetas/mergas till samma rigg**. Vi har **inte** implementerat automatisk retargeting.

Första importen är konservativ: ett riggat mesh-node, inbakade materialtexturer och animationer i en GLB. Externa `.bin`/PNG, flera separata skinnade mesh-noder och specialextensions är ännu inte stödda. CUBICSPLINE samples approximeras till linjär interpolation i preview. Detta är inte ännu en färdig karaktärspipeline med IK, fotkontakt eller fotorealism.

## Verifiering gjord i byggmiljön

- **92/92 offline-regressionstester** godkända: befintliga 80 plus 12 nya tester för beslut vid sidogångar, deterministiska inredningar, GLB-accessors, 4-bensvikter, animation, övergångar, fake-GL draw/shadow och fallbacks.
- **11/11 OpenGL 3.3-shaderprogram kompilerade och länkade i Mesa/EGL**, inklusive introspektion av alla skugg-uniformer som ModernGL behöver. **Ingen NVIDIA/GTX 1070-test** här.
- Realistisk generator körd på **0–80 m (207 360 vertices, ~3,0 s)** och **960–1040 m (165 744 vertices, ~2,4 s)**. Båda hade ändlig och giltig geometri. Dessa är offline CPU-värden på testmiljön, **inte FPS**.
- Inga förändringar i den fysiska träffdetektionen, inga externa nätverksförbindelser, inga ändringar på `dev`.

## Nästa steg

1. Testa bildkvalitet och FPS för olika korsnings-/dugoutstilar, och säkerställ att observation utan intrång är spelmässigt rimlig.
2. Importera **en verifierat licensierad, faktisk humanoid-GLB med animationsklipp**, justera orientering, skalning, fotkontakt och material i F1; profiler GPU-lasten.
3. Implementera geometrisk jämförelse mellan den renderade kroppen och skottfrysta 3D-träffvolymer **innan** den nya modellen får användas i riktig gameplay.
4. När riktiga sidogångsfiender/sound events tillkommer: mata SoldierBrain med faktisk lokaliserad evidens. Då kan han söka av **just den sidogången**, inte alla.
5. Profilera streaming vid upprepade 25-metershopp; tunna inte ut den oändliga banan på chans. Prioritera GPU-upload-kostnad och bounded cache när data visar en flaskhals.
