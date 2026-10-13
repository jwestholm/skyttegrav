# Skyttegrav – hemmatest från V2.4 till V3.8.3

**Datum:** 2026-10-13  
**Spelperspektiv:** Du ÄR soldaten. Kameran är spelarens ögon; SoldierBrain sköter automatisk fysisk förflyttning och reaktioner.  
**Verifieringsstatus:** Senast visuellt testad av användaren: ungefär V3.4. V3.5–V3.8.3 är offline-testade, **inte visuellt godkända** på GTX 1070.  
**Ingen ändring av Skjutbanans fysiska hit-detection.** Standalone-klick är simulerade skott.

## Installera – två alternativ

### A. Enklast: samlad uppdatering för V2.4 → V3.8.3

Utgå från den fungerande V2.4-katalogen (inklusive de 13 ursprungliga texturerna under `assets/`).

1. Ta en kopia av katalogen eller skapa en separat testkopia. Rör inte din fungerande Git-branch om du inte vill.
2. Packa upp **`UPGRADE_skyttegrav_v2_4_to_v3_8_3.zip`** ovanpå V2.4.
3. Behåll egna Poly Haven-texturer under `assets/polyhaven/`. De ingår **inte** i uppdateringen.
4. Starta `python3 trench_3d_test.py`.

Den samlade ZIP:en innehåller senaste kod, aktörer, effekter, fallbacks och uppdaterade regressionstester. Den behöver **inte** V2.5–V3.8.2-ZIP:arna först. Installeras bara ovanpå en **befintlig** V2.4-installation, inte i tom katalog.

### B. Versionsvis jämförelse av grafiken

För att se skillnaden efter varje större milstolpe, packa i ordning över V2.4:

`V2.5` → `V2.5.1` → `V2.6` → `V2.7` → `V2.8` → `V2.9` → `V3.0` → `V3.1` → `V3.2` → `V3.3` → `V3.4` → `V3.5` → `V3.6` → `V3.7` → `V3.8` → `V3.8.1` → `V3.8.2` → `V3.8.3`.

**Obs:** Milstolparna är skillnader i prototypen, inte alla användarverifierade releaser. För snabbtest räcker alternativ A.

## Kör – snabbtest ca 10–15 min (7 kontroller)

| Nr | Test | Gör så här | Förväntat resultat / vad du ska notera |
|---|---|---|---|
| 1 | Start, förstaperson och kameraflöde | Starta; `0` för AUTO. Följ första 20–30 m. | Du upplever att du går själv; inga snabba kvartsvändningar eller pingvingung. Läs FPS i fönstertiteln. |
| 2 | Första fiendekontakten | Låt AUTO nå första fienden kring 32 m. Klicka på synlig kropp. | Fienden reagerar, öppnar eld; spelaren måste skjuta bort hotet; miss ska inte eliminera. Kroppen ska inte sväva. |
| 3 | Hörn, sidogång, dugout | Fortsätt mot första sidogångarna (första korsning kring 64 m). | Kroppen närmar sig kanten, huvudet kikar försiktigt; dugout har välvt tak, inga dubbla markplan och ingen kamerateleport. |
| 4 | Nära explosion | Tryck **F3** under förflyttning, helst när ett hörn närmar sig. | Kort efter knapptrycket smäller det nära; du hukar/ligger beroende på närhet. Ingen markdeformation. Navigationen pausar och bedöms om utan hopp. |
| 5 | Artilleri och flyg | `F5` för salva, `F4` för flyg, `F6` för enstaka brisad. | Små, trovärdiga, temporära rök-/damm-/gruseffekter. Flera osynkroniserade nedslag, inga jättelika eldklot. |
| 6 | Miljö och streaming | Gå vidare mot 80 m/160 m chunkgränser, observera kanterna och landskapet. | Stenar, lerigt grus, mindre kantiga sandsäckar, varierat timmer, träd och taggtråd. Inga svävande jordytor eller stora FPS-hack. |
| 7 | Återhämtning och omstart | `F3` medan fiende lever; eliminera sedan fienden. `R` för omstart. | Explosion får avbryta rörelsen men inte döda fienden automatiskt. Hotet kvar tills skott. R återställer även manuellt läge, kroppshöjd, kameravinkel och pausstatus och visar omedelbart startterrängen. |

### Extra om du hinner

- Gå ungefär till **280–350 m** för att prova en täckt huvudtunnel med ned-/uppförslutning. Taket får inte klippa kameran.
- Låt spelet gå **10 minuter** för att upptäcka stutter, minnesläckage eller fastnande navigation.
- Prova **F7/F8** (dimma), **F2** (slumpmässiga effekter AV/PÅ), **SPACE/P** (paus), **F9/F10** (fönsterhöjd), **T** (simulerat skott i bildens mittpunkt).
- Manuell rörelsetest med **1–9** ändrar hållning/gångart. **0** återgår till autonom SoldierBrain.

## Offline-test (valfritt)

I projektkatalogen:

```bash
PYTHONPATH=.:tests python3 -m unittest tests.test_v382_first_person_timestep tests.test_v381_blast_reactions tests.test_v33_first_contact -v
```

V3.8.2 fixade ett konkret kamerafel: `last_dt` uppdaterades inte och låg konstant på `1/60`, även om skärmen ritades med t.ex. 400 FPS. Nu används uppmätt `dt` även för huvudvridningen och kamerans dämpning. Nytt test jämför 30, 60, 144 och 400 FPS.

Om du installerar ovanpå en gammal arbetskatalog kan äldre, numera föråldrade testfiler finnas kvar. **Kör därför de namngivna testmodulerna**, inte nödvändigtvis `discover` på hela gamla katalogen.

## Återrapportera kort

För varje avvikelse: ange **ungefärlig meterposition**, aktuell **SoldierBrain-fas** (står i fönstertiteln), **FPS / max ms / upload ms**, och gärna skärmbild eller kort film.

```text
Version testad: V3.8.3 (eller annan)
Känsla att JAG går i skyttegraven (1–5):
Hörn och kroppsrörelser (1–5):
Fiender och animationer (1–5):
Miljö/grafik (1–5):
Explosioner och skyddsreaktion (1–5):
Lägsta märkta FPS och eventuella hack:
Problem + meterposition:
``` 

**OBS:** Detta är ett spel-/grafiktest, inte en validering av Skjutbanans fysiska accuracy. Den integreringen testas separat längre fram.

**V3.8.3 tilläggstest:** Låt spelet passera minst 160 m. Välj därefter ett manuellt läge (`1`–`9`), tryck `P` för paus och `R` för omstart. Förväntat: 0 m, automatisk gång, upprätt och opausat utan kvarvarande sidovinkel. Leta efter enstaka hack runt chunkgränserna och notera `max ms`/`upload ms`.
