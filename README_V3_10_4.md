# SKYTTEGRAV V3.10.4 – Träd, bark, bladskuggor och jordmaterial

**Bas:** V3.10.3 SAMLAD. Detta paket innehåller **hela V3.10.3-filsamlingen och alla nya ändringar**, så inga mellanversioner behöver installeras. Även V3.10.0–3.10.2 finns med via V3.10.3. Extrahera i `~/infinite_trench_3d_test/` och skriv över. **Ingen Godot, ingen Skjutbanan-integration, ingen Git-ändring.**

## Praktisk förändring

- **Närmre träd:** stammen har rotutvidgning, avsmalning, små böjar och rundade ytnormaler; trädtoppen byggs med separata synliga grenar i stället för enbart grönaktiga klot.
- **Lövverk:** korsade kort med transparenta löv-/barrsilhuetter (4 varianter i en medföljande 1024×1024-atlas), med alpha-test i GLSL. Korten sitter i riktiga tre-dimensionella grenkluster, inte som ett stort kameravänt plakat. Det är en procedurvisualisering, **inte ett fotogrammetriskt träd**.
- **Skuggor:** exakt samma utskurna bladform i solens, månens och lampans depth-pass. Samma GPU-VBO som tidigare; inga nya material-draw-calls eller skuggpass.
- **Material:** nya lokalt genererade barktexturer och matchande OpenGL-normalmappar för tall och ljus lövträdsbark. Om redan installerade Poly Haven-filer finns använder spelet dem före våra nya fallbacks.
- **Sidogångar/dugouts:** jordskärningar (`layer 20`) använder world-space triplanar färgprojektion i stället för uppsträckt per-polygon UV. Det är en **shaderförändring**: terräng-, skott-, sikt- och navigationsgeometri ändras inte av den här materialkorrigeringen.
- **Skjutlogik:** `layer 27` (blad/barrkort) räknas uttryckligen som **skyl, inte skydd**. Jord, större stockar och stenar fortsätter att blockera enligt samma exakta trianglar som i V3.10.0.
- **LOD:** nära träd har flest gren- och bladkort; mid/far billigare silhuetter. Det är fortfarande V3.10.3:s **genereringsstyrda LOD**, inte dynamiskt kamerabyte. Ingen ny trädkollision/nav-hinder introduceras.

## Nya filer

`assets/trees/foliage_cards.png` (1024 RGBA-atlas), `pine_bark.png`, `pine_bark_nor_gl.png`, `willow_bark.png`, `willow_bark_nor_gl.png`, samt det *valfria* skaparskriptet `generate_tree_materials.py`. Texturerna är lokalt skapade till detta projekt, utan nedladdad tredjepartsmodell.

## Testa i spel

```
cd ~/infinite_trench_3d_test
python3 trench_3d_test.py
```

1. Titta på de första träden i `forest` och vid skyttegravens krön: särskilt barkens sprickor, öppna grenar, löv/barr med hål och färgnyanser. F7/F8 ändrar dimma.
2. Kontrollera öppningen till första sidogången vid ~64 m: jordytan bör nu ha mindre uppsträckta texturmönster. Observera hörnkiken; dess timing är oförändrad från V3.10.1.
3. Testa att skjuta fiender som syns bakom lövverk och grenar: blad ska inte ge ett nytt osynligt stopp. Solida stammar, plank och jord ska fortsätta stoppa enligt synlig geometri.
4. F11: jämför FPS/frametimes nära träd, vid animationstillståndsbyten och under snabba hopp. F12 stänger av skuggor för en prestandajämförelse.
5. Fortsätt till 450–1 000 m: kontrollera streaming och att vegetation inte dyker upp i sidogångarnas öppningar.

## Verifiering i denna leverans

- Python kompilerar; ZIP:ens CRC och ren uppackning kontrollerade.
- 8 nya, riktade trädkontroller godkända (atlas, barknormaler, geometrisk LOD, determinism, skottpenetration, alpha-skuggkontrakt).
- Ytterligare riktade regressionstester från V3.10.0–V3.10.3 godkända: totalt **35/35 i de fem utvalda testmodulerna** (modulerna körda var för sig eftersom vissa gamla testmoduler laddar om Pythonklasser).
- OpenGL 3.3 headless på Mesa/EGL: **11/11 shaderprogram länkade**, inklusive shader-uniforms för de tre canopy-pass som behöver dem.
- Första 80 m: V3.10.3 207 786 vertices; V3.10.4 203 814 vertices (samma seed, isolerad CPU-generering). Bakgrundsgenereringen tar dock något längre tid i den begränsade testmiljön; det är **inte ett FPS-resultat**.
- Det fullständiga äldre testpaketet slutfördes **inte** i den här miljön: ett separat streamingtest fastnade. GTX 1070, materialutseende och bildrutetider kräver fortsatt live-test.

## Kvarvarande realismarbete

**NOW:** validera V3.10.4 visuellt/F11 mot V3.10.3, rätta eventuellt bladkortens storlek/densitet.
**NEXT:** verkliga licensverifierade GLB-träd, separat trädmesh, kamerastyrd LOD med hysteresis och GPU-instancing, bättre texturmaterial vid portalträ/skärningar.
**LATER:** samma dynamiska LOD-ramverk till stenar, lådor, sandsäckar, soldatprylar; animationer och verkligt riggade humanoider.
**FUTURE:** filmisk fotorealism, stabil 60 FPS på GTX 1070, en dag integration med Skjutbanan efter särskilt beslut.

**OBS:** Detta är ett visuellt uppgraderingssteg och ska inte påstås vara redan fotorealistiskt. Det rör inte SoldierBrain, EnemyDirector eller GameEngine.
