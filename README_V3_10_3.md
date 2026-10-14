# SKYTTEGRAV V3.10.3 – Tactical Framing & Bends

**Bas för detta paket:** V3.10.2 (Python/Pygame/ModernGL, seed 1944). Inget Godot och ingen Skjutbanan-integration.

## Varför

Skotten koncentreras i bildens centrum eftersom tidigare fiender oftast stod ±0,12–0,18 m från rutten. En central kameravinkel plus SoldierBrain som stannar rakt framför dem gjorde att samma del av den framtida fysiska tavlan riskerade att belastas kraftigt.

## Implementerat

1. **Äkta laterala fiendepositioner:** De fyra första fienderna har samma ruttmetrar och profiler som tidigare, men nya sidopositioner. Senare fiender får seed-stabila positioner cirka 0,30–0,64 m från mittlinjen åt båda håll i stället för växelvis ±0,12 m. Befintlig `enemy_position` begränsar fortfarande kroppen till korridorens fysiska väggfrigång och navigerar runt lådor/ras.
2. **SoldierBrain – förberett skottläge:** Vid verklig, redan engagerad fiende kan den befintliga hjärnan långsamt gå till en motsatt väggnära position. Förflyttning och huvudvinkel är tidsfiltrerade, med företräde för befintliga hinder- och korsningsmanövrer. Efter kontakt glider han tillbaka till normal rutt. Det finns ingen ny navigationsklass eller sikthjälp.
3. **Ingen automatisk centrering:** En liten, medveten huvudscan (upp till 0,22 radianer i ett fullt utvecklat kontaktläge) ger ytterligare varierade, perspektivkorrekta vinklar. Siktlinjen mot fienden kan bli mer utmanande. Skottets pixelkoordinater ändras inte.
4. **Böjligare långa sträckor:** Efter 430 m tillkommer en mjuk, lågfrekevent kurvatur ovanpå samma `turn_for_meter`/`route` som allt annat använder. De första 430 metrarna är identiska med tidigare *vad gäller mittlinjens geometri*. Riktiga världschunkar och shot-mesh följer samma nya rutt och frysta geometri; inga separata visuella kamerafusk-böjar.
5. **F11-diagnostik:** Vid aktiverad profilering samplas potentiellt synliga fienders projicerade, aktuella världspunkter och skrivs ut som `PROFILE ENEMY PROJECTED X left/middle/right`. Statistiken är sessionsbunden och diagnostisk, inte samma sak som fysiska registrerade skott. Den är varken aim assist eller hitbox-expansion.

## Vad är medvetet oförändrat?

- Spelarens skott sker genom samma frysta MVP, kroppsträffvolymer och V3.10.0-triangelbaserade skottblockering.
- Skjutbanans fysiska accuracy är inte testad, ändrad eller kopplad till detta spel.
- Terrängstreaming via separat process, säker hoppladdning, dugout-/hörnobservation och shadow shaders.
- Svårighetskurva och fiendens skotteffekter.
- Kamerans FOV och världens kollisions-/väggdefinitioner.

## Verifiering

- 135/135 Python-unittest offline-testfall passerar inklusive åtta nya tester (räknat vid skapandet).
- Första fyra mötenas nya flanklägen hade LOS enligt befintlig siktmodell cirka 8 m före fienden.
- Riktig `make_chunk(960)` genererades som ändlig Nx9-mesh.
- 100 senare fiender ger sidopositioner på båda sidor om mitten och en förenklad perspektivprojektion ger spridning i skärmen; **detta är inte en faktisk mätning av spelklippet**.
- Originalets shaderkod är oförändrad. Ingen OpenGL-rendering på GTX 1070 är verifierad i denna miljö.

## Installation

Packa upp direkt i roten av `~/infinite_trench_3d_test/` **bara om din lokala utgångsversion är V3.10.2**. Paketet består av kompletta filer (ingen patch/installer), men ett fullständigt överskrivande paket är **inte säkert ovanpå en lokalt ändrad V3.10.4** utan att först göra en diff/rebase. Använd helst en testarbetskopia och behåll/committa dina lokala ändringar på egen branch före ersättning.

```bash
cd ~/infinite_trench_3d_test
python3 -m unittest discover -s tests -p 'test_v*.py' -q
python3 trench_3d_test.py
```

## Provning på GTX 1070

1. Kontrollera första fyra fiendemötena. Fienden ska kunna stå till vänster och höger, och kameran ska aldrig teleporteras för att skapa variation.
2. Slå på `F11`. För långsiktig testning, anteckna `PROFILE ENEMY PROJECTED X left/middle/right` vid spel och jämför med tidigare version. Tänk på att fördelningen påverkas av vilka fiender som blir observerbara och hur länge.
3. Hoppa till 600–1 000 m och kontrollera att böjarna verkligen känns varierade och att skyttegraven, fienderna, träden och hårda väggar sitter ihop över chunkgränser. FPS bör mätas med F11.
4. Kontrollera att en fiende genom en synlig öppning går att skjuta, men aldrig genom en solid jordvägg. Kolla också att sikten fortfarande fungerar med fiender nära en sidovall.
5. Kika vid första sidogången. V3.10.1-beteendet är återanvänt utan att utökas.

## Öppet / nästa

- **Fysisk testning**: mät faktisk använd yta på projektionstavlan efter många skott, innan vi påstår minskat mittslitage. Använd F11-projektionsstatistik som kompletterande data, inte som sanning om fysiska skott.
- **Navigation**: mer systematisk optimering av vilka skydd som kan nås och vilka skottlinjer som verkligen är exponerade; nu är det ett försiktigt vägg-läge ovanpå befintlig steering.
- **Variation**: framtida hinder-/LOD-/cover- och kamerarörelser ska valideras offline och i riktig Pygame-rendering separat.

Ingen Git-commit, push eller merge utförd.

## NEXT – patruller ovanför vallen (beslut efter användarens testidé)

**Inte implementerat i V3.10.3.** En framtida patrol-/nedhoppsfunktion ska återanvända `EnemyAgent`/`EnemyDirector` och `SoldierBrain` och först inventera verkliga övervallens gångytor samt möjliga landningsplatser. Ingen separat enemy-AI eller teleport.

- Fienden ska existera i världen inom rimligt visnings-/höravstånd, röra sig längs en giltig stig ovanför skyttegraven, synas om geometrin tillåter och kunna upptäcka spelaren endast via faktisk hörsel/sikt. Höjdskillnad, terräng och jordvall måste beaktas.
- Flera rättvisa utfall ska vara möjliga: patrullen passerar utan att upptäcka spelaren, SoldierBrain hukar och väntar och kan krypa obemärkt förbi, patrullen upptäcker spelaren och väljer att öppna eld eller hoppa ner, beroende på fri och säker landningsplats. SoldierBrain får inte använda fiendeinformation som inte upptäckts.
- Nedhopp är en verklig kontinuerlig 3D-rörelse med visad förberedelse, synlig landning och återhämtning. Den synliga modellen, skuggan, line-of-sight och frysta träffgeometrin ska dela samma aktuella pose; ingen direkt teleporterad fiende.
- Akustik/visibilitet och hot ska vara evidensstyrda; inga bakom-väggen-dödsfall. Huvudbanans spelkänsla och fysiska projektionens spridning ska bibehållas. Kräv regression för oupptäckt patrull, korrekt terrängocklusion, giltig landning, rimlig frekvens, FPS och distansbaserad svårighetsgrad.
- Begränsa antal aktiva ovanför-vallen-patruller runt spelaren. Distant AI kan sova/despawna och visual LOD ska vara separat från hit geometry. Seedad slump ger reproducerbara testmöten.

## Källvariant och installationssäkerhet

De kompletta filerna här är baserade på **V3.10.2** med V3.10.3-förbättringarna. Om den lokala arbetskopian innehåller separata, nyare ändringar (exempelvis en egen V3.10.4), jämför/diffa först. En direkt överskrivning utan jämförelse kan förlora lokala förbättringar. Filmernas versionsetikett har tidigare inte alltid överensstämt med faktiska filer; kontrollera din arbetskopia.
