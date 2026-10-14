# SKYTTEGRAV V3.10.0 – Visual Realism + Shot Consistency

**Bas:** V3.9.9 (samma fristående Pygame/ModernGL-spel), installerbar över befintligt repo. **Seed:** `1944`. **Skjutbanan-integrationen:** pausad. **Godot:** ingår inte.

## Praktisk effekt

### 1. Synligt hål i jordvallen = inte längre en osynlig cylinder

Tidigare använde `Trench._enemy_shot_occluded()` en *separat, grovt uppskattad huvudgångs-/vallproxy* som kunde stoppa ett skott trots att 3D-geometrin visade en öppning. Nu används `shot_geometry.WorldShotMesh`, som får **samma vertexarray som läggs i world-VBO:n**. Segment/triangel-raycast avgör om något faktiskt solidt finns mellan kamerarålen och **närmaste frysta fiendeträffsfär**.

- **Jord/sten/plankor/sandsäckar/lådor:** de *renderade* trianglarna stoppar skott. Inga extra volymer skapas.
- **Buskblad (`layer 6`), vindduk/nät (`26`):** skyl, men blockerar inte skott.
- **Dekorativa lågor (`11`), pölar (`12`):** ingen ballistisk barriär.
- **Trälådor som råkar använda canvas-textur (`9`):** förblir solida. En textur är inte per automatik ett fysikmaterial.
- Ett missat skott som verkligen träffar en solid triangel ger ett litet grus-/trä-/stenstänk *vid den faktiska ray/mesh-träffpunkten* och HUD-text `SKOTT I JORD/TRÄ/...`.
- Ingen aim snap, hitbox-expansion eller ändring av den fysiska träffpunkten.

**Fryst bild:** `FrozenEnemyFrame.world_shot_meshes` sparar referenser till world-occluders för **samma presenterade bild** som fiendens poser. Om nya chunks laddas efteråt används inte deras väggar för det gamla skottet. Både träffar och missars splash använder frame-snapshotet.

**Kvarstående begränsning:** Fienden representeras fortfarande av animerade *träffsfärer* som kan avvika från verkligt skinnad modell på vissa siluettdetaljer. De nya raycasten löser framför allt falsk blockerad skottlinje från grov *world*-proxy. Framtida exakt kroppstriangel-picking kräver en verifierad humanoidmodell/rigg. Fiendens **perceptions-/sikt-AI** använder ännu sin CPU-begränsade approximerade LOS för rimlig FPS. Det är alltså inte ännu ett enda heltäckande sikt-/skyddsfysiksystem. Texture-only mörka fläckar är inte automatiskt fysiska hål.

### 2. Miljöpass – utan nya tunga renderingspass

- Varmare, djupare skymningshimmel och mörkare, mindre vitgrå dimma.
- Filmisk, återhållsam highlight-/mellantonskurva. Värld och fiender får samma efterbehandling.
- Världskoherent mikrosmuts, jordlager, fuktfläckar och mörknande trä; sömlöst över chunkgränser.
- Fler små, seed-stabila golvdetaljer i dugouts: upptrampade vatten-/lerfläckar och trasigt virke; passerbara dekorationer.
- Belysning, befintliga normal maps, dynamiska skuggor och valfria Poly Haven CC0-fototexturer återanvänds. **Inga nya fotografiska filer eller 4K-texturer** ingår. Vill du ha mer fotorealistisk yta: kontrollera redan befintlig `python3 fetch_polyhaven.py --check` och kör separat `python3 fetch_polyhaven.py` när du vill. Det är en *valfri* extern nedladdning, inte ett installationskrav.

### 3. Hörnkik

- Tidigare stopp vid `junction_marker - 2.25 m`, nu **-2.72 m**: cirka 47 cm längre tillbaka.
- Sidoblick kalibrerad till att faktiskt se *in* från den bakre stoppunkten, inte titta 70° för långt genom väggen.
- Fortsatt övervakning vid passage och samma faktiska `report_branch_evidence()`-beslut. Ingen ny falsk fiende i sidogångar.

## Teknik och prestanda

- `WorldShotMesh` skapas i den redan befintliga **CPU-bakgrundstråden** tillsammans med varje chunk. World-VBO/VAO uppdateras fortfarande endast på OpenGL-huvudtråden. **Inga raycast mot terräng körs varje frame.**
- Chunkar från cache återanvänder också beräknad collisiondata. Minnescachen följer befintligt bounded `MESH_CACHE_CHUNKS` och eviktionsregler; presenterad snapshot behåller den gamla referensen tills bilden ersatts.
- *Offline uppmätt* på testmiljön:
  - 0–80 m: 207 624 rendered vertices / 65 702 solid triangles; collisionprep **21,5 ms**; en ray **2,65 ms**, ca 3,88 MiB collisiondata.
  - 960–1040 m: 165 744 vertices / 54 552 solid triangles; collisionprep **16,5 ms**; en ray **1,85 ms**, ca 3,23 MiB collisiondata.
- Det är CPU-mikromätningar; **inte GPU-FPS** på GTX 1070. Testa F11 vid vanlig gång och efter hopp till 1000 m. F12 växlar skuggor. F7/F8 ändrar dimman.

## Installation

Packa upp `DELTA_skyttegrav_v3_10_0_VISUAL_SHOT_FULL_FILES.zip` i `~/infinite_trench_3d_test/` och skriv över filer. **Kompletta Python-filer** levereras, inga patch-/installskript. Behåll övriga `assets/` (inklusive egna Poly Haven-texturer) oförändrade.

```bash
cd ~/infinite_trench_3d_test
python3 -m unittest discover -s tests -p 'test_v*.py' -q
python3 trench_3d_test.py
```

### Viktigaste manuella fall

1. Vid 32 m eller längre fram: sikta på fiende som syns genom **verklig** ojämn öppning i vall – träff om frysta fiendens hit-sphere korsas och ingen solid triangel ligger framför.
2. Samma skott med jord/planka synligt mellan kamera och fiende – ska blockeras, träffmarkering på faktiskt objekt och inte döda fienden.
3. Hängande tyg / buskblad – ska inte ge osynlig kulvägg.
4. Första dugouten runt 64 m: kort stopp **något tidigare**, ordentlig titt, passera med uppsikt, fortsätt på huvudgången.
5. Hopp till ca 450 och 1000 m: samma säkra terrängstreaming som V3.9.9 och ingen kontinuerlig FPS-förlust.
6. Ljussättning: jämför med V3.9.9. Se särskilt på att dimman är mindre urtvättad, att jord/trä varierar och att små våta golvfläckar finns. Med befintliga Poly Haven-texturer blir fotomaterialen bättre.

## Verifiering

- **118/118 offline-tester godkända**, varav 13 nya för exakt solid/canvas/vegetation, frysta bildrutor, riktig missimpact, 2.72m-hörnkik och shaderkällor.
- **11/11 real OpenGL 3.3 shaderprogram kompilerar och länkar i Mesa/EGL**, inklusive world, rigg, GLB-skinning och skuggor.
- Paketkontroll från ren uppackning och ZIP-CRC genomförs innan leverans.
- **Inte utfört:** faktiskt spel/GPU-FPS på GTX 1070; live-fysisk träffdetektion; fotorealism benchmark. Arkadspelsträffar är fortfarande mus-/T-simulerade.
- Ingen push/merge/commit. Inga ändringar i Skjutbanan.

## Nästa steg

1. Verifiera videon och FPS efter denna mesh-baserade skottkonsistens.
2. Mät faktisk fiendekropp kontra animerad skinnad siluett – inför exakt modellträff stegvis, inte aim-assist.
3. För mer filmiskt utseende: säkra riktiga CC0/PBR-fotomaterial med licenskällor, justera exposure och AO på GTX 1070 innan tyngre effekter.
4. Först efter detta: utöka fiende-LOS till samma materiella/triangulära modell med tydlig CPU/GPU-budget och offscreen-observationer.
