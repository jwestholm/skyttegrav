# SKYTTEGRAV V3.9.8 – Naturlig förbifart vid tomma sidogångar

**Bas:** V3.9.7 (`dev` har historisk bascommit `59eca659d1bba2389eb231b9672f883383dd5e9b`, "Old model"). Detta är en snäv kamerabeteende-/SoldierBrain-fix, ingen ny motor. Inget Godot, ingen Skjutbanan-integrering, ingen push/commit/merge.

## Felet i användarens videofilm 17181.mp4

I V3.9.7 följde även tomma sidogångar sekvensen `approach -> edge -> peek -> retract -> assess -> branch_rest`. Genomsökning uteblev, men SOLDATEN STANNADE fortfarande, sidovred blicken upp till ca 0,89 radianer och lutade kameran kraftigt. Resultatet såg konstlat ut när han skulle kontrollera öppningen och fortsätta. Detta är en verifierad orsak i koden; video visar beteendet men ger inte precisa 3D-sikt- och kollisionsdata.

## Nytt beteende

- **Utan lokaliserad evidens:** SoldierBrain behåller `main`, styr kroppen genom sin befintliga säkra huvudgångsbana och gör en **gradvis sidoblick i rörelse**. En kort snabbgång (mode 6, `SNABBGÅR`, med 90% tempofaktor nära öppningen) ger tillfälle att se in utan att kameran tvärstannar eller pekar rakt in i träväggen.
- Blicken bygger på **faktiskt passerade meter** relativt öppningen: byggs upp från -6,5 m, håller en liten stund kring öppningen, återgår framåt senast +3,7 m. Max mål-vridning **0,52 rad ~30°** i rätt sidoriktning; head-turn är tidsbegränsad till högst **1,2 rad/s** även om FPS svajar.
- Mycket liten kameraförflyttning vid sidoblick (mindre än 1 cm) i stället för det tidigare stora peek-/lean-manövern. Originalets `cover_distance` och säker vägplanering används fortfarande.
- **Med explicit lokaliserad evidens (`seen_enemy`, `localized_sound`, `movement`, `friendly_report` minst 0,65):** Behåller den tidigare mer försiktiga sekvensen med ordentlig observation och möjligt intrång. Inga låtsade fiender.
- Passager påverkar **inte** enemy AI, eldväxling, hitboxar, GLB-preview, GPU-skelett, skuggor eller chunk-streaming.

## Installation

Packa upp hela ZIP:en i roten av `~/infinite_trench_3d_test/`, skriv över filerna. **Endast kompletta filer**. Inget patchskript/installer. Befintliga git-ändringar bör sparas först. Starta som vanligt:

```bash
cd ~/infinite_trench_3d_test
python3 -m unittest discover -s tests -p 'test_*.py' -q
python3 trench_3d_test.py
```

Testa första sidogången runt **64 meter**, där soldaten nu ska titta in under rörelse, sedan gå vidare. Sök gärna också upp en senare T/Y/X-korsning och prova snabbspolning långt fram. Fiender ska fungera som förut. FPS och verklig projektion på GTX 1070 är **inte** fysiskt verifierade här.

## Verifiering

- Hela den tidigare offline-sviten samt nya regressioner för **icke-stopp vid tomt rum, följsam blick, begränsad lutning, kroppens huvudgångsposition, evidensstyrd genomsökning och dt-begränsad huvudrotation**.
- Spel-/skuggsprogram genomgånget i Mesa/EGL OpenGL 3.3.
- Ingen ändring av generator, meshes eller terrängtransport. Den procedurgenererade oändliga banan och den atomiska snabbspolningen kvarstår.

## Återstår

- Speltest på GTX 1070 för att se om sidoblicken känns mänsklig i **rörelse** (film från runt 64 m). Begränsningen är att vi fortfarande visar kamerans/huvudets rörelse direkt i first person; vi kan inte se en faktisk soldats huvud/kropp i first person.
- Vid riktiga sidogångsfiender krävs en separat mekanism för att eskalera om evidens upptäcks mitt under en förbifart; ännu inget sådant feed finns inkopplat.
- Fotorealistisk GLB-modell och animationsklipp kvarstår för F1-forskning, inte gameplay-promotade.
