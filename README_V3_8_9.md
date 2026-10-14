# SKYTTEGRAV V3.8.9 – Osynlig spelarkropp, LOS, skott och dödsskärm

## Installation

**Utgångspunkt:** den tidigare V3.8.8 FULL_FILES-installationen ovanpå `skyttegrav/dev` (V3.8.7.x). Packa upp ZIP:en **direkt i roten** av Skyttegrav-katalogen och tillåt överskrivning. Här levereras **hela färdiga ersättningsfiler**; inget installationsskript. Dina befintliga `assets/` påverkas inte.

Starta: `python3 trench_3d_test.py`

## Spelmekanik

- Spelaren styr **enbart skyttet**: vänster musklick eller T (skott i mitten). Vår soldat navigerar vidare med befintlig SoldierBrain.
- Spelarkroppen är ett **osynligt kollisions-/perceptionsmål i virtuella världen** som följer senaste presenterade kamerans X/Z och kroppsställning. Stående ungefär 1,8 m, på knä ungefär 1,2 m, liggande ungefär 0,66 m. Ingen kropp ritas. Fysiskt skjutavstånd 6,3 m till projektionsytan påverkar INTE positionen i 3D-världen.
- Fiender kontrollerar **synriktning** vid första upptäckt och **konservativ världssiktlinje** mot kroppsdelarna. De ska inte förvärva eller skjuta träffsäkert genom den modellerade skyttegravsväggen eller befintliga lådor/bråte. Detta är en approximerad skjutbanesiktkontroll, inte ett fullständigt raycast mot varje renderad triangel eller varenda prop.
- Fiender kan däremot bli uppmärksamma genom befintliga skott-/springstegsljud och undersöka dem.
- Den tidigare V3.8.8-dödstimern är **borttagen**. Varje faktisk avfyrad fiendekula ger ett separat träffslag med avstånds-/kroppsexponeringsberoende misschans. En fiende får INTE döda när siktlinje saknas eller spelaren redan är död. Fiender vars sikte blockeras slutar skjuta och söker kontakt igen.
- Automatisk framryckning mot skymt hot stannar inte redan på åtta meters avstånd; soldaten får försiktigt närma sig för att hitta synkontakt. Den befintliga reaktiva navigationslogiken ligger kvar.
- Död: svartnande bild, röda droppar som rinner nedåt, text med sträcka, antal dödade fiender, antal avfyrade skott och totalpoäng. `R` börjar om.
- **Poäng V3.8.9:** hela meter + 100 poäng per eliminerad fiende. Den här modellen är till för utprovning.
- Fryst renderingssnapshot används fortfarande för musens simulerade 3D-skott. **Ingen ändring i Skjutbanans fysiska träffdetektion.**

## Tester hemma – börja här

1. **T1 – Regression för skärmbilden, 8 m:** Starta och låt soldaten avancera. En fiende bakom jordvägg får **inte** döda dig vid 8 m. Den faktiska geometrin har verifierats offline: första fienden vid 32 m är skymd från 8 m och 12 m; öppen sikt börjar runt 16 m. Notera eventuella andra förflyttningar orsakade av ljud.
2. **T2 – Kontakt utan skott:** Fortsätt mot synlig fiende och låt den skjuta flera gånger. Första skottet får missa; du ska inte dö av en osynlig timer. Det ska slutligen gå att dö vid träff.
3. **T3 – Skjut först:** `R`, skjut en synlig fiende med musen. Den faller, `dödade` ökar och vår soldat fortsätter framåt. Skott som missar räknas ändå som avfyrade skott.
4. **T4 – Hörsel/överraskning:** Spring fram utan skott jämfört med att skjuta i luften. Fiender kan reagera på ljud från vår färd; en vänd bortåt fiende ska inte automatiskt se genom bakhuvudet.
5. **T5 – Ställningar:** `0` AUTO, `F3` nära brisad. Soldaten hukar/ligger, och den osynliga målkroppen följer kroppshöjden. Vid manuell testställning (`1`–`9`) fungerar detta likadant.
6. **T6 – Dödsskärm:** Låt fienden träffa. Kontrollera mörk fade, rinnande röda stråk, och exakt: `DU ÄR DÖD`, `Du kom X meter`, `Dödade X fiender`, `Sköt X skott`, `TOTALA POÄNG: X`, samt `R`.
7. **T7 – Paus/omstart:** `P` stoppar all simulering/dödsskärmsanimation; `R` återställer räknare, fiender, kameran och framryckning.
8. **T8 – Prestanda:** slå på `F11`, gå till första fienden och en andra kontakt, anteckna `update p95/max`, `draw p95/max`, `FPS` och eventuella hack. LOS är nu CPU-baserad och får inte orsaka kraftig frametime-regression.

## Verifiering vid paketbygge

- 11 rena offline-enhetstester godkända.
- Grundspelets 12 befintliga GLSL-shaders och 6 programlänkningar testade med riktig Mesa/EGL OpenGL 3.3.
- 4 nya GLSL-shaders och 2 programlänkningar testade i samma OpenGL 3.3-miljö.
- Python-syntax kontrollerad.
- På faktisk befintlig procedural värld: första fienden bakom svängd vägg occluded från 8/12 m och synlig från omkring 16 m.
- **Inte GPU-visuellt testad på GTX 1070; inte full befintlig regressionstestsvit** (bara delta-testsviten fanns tillgänglig som körbara filer i arbetsmiljön). Det återstår för hemmatest.

## Nästa arbete

1. Förfina siktsystem till faktisk renderad 3D-ocklusion/BVH och särskilda skyddspositioner; konservativ proxy kan missa/hindra verkliga siktlinjer.
2. Fiender som faktiskt flyttar sig mellan skydd och tittar fram. Vår SoldierBrain ska navigera till ny säker skjutvinkel i stället för att fastna.
3. Fler animationer/riggade modeller och ljud för hörbara avfyrningar, impact och missar.
4. Visuell kvalitet på GTX 1070: material, skuggor, ljus och GPU-prestandabudget enligt plan.
