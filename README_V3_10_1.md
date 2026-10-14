# SKYTTEGRAV V3.10.1 – Hörnkik med riktig observationstid

**Bas:** V3.10.0. Fristående Pygame/ModernGL. Fast seed 1944. Ingen Godot och ingen integration med Skjutbanan.

## Varför
V3.10.0 nådde stor sidoblick först i slutet av en alltför kort `observe_peek`-fas. Dessutom höll kameran blicken in i sidogången för länge efter att öppningen passerats. Användarens film 17191.mp4 och feedback låg bakom ändringen. Separat feedback tyder på bättre skottkonsistens i V3.10.0, så skottgeometri och fiende-AI **ändras inte**.

## Ändringar
- Kamerastopp vid `junction_marker - 2.47 m`, mellan V3.9.9 (2.25 m) och V3.10.0 (2.72 m).
- Stannad kiksekvens: `observe_settle` 0.25 s, `observe_peek` 1.85 s, `observe_assess` 0.35 s. Äldre tider: 0.22 / 1.20 / 0.28 s.
- Under `observe_peek` ger befintlig smidig/rate-limited huvudvridning **cirka 1.28 sekunder** med blicken mer än 0.9 rad in i sidogången, enligt seed-1944 offline-simulering på 60 Hz; ingen sekundsnabb panorama-svepning med exakt slutvinkel först sista bildrutan.
- Under passage hålls sidoblicken fram till 0.35 m efter junction och faller sedan till noll på intervallet +0.35 till +2.50 m. Kamerans egen utjämning fortsätter utan teleportering.
- Befintliga fiender, hitboxar, jordtriangel-raya, fysiska skottkoordinater, animationsrigg och shaders är oförändrade.
- Gamla tids- och stopp-påståenden i två regressionstester har justerats till den nya avsiktliga designen. Tre nya regressionstester verifierar observationstid, framåtblick och ingen intrång i tom sidogång.

## Installation
Packa upp ZIP:en i roten av `~/infinite_trench_3d_test/` och skriv över filer. Detta är kompletta Python-filer, inga patchskript eller Git-operationer. Övriga egna assets/texturer lämnas kvar.

```bash
cd ~/infinite_trench_3d_test
python3 -m unittest discover -s tests -p 'test_v*.py' -q
python3 trench_3d_test.py
```

## Testa visuellt
1. Första sidogången runt 64 m: stannar strax före hörnet, vrider huvudet och har faktisk tid att se in i öppningen.
2. Fortsatt gång förbi öppningen: sidoblicken ska minska strax efter mitten och vara nära noll ca 3 m efter öppningen.
3. Korsning från andra sidan runt 136 m: samma beteende spegelvänt.
4. Första fiendekontakten och miss/träff vid jordvall: oförändrad V3.10.0-geometri; spela gärna fler varierade fall innan vi kallar den live-validerad.
5. F11 och snabbhopp: inga kända nya krav på CPU/GPU-resurser.

## Verifiering
- 121/121 automatiska offline-tester passerade (med riktiga SoldierBrain-vägar och skottregressioner).
- 11/11 OpenGL 3.3-program kompilerade och länkade i Mesa/EGL.
- Inte testat på användarens GTX 1070, inte validerat med verkliga skott från Skjutbanan.
- Ingen commit/push/merge.
