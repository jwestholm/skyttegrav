# Skyttegrav V3.9.9 – stanna, kika och passera med uppsikt

**Bas:** V3.9.8 Natural Branch Glance. **Motor:** Python/Pygame/ModernGL, ingen Godot. Skjutbanan-integrationen är pausad.

## Varför

Videon `17185.mp4` visade att V3.9.8:s 30-graders sidoblick under rörelse inte gav någon trovärdig kontroll av öppningen. Tidigare V3.9.7 gjorde däremot för många stillastående delmoment. Den här versionen använder *en* kort, synlig hörnkontroll.

## Nytt beteende: sidogång utan bekräftat hot

1. **Observera ingången:** fortsätt framåt längs huvudgången, bromsa inför öppningen.
2. **Stanna cirka 2,25 m före markören:** ingen framåtrörelse under själva kiken.
3. **Kika runt hörnet:** mjuk, hastighetsbegränsad blick upp till ca 69–71° mot sidogången och en liten huvudförskjutning; cirka 1,2 s visuell kontroll.
4. **Bedöm:** påstå inte att rummet är tomt bara för att ingenting upptäckts. Pröva registrerad sidolokaliserad evidens.
5. **Fortsätt:** om ingen sådan evidens finns går soldaten förbi med huvudet fortfarande vänt mot öppningen, och vrider sedan smidigt fram blicken.

Inga nya fiender skapas i sidogångarna av den här patchen. Det finns ännu ingen fullständig side-branch-person-detektor. Framtida fiende-/ljudsystem kan rapportera faktisk lokalisering via det *befintliga* `report_branch_evidence()`; misstänkta ingångar behåller sin försiktiga söksekvens. Beslut kan ändras under kika-/bedömningsfasen.

## Arkitektur och gränser

- Återanvänder befintlig `SoldierBrain`-FSM, skyttegravsgeometri, kamera, seed och fiende-AI.
- Fyra små FSM-steg: `observe_approach`, `observe_settle`, `observe_peek`, `observe_assess`.
- Kamera- och markpositionsvägen använder fortfarande **huvudgångens** `route()` och `_main_offset()`. En blick vrider inte kroppen runt hörnet eller flyttar fötterna genom jordväggar.
- Ingen förändring av hitboxar, träffdetektion, fiende-AI, terräng-/chunkstreaming eller GLB-import.
- Explosionsavbrott under observation kräver ett nytt kikmoment efteråt.
- V3.9.7/V3.9.8-testerna som krävde *ingen paus* är uppdaterade till det nya accepterade beteendet. Samtliga tidigare säkerhets- och kontinuitetskontroller finns kvar.

## Installation

Packa upp `DELTA_skyttegrav_v3_9_9_CORNER_CHECK_FULL_FILES.zip` i roten av `~/infinite_trench_3d_test` och skriv över. ZIP innehåller **fullständiga, körklara** filer, inte ett install- eller patchscript.

```bash
cd ~/infinite_trench_3d_test
python3 -m unittest discover -s tests -p 'test_v*.py' -q
python3 trench_3d_test.py
```

## Viktigaste manuella testet

Gå till första sidogången vid cirka 64 m. Soldaten ska:

- synligt bromsa och stanna vid kanten,
- vrida blicken långt nog att man ser in i rummet medan kroppen håller huvudgången,
- välja att fortsätta om inga faktiska tecken finns,
- under förbipassagen fortfarande titta in mot golv/plankor och eventuellt dolt hot,
- återgå med mjuk huvudvridning mot huvudgången.

Kontrollera samma mönster vid sidogången cirka 136 m (motsatt sida). Kontrollera vanliga fiendekontakter och hoppet till 450 m.

## Utförd verifiering (offline)

- 105/105 automatiska regressionstester passerade, inklusive 7 nya testspecifika fall för V3.9.9.
- Alla 11 GL3.3-program kompilerade och länkade i Mesa/EGL.
- Stopp/huvudrörelse och själva förbipassagen kontrollerade med originalets seedade 3D-koordinater på flera sidogångar.
- Fullt spel och renderad film på GTX 1070 **inte** validerat – fysisk/visuell kontroll återstår.

Ingen commit, push eller merge gjord.
