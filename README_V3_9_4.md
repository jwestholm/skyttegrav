# Skyttegrav V3.9.4 – dödsställning och tappat gevär

**Bas:** V3.9.3 (GPU-skelett). Detta är en liten visuell korrigering efter
skärmbilden 2026-10-14 där den döda soldaten såg ut att ligga och spana.

## Orsak

V3.9.3:s `dead`-ställning delade i stort sett arm- och huvudposition med
`prone`. Geväret låg kvar på en benmatris som följde händerna. Resultatet
liknade en levande skytt i liggande skjutställning.

## Ändringar

- En separat dödsställning: böjd/asymmetrisk underkropp, huvudet faller åt
  sidan, armarna slappnar av åt olika håll. Två spegelvända varianter efter
  `enemy_id` utan ny slump eller extra animationstråd.
- Geväret släpps efter cirka 0,15 sekunder och landar bredvid kroppen.
  Vapenrörelsen och huvudet är interpolerade; inga omedelbara hopp i första
  dödsbildrutan.
- Markkontakten korrigerad för underarmarna och det tappade vapnet.
  Samma benmatriser används i huvud- och skuggpass.
- Versionssträngen i spelfönster och terminal ändrad till V3.9.4.
- Ingen förändring av NPC-AI, bullet/hit-system, score eller spelbalans.

## Installation

Packa upp ZIP-filen **i roten av ditt befintliga Skyttegrav-repo** och skriv
över filerna. Alla ändrade Pythonfiler levereras i sin helhet. Även resten
av V3.9.3:s filer ingår, så ZIP-filen kan läggas direkt ovanpå din version.

```bash
python3 trench_3d_test.py
```

## Verifiering och kvarvarande begränsningar

- Python syntax / offline-unit-tester kontrollerade.
- Separat regression för tappat gevär, asymmetri, markkontakt och kontinuerlig
  animation.
- Ingen faktisk GTX 1070-bild eller riktig spelupplevelse verifierad här.
  Prova att skjuta en fiende och filma dödsanimationen igen.
- Detta är **inte fysikalisk ragdoll**: den procedurbyggda figuren har fortfarande
  en 16-bens single-influence GPU-rigg. En konstnärligt riggad GLB med bättre
  hudning och dödsanimationer behövs för högre realism.

Ingen push, merge eller commit utförd. Skjutbanans fysiska hit-detection ändras inte.
