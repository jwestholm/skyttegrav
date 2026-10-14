# SKYTTEGRAV V3.10.4 – Enemy Pairs & Physical Cover

Bas: V3.10.3 från `dev` (`bb068ad9`). Standalone Pygame/ModernGL, ingen Skjutbanan-integration.

## Implementerat

- Efter de fyra första orörda mötena dyker vissa huvudpatruller upp som **fiendepar** (en andra, individuell `EnemyAgent` med separat ID, död, posering, projektion och frysta träffsfärer). Deterministiskt var femte senare möte, utan globalt fienderegister.
- Vissa par får en **fysiskt renderad låda vid sidan av gången** (`paired_cover_at`). Samma `TrenchObstacle` används vid chunkbyggande, lokala LOS-kontroller, navigering och spelarens exakta triangelskott. Den ersätter vanligt skräp inom ett smalt område för att undvika överlappning.
- När spelaren skjuter reagerar **redan engagerade** fiender på skottljud. Fienden väljer ett tillgängligt, nåbart **högt** skydd framför sin egen position. Om inget passande skydd finns hukar han tillfälligt men får inte osynlig skottsäkerhet.
- Fienden förflyttar faktisk `route_m` och `lateral_offset` med begränsad hastighet mot lådan, hukar, kikar och återgår till sikte. Modell och träffsfärer delar dessa posevärden.
- En besegrad medlem lämnar den andra vid liv; den kvarvarande kan reagera på kamratens fall. Alla fyra första mötena har oförändrade grundspecifikationer.
- Skottgeometri, Game Space-koordinater, shaderkod, material och terrängstreaming har inte skrivits om. Inga artificiellt större hitboxar.

## Medvetna begränsningar

- Detta är första nivåns cover-AI; den söker inte ännu vägar runt komplicerade hörn/rum, och det finns ingen global AI-pathfinding.
- Den lokala fiende-LOS-modellen bygger delvis på tidigare approximativ `combat_visibility` medan spelarens skott mot världen använder renderade trianglar. Skydds-AI får alltså inte beskrivas som centimeterexakt skydd i varje pose.
- Par/gömställen har ännu inte fysisk eller visuell verifiering på GTX 1070. Offline-test är inte faktisk gameplayvalidering.
- Patruller **ovanpå** vallen, fiender **i** sidogångar, kastade granater, verkliga T-vägval och avancerade rökeffekter är planerade nästa steg, **inte implementerade i detta paket**.

## Verifiering och testning

- `python3 -m unittest discover -s tests -p 'test_v*.py' -q`: 141/141 godkända efter ändringar.
- `python3 check_glsl_v397_egl.py`: befintliga 11 shaderprogram OpenGL 3.3-kompilerar och länkar i Mesa/EGL.
- Nya regressioner: seeded par, oberoende död, frysta individuella 3D-hitvolymer, faktiska lådor i chunkmesh, begränsad/fysisk förflyttning i skydd och undertryckning utan skydd.

## Installation

Kopiera **kompletta** filer över en V3.10.3-installation. Kör inte ovanpå en nyare lokalt modifierad kodbas utan diff/backup. Ingen push eller merge har gjorts.

```bash
cd ~/infinite_trench_3d_test
python3 -m unittest discover -s tests -p 'test_v*.py' -q
python3 trench_3d_test.py
```

### Att testa på riktigt

- Gör ett hopp med F11 till cirka **510 m**: första möjliga fiendeparet står vid ungefär **516 och 518,45 m**. Varje fiende ska kunna träffas separat.
- Skjut ett varningsskott medan de redan är engagerade. En av dem bör söka lådan vid cirka **517,2 m**, den andre huka/agera utan att få osynligt skydd.
- Håll koll på FPS, särskilt när två fiender syns samtidigt. Dokumentera eventuella skott genom eller mot lådan, och om SoldierBrain blir stående bakom en osynlig vägg.
