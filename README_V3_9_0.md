# SKYTTEGRAV V3.9.0 – Rättvis fiendekontakt, soldatreaktioner och arkadsvårighet

**Bas:** V3.8.9 (kompletta filer, kopieras direkt över repots rot).  
**Utvecklingsinriktning:** on-rails lightgun: SoldierBrain styr all navigation, spelaren styr enbart skotten.  
**TESTSEED:** `1944`, avsiktligt oförändrad tills verkliga randomiserade runs är implementerade.

## Installera

Packa upp ZIP-filen i ditt befintliga **Skyttegrav**-repo, skriv över filer med samma namn. Ingen installerare, inga patchskript, ingen Git-åtgärd. Befintliga `assets/` behövs som tidigare och ingår inte i deltat.

Starta:

```bash
python3 trench_3d_test.py
```

## Vad som faktiskt är ändrat

- **Fienden måste få ett synligt möte innan dödliga skott tillåts.** En separat kontroll avgör om fiendens 3D-träffzon har varit på skärmen och nåbar från spelarens aktuella vy en rimlig tid. Världens siktlinje testas dessutom om **vid varje verkligt fiendeskott**. Den befintliga skottfrysta Game Space-träfflogiken för spelaren är orörd.
- **Kortare hörsel för steg**: automatisk löpning hörs maximalt 12 m (tidigare 35 m). Gevärsskott hörs fortfarande längre bort. Första fienden lockas inte fram över halva skyttegraven bara för att soldaten springer.
- **Fiendens taktik**: återanvänder `EnemyAgent` och `EnemyDirector` med sekvensen `scanning → peeking → hiding → peeking → hiding → rushing → locating → turning → aiming → firing`. Efter förlorad sikt kan fienden `searching → repositioning` istället för att fortsätta skjuta genom jordbanken. Synliga modeller och frysta träffzoner följer samma rörliga position, inklusive liten sidoförskjutning och hukning.
- **Vår soldats skyddsreaktion**: `SoldierBrain` får en överlagrad reaktion på **avfyrade** skott: rör sig mjukt mot en åtkomlig väggsida, hukar/knästår, och kan lägga sig efter upprepad beskjutning. Om inget synligt skottläge finns försöker soldaten gå framåt försiktigt inom befintligt framryckningsstopp. Ingen automatisk eldgivning från vår soldat.
- **Grus- och träsplittereffekt**: ett kort, begränsat partikelsprut vid icke-dödliga fiendeskott. Bygger på befintliga Battlefield-partiklar; är **inte** en ballistiskt beräknad kulträff eller bestående skada.
- **Svårighetskurva**: nivån bestäms av avancerad sträcka och styr spaningstid, antal kikningar, framryckningshastighet, rättvis reaktionstid, antal varningsskott och sannolikheten att fienden träffar. Svårighetsnivåerna börjar vid 0, 180, 450 respektive 850 meter. Exakta värden kan balanseras senare.
- **Prestanda**: tung CPU-siktanalys samplas med cirka 15 Hz i stället för varje renderad bildruta. Det är **endast perceptionen** som glesas ut; synlinjen kontrolleras på nytt före dödlig fiendeeld.
- **Befintlig game-over-animation bevaras** utan grafiska ändringar.

## Skyl och skydd – implementeringsstatus

`combat_tactics.MATERIALS` beskriver planerad skillnad mellan **skyl** och **skottskydd**:

- Jordvägg, stora stenar: ogenomskjutbara i det nuvarande förenklade sikt-/kulskyddet.
- Låda, rasbråte: används i befintlig geometrisk siktblockering och som typ för trä-/stenskärvor.
- Duk/nät: materialpolicy finns definierad, **men korrekt optisk ocklusion och genomskjutning är ännu inte implementerade i spelvärldens geometri**.
- All penetrationssannolikhet och täckningsprocent för material är förberedande värden, **inte en färdig ballistikmotor**.

### Kvarvarande begränsningar

- Kika-/huksidoförskjutning är kort och körfältsbegränsad. Fienden väljer ännu inte en verklig, säker plats bakom *en särskild låda* med komplett pathfinding.
- Vår soldat kan röra sig mot väggen och söka bättre vinkel, men gör ännu inte ett avancerat skyddssök till ett objekt flera meter framåt.
- LOS är fortfarande en konservativ geometrisk approximation, inte triangelexakt raycast mot alla renderade props.
- Missade skott ger visuell grus-/träskvätt nära spelaren; de följer inte en simulerad projektilbana.
- Proceduren är en arkad-AI med begränsade regler, inte mänsklig militärtaktik.
- GTX 1070-visning, varje animation i riktig scen och verkliga frametimes är **inte verifierade** i denna miljö.

## Tester – genomför i denna ordning

| Test | Genomförande | Förväntat |
|---|---|---|
| T1 – Gamla väggfelet | Starta normalt och låt soldaten vara vid ca 8–12 m. Skjut inte. | Första fienden skjuter **inte** och du dör **inte** bakom väggen. |
| T2 – Synligt möte | Låt SoldierBrain närma sig fienden vid ca 32 m. | Fienden syns, spanar/kikar, hukar undan och rör sig några meter innan han försöker sikta och skjuta. |
| T3 – Varningsskott och missar | Skjut inte efter första fiendekontakten. | De första skotten dödar inte direkt; missar kan skapa grus-/träsplitter. Först efter ett synligt skottläge kan ett skott bli dödligt. |
| T4 – Egen AI | Låt synlig fiende skjuta. | SoldierBrain försöker huka, söka väggen och reagerar kraftigare på flera skott utan att du styr rörelsen. |
| T5 – Eliminera | Klicka på synlig fiendes kropp. | Fienden faller. Räknaren ökar och SoldierBrain avancerar igen. |
| T6 – Game over | Låt fienden träffa efter en rättvis kamp. | Befintlig fade/blod/resultatskärm med meter, fiender, skott och poäng visas. |
| T7 – Starta om | Tryck `R` efter död. | Tillbaka till 0 m, AUTO, samma seed och återställda AI-/speltillstånd. |
| T8 – Prestationsmätning | Tryck `F11`, spela första mötet och testa `F3`/`F5`. | Rapportera `update`, `draw`, `chunks`, max-frametid och position om FPS hackar. |
| T9 – Svårighetskurva | Använd endast felsökningsknappen `↑` för att hoppa längre fram. | Fiendernas parametrar stegras men de får inte kringgå LOS eller skjutmöjlighet. OBS: `↑` är utvecklingskontroll. |

### Offline

```bash
PYTHONPATH=. python3 -m unittest tests.test_v390_tactics tests.test_v388_arcade -v
python3 check_glsl_egl_v33.py
```

De **23** nya + medföljande regressionstesterna passerar offline. Kompilering/länkning med Mesa/EGL OpenGL 3.3 passerar. Detta ersätter **inte** test på riktig GTX 1070 eller hela repots befintliga svit.

## Framtida slumpade körningar

Skilj *världens seed* från *svårighetskurvan*. I framtiden tilldelas en ny seed per **ny spelomgång**, och alla procedurkomponenter (rutt, biomer, skydd, encounters, händelser, RNG) ska reproduceras från samma run-seed. Vid reproducerad run används exakt samma seed. När vi inför ny seed måste även den globala ruttcachen, streaming och första chunkens förberäknade mesh byggas om korrekt; det räcker **inte** att bara skriva `SEED = random.randint(...)` vid `R`.

Svårighet ska bero på uppnådd sträcka och möteskomposition, inte på turen med seed. Spelbara fiendemöten måste garanteras i varje seed. När seedval införs ska resultat/dödsskärm/logg kunna visa eller spara den seed som skapade omgången.

Ingen ändring av Skjutbanans CV/träffdetektion. Alla tangentbords-/musklicksskott i standalone är simulerade.
