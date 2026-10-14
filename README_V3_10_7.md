# SKYTTEGRAV V3.10.7 – Exterior Patrols (above the trench)

**Bas:** V3.10.6, byggd på användarens GitHub `dev` V3.10.3. Fristående Pygame/ModernGL. Skjutbanan integreras INTE.

## Implementerat

- Glesa, seedstabila fiendepatruller ovanför jordvallen, på **verklig exteriör mark**, inte på huvudgångens golv eller fejkade skärmpositioner. Första vid ungefär **732 m**, sedan omkring **1 308 m**. Svårighets- och mötesbalans kan behöva justeras efter faktisk spelning.
- Varje patrull har `EnemySpec.exterior_side` och `exterior_clearance`; `Trench.enemy_position()` placerar både renderad soldat och frysta kroppsträffsfärer på samma `world_on_ground`/`hill_y` som world-meshen använder. Små differenser mot detaljerat tesselaterad mark kontrollerade offline.
- Kontinuerlig, bounded rörelse längs vallen. Ingen teleport vid spawn, och kroppsrörelsen driver normal gånganimation. Vid upptäckt stannar patrullen och reagerar/siktar med befintlig fiende-FSM.
- **Faktisk triangel-LOS** mot frysta världen för observation, eld och spelarens möjlighet att upptäcka/skjuta. Ingen magisk vetskap om soldaten. Finns ingen mesh blir LOS inte automatiskt godkänd.
- Exteriöra patruller behandlas **inte** som huvudgångens fysiska framryckningshinder; de ska inte frysa SoldierBrain mitt i skyttegraven.
- Befintlig metod för kroppsträffar och spelares skott är oförändrad. Världsraycast för jordvall bibehålls. Ingen modifiering av projektion/hit-koordinater.

## Avsiktligt kvar

- Inget synligt **nedhopp** ännu. Kräver säker fysisk avsats, animation, landning och navigering på skyttegravens golv; inte teleportera ned.
- Ingen aktiv **stealth-policy** där SoldierBrain väljer att krypa förbi patrull; befintliga huka-/rörelselägen, bankskydd och verklig LOS finns, men AI-beslutet är NEXT.
- Fiendens övergång från allvarlig skada/suppression till flykt utomhus behöver separat verifiering.
- Kastade granater, avancerad röktaktik, ytterligare rumsrundor och verklig ruttdelande 90° T-korsning är kommande fristående delprojekt. De ingår INTE i detta paket.

## Verifiering

- **155/155** Python-unittest offline, inklusive sex nya tester i `tests/test_v3107_exterior_patrols.py` och alla tidigare 149 regressionstester.
- Genererad riktig chunk runt 720 m använd för vertikal landning, sikt bakom jordvall och normal exponerad sikt.
- Kontrollerat att frysta hit-spheres följer samma kontinuerliga world-pose och ingen ny aim assist används.
- Shaderkällan **oförändrad** sedan tidigare kontrollerad V3.10.4; inga nya GLSL-program.
- Inte testad på användarens GTX 1070, projektor eller fysiska skjutbana. Ingen faktisk FPS- eller live-accuracyförbättring påstås.

## Installation

Fullständiga filer i ZIP. Packa upp i `~/infinite_trench_3d_test/` och skriv över. ZIP innehåller kumulativt även V3.10.4–V3.10.6-ändringar och kan därför installeras direkt ovanpå **ren V3.10.3** som ligger på GitHub `dev`. Har du lokala ändringar ovanpå V3.10.3: gör en diff/backup före överskrivning. Inget installations-/patchskript.

```bash
cd ~/infinite_trench_3d_test
python3 -m unittest discover -s tests -p 'test_v*.py' -q
python3 trench_3d_test.py
```

Använd F11 och snabba debughopp försiktigt om du vill se en patrull kring 732 m. Ge gärna bildsekvens av hur den upplevs, särskilt om den ser ut att sväva, röra sig innanför vallen eller kunna skjuta trots skymd sikt.

Ingen commit, push eller merge utförd.
