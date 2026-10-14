# Skyttegrav V3.9.6 – Pose commands, shouldered rifle, smooth transition

**Bas:** GitHub `jwestholm/skyttegrav`, branch `dev`, commit `59eca659d1bba2389eb231b9672f883383dd5e9b` (*Old model*, V3.9.5). Lokala originalfiler (`trench_3d_test.py`, `enemy_system.py`, `skeletal_pose.py`) kontrollerades med `git hash-object` mot committens blob-SHA. Ingen Godot och ingen Skjutbanan-integration.

## Installation

Packa upp denna ZIP **i roten av befintliga Skyttegrav-repot**, exempelvis `~/infinite_trench_3d_test/`. Skriv över medföljande Pythonfiler. Alla är kompletta, körbara filer, inte patchar och inga installskript finns med.

```
cd ~/infinite_trench_3d_test
python3 -m unittest discover -s tests -p 'test_*.py' -q
python3 trench_3d_test.py
```

## Vad som faktiskt ändrats

1. `F1` demonstrerar **kommandostyrda övergångar** i stället för att teleportera skelettet mellan fixerade poser. `PoseTransition.request(pose, actor)` tar en snapshot av exakt den **visade** paletten. Övergången interpoleras i rigid-rotation med normaliserade kvaternioner och mjuk acceleration/bromsning. Upprepade snabba `F1` mitt i en rörelse börjar från rådande ställning. Vid ny F1-session återställs testkontrollern.
2. **Rifle shoulder aim:** i `aim` och `fire` lyfts händer och gevär närmare axel-/kindlinjen; ena handen ligger vid avtryckaren och den andra håller längre fram på framstocken. I normala AI-states interpoleras detta från befintliga `EnemyAgent.aim_fraction()`. Detta är fortfarande geometrisk approximation, **inte verifierad äkta ögon-till-sikte-IK**.
3. **Arm-sving reducerad** ca 40–47 % i gång-/springscyklerna. Idle-andning och huvudspaning från V3.9.5 kvarstår.
4. Båda GPU-passen använder samma `collect_instances`-snapshot och benpalett, så skuggorna följer exakt samma övergång som figuren.
5. Arkitektur: `PoseTransition` är en liten tillbyggnad i befintliga `skeletal_pose.py`, **inte** en ny spel-AI eller parallell animationsmotor. All nav/CPU-sikt, skottfrysta hits, fiendens FSM och AI-beslut är oförändrade.

## Provkörning på GTX 1070

- `F1` från av: startar stand och visar andning/blick.
- Tryck `F1` en gång till: **stand → walk** (ingen direkt pose-pop). Nästa: **walk → run**; armarna ska röra sig mindre än i V3.9.5.
- Tryck vidare till **crouch → kneel → prone → supine_sleep → fear_curl → aim → fire → spade_attack → dead**. Ge särskilt **kneel** minst en sekund för att kunna se hela övergången.
- **F1 flera gånger snabbt:** övergången ska fortsätta mjukt från redan visad ställning. Föregående kommando kan då avbrytas (avsiktligt).
- **Aim/fire:** vapnet ska komma upp närmare axeln än i V3.9.5; du ska inte längre se samma låga maghållning. Pistången i demot är fortfarande den procedurskapade gamla gevärsgeometrin, inte verklig rig/IK.
- `F12`: skugga på/av. `F11`: mät frame-time och FPS i normalt spel. Testa skott, dödsställning, snabbhopp mot 450 m och `R`. Vid regresserad gameplay: återgå till V3.9.5 genom att återställa committens filer.

## Offlineverifiering (inte fysisk/GPU-speltest)

- `80/80` automatiska tester: original 69 samt 11 nya (`test_v396_pose_commands.py`). Inklusive mitt-i-övergång-interrupt, kvaternionortogonalitet, faktisk vertex-markkontakt, axlad gevärsställning, recoil, och oförändrade gameplay-/hitboxdata.
- `9/9` OpenGL 3.3-shaderprogram kompilerade och länkade i Mesa/EGL, inklusive skelettrendering och skuggor.
- Python-filerna kompilerade med `py_compile`.
- ZIP packas upp i en ren testkatalog och omtestas.
- **Ej verifierat:** faktisk animation/kameravinkel/FPS på din GTX 1070, fotorealistisk GLB, fot-IK, avancerad vapen-IK och mjuk 4-weight skinning.

## Nästa fokus – V3.9.7

1. Välj och licensverifiera en **verkligt riggad** glTF/GLB-karaktär, inte bara en högupplöst statisk figur. Tillgängliga Quaternius-animationer är CC0 men karaktären måste också ha korrekt licens och rig-kompatibilitet.
2. Bygg importer **inne i befintliga ModernGL-renderaren**: vertex-weights (upp till 4 influences), 3D-joints, inverse bind matrices, glTF-animationskanaler och gpu-skinning. Visa en enda soldat i F1-labbet först, med legacy-soldaten som fallback.
3. Behåll world-position från `EnemyAgent` och frysta träffvolymer; mät render-och-hitbox-avvikelsen före byte i vanligt spel. Animation får inte påverka fysisk hitdetektion genom att smyga in extra förflyttning.
4. Efter fungerande import: riktig axel/kind-IK, fotkontakt, normal maps/PBR på den nya modellen, mät FPS på GTX 1070. Fortsätt först därefter med attacker/sömn/rädsla.

**Git-policy:** Ingen commit, push eller merge. Skjutbanan/S03 orörda. Originalspel med Godot är inte med i ZIP.
