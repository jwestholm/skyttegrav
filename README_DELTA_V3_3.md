# SKYTTEGRAV V3.3 – FIRST CONTACT

## Installation

**Bas: V3.2 World Terrain Fix**, med dess befintliga `assets/`, `fetch_polyhaven.py` och tester kvar.

Packa upp ZIP-filen direkt i `~/infinite_trench_3d_test/` och skriv över `trench_3d_test.py`. Deltat innehåller följande ändrade/nya filer:

- `trench_3d_test.py`: liten EnemyRenderer, inputadapter, 3D-ray, fiendens synliga frame-snapshot, fiende-trigger och stopp för SoldierBrain.
- `enemy_system.py`: ren Python-logik för fiender, hot, hit-spheres, stridssekvenser och chunk-nära spawn/despawn.
- `assets/enemies/{uniform,webbing,skin}.png`: **egengenererade**, enkla fallback-texturer, ej externa kommersiella modeller.
- `generate_enemy_textures.py`: valfri deterministisk omgenerering av just dessa tre bilder.
- `tests/test_v33_first_contact.py`: nya regressions-/integrationskontroller.

```bash
cd ~/infinite_trench_3d_test
python3 -m unittest discover -s tests -p 'test_v33_first_contact.py' -v
python3 trench_3d_test.py
```

## Funktion och kontroller

**Testscenario**: de första mötena ligger omkring **32 m, 164 m, 258 m och 384 m**. Sedan finns seedade, glest placerade kontakter längre fram. Spela med **0** för SoldierBrain i autoläge.

- Fienden syns som en *prototypbyggd 3D-soldat* med återanvänt uniformsmaterial, hjälm, ben, armar, väst och ett enkelt vapen. **Inte** en fotorealistisk GLB med skelettrigg.
- Första kontakten startar med en ovetande soldat. När vår soldat kommer nära vänder fienden kroppen gradvis, höjer vapnet, siktar och skjuter med synlig mynningsblixt. Fiendeskotten har **ännu ingen gameplay-skada**.
- Andra typer: **ambush**, **cover** (kan huka sig vid omladdning), **unaware**. **Rush** är endast profil-/AI-grund, ingen färdig väg-/kollisionsstyrd anstormning ännu.
- SoldierBrain **bromsar/stannar på huvudgången** inför olöst fiendekontakt och går ner på knä. Han skjuter aldrig själv. Hotet försvinner inte automatiskt.
- **Vänster musklick på fienden** = testskott i *simulerade Game Space-koordinater*.
- **T** = skjut i exakt bildcentrum (smidig debug för inriktning); ett skott **missar** om ingen träffvolym ligger där.
- **R** återställer resan och fienderna, **Space** pausar, **F7/F8** dimma, **F9/F10** flyttar fönstret, **Esc** avslutar.
- När en fiende får träff spelas en enkel fallen-pose. Liket ligger kvar tills den närliggande encounter-instansen evicteras. Samma fiende kan inte få dubbla träffreaktioner.

## Gräns mot Skjutbanan (kontrollerat mot `jwestholm/skjutbana`, `dev`, 2026-10-12)

**Aktuellt GameEngine-API**:

- `src/engine/scenes/game.py`: `create_game(game_root, viewport)`, `get_hit_regions()` (om implementerat), `on_object_shot_frozen(snapshot)`, `on_frame_presented(timestamp)` och vanlig `handle_event(event)`.
- `src/engine/input/hit_input.py`: `HitEvent.game_x/game_y` är redan **viewport-lokala / game-lokala**, färdigtransformerade koordinater. `HitEvent.is_simulated` visar testkälla. Det är **inte** kamerakoordinater.
- `src/engine/input/hit_regions.py`: `HitRegion`, `object_query_regions(...)`, `hit_context_snapshot_for_shot(shot_id)`, `object_physical_result(shot_id)`.
- `content/games/can_shootout_game.py` demonstrerar `get_hit_regions()`, `on_object_shot_frozen()` och `physical.object_result` från `event_bus` för OBJECT-vägens skottfrysta kontext.
- Vanliga spel, t.ex. `pop_the_balloon_game.py`, använder `hit_input.subscribe(self._on_hit)` och läser `hit.game_x/y`; musen simuleras centralt av `OverlayScene` via `HitInput`, inte av varje spel.

**V3.3 är fristående** och ändrar inte någon av dessa filer. Den har däremot färdiga rena gränser:

1. `EnemyDirector.capture_frame(view_projection, width, height, route_m, position_at, heading_at)` skapar **immutabla 3D-poser + MVP för den renderade bilden**, utan att spara hela världen.
2. `Trench.submit_game_hit(x,y,source='mouse_simulated',frame=...)` använder de exakta viewport-pixlarna för `ray_from_screen()` och närmaste levande kroppsträff. Miss medför ingen eliminering.
3. `Trench.submit_verified_hit_event(hit,frame)` är en **framtida adapter-signatur**, inte inkopplad i Skjutbanan. Den vägrar `is_simulated=True`. Det verkliga verifieringsansvaret ligger utanför den här funktionen.
4. Renderstorleken (`frame.width/height`) är **målbildens faktiska viewport-storlek**. Om GameEngine renderar med annan upplösning än fristående 800×600 måste träffkoordinaten först mappas via den etablerade viewport-/content-transformeringen, inte med godtyckliga skärmpixlar.
5. Vid portning måste den renderade framen och fiendens träffvolymer **frysas på skottets tidpunkt** och knytas till verkligt `shot_id`. Flera senkomna resultat för samma skott måste dedupliceras.
6. Den fysiska kameran och `HitInput`/homografin ska **inte** modifieras, och GameEngine ska fortsätta få en korrekt vald/emitterad fysisk träff, inte bara en orakelkandidat.
7. OBJECT-vägen får inte tolkas som en vanlig `HitEvent`. Den kräver respekt för `physical.object_result` och ett giltigt, fysiskt verifierat beslut mot skottfrysta objekt. Vi bygger den adaptern vid den verkliga integrationen.

**3D-rendering vid integration** är ett separat arbete: Skjutbanan ritar på Pygame-ytan medan testet använder ett eget ModernGL-fönster. Vi behöver planera FBO/offscreen-rendering eller annan medveten integrationslösning. V3.3 försöker **inte** ersätta GameEngine API eller träffdetektor.

## Tekniska val

- Ingen PyBullet i denna version: statiska lokala actors behöver inte rigid bodies ännu.
- Ingen OBJ-per-frame: `EnemyRenderer` skapar delade GPU-bufferar **en gång**, med små transformmatriser per figurdel och frame. En framtida riggad glTF/GLB kan kopplas in som renderer och byta klädmaterial utan att ändra EnemyBrain.
- Ingen fiendeaktivitet utanför närområdet: `EnemyDirector` räknar fiende-ID från ett deterministiskt encounter-schema, aktiverar nära soldaten och evicterar gamla instanser. Eliminerade ID behålls så de inte återuppstår på ett återbesök.
- Grafik- och träffgeometri: enkla, roterade 3D-kroppssfärer; inte ännu en GLB-skeletts exakta bone-hitboxes. Kollisionskontrollen mot jord/befintliga lådor är en **konservativ approximation**, inte komplett per-triangel LOS/depth-picking.
- Fiender kan inte skada soldaten i V3.3. Detta är ett medvetet avgränsat första kontakt-test – inte färdigt strids-/hälsosystem.

## Validation

Kör det snabba första steget:

```bash
python3 -m unittest discover -s tests -p 'test_v33_first_contact.py' -v
```

Testerna omfattar träff/miss, ocklusion, olika fiendeprofiler, träffzonernas världsriktning och pose, återstart, långvarig kontakt som aldrig försvinner utan skott, renderframs-frysning över AI-poseändring, samt fyra encounters med återupptagen SoldierBrain-navigation.

För basens äldre 3D-geometri finns V3.1-/V3.2-tester kvar. Ingen ändring har gjorts i `make_chunk()` eller utomhusterränggenereringen i detta delta.

## Git och begränsningar

- **Ingen commit/push/merge** görs av deltat. När du visuellt har godkänt V3.3 kan du själv uppdatera `dev`.
- **Kräver live-test på GeForce GTX 1070** för att avgöra synlighets-/animeringskvalitet, modellproportioner, frametimes och faktiskt hit-resultat i fönstret.
- Framtida fiender i **sidogångar/dugouts**, lådskydd som exakt skymmer 3D-modellen, välanimerad sprint/närstrid och riggade modellfiler är NEXT, inte lovade i V3.3.
- Om ett möte verkar osynligt men SoldierBrain stannar, skriv av avståndet i titelraden. Då kan encounterplacering och siktlinje få riktade regressionstester.
