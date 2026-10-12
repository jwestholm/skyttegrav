SKYTTEGRAV 3D — V2.7: Detail Materials, Props & World-Fixed Sun
==============================================================
Utgå från din V2.6/dev-installation; extrahera ZIP direkt i
~/infinite_trench_3d_test/ så att filernas relativa sökvägar bevaras.
Denna ZIP innehåller bara ändrade/nya filer. Befintliga 13 bastexturer
ska ligga kvar i assets/. Ingen commit eller push har gjorts.

KÖR
  cd ~/infinite_trench_3d_test
  python3 trench_3d_test.py

Nytt i V2.7
- 1024 x 1024 texture-array (tidigare 512), 16x anisotropi där stöds.
- 7 NYA texturvarianter med egna OpenGL-normal maps under assets/detail/.
  De är lokalt genererade/procedurala FALLBACKS, INTE foton.
- Alternativ nedladdning av riktiga CC0 Poly Haven-material (se nedan).
- Mer rundade/träaktiga stockar med avkapade ändar, fler polygoner på
  större boulders, sandbags och trädkronor; enklare LOD efter avstånd.
- Jordväggar har lokala timmerpartier, plankbeklädnad eller helt öppna
  väggar; varianter ändras per 15m, utan att SoldierBrain ändras.
- Nya deterministiska väggdetaljer: korta stegar, förstörda plankor,
  små lådor, presenningar, säckar, metalltunnor, skräp och stenfragment.
- Vegetation/stenar väljs nu efter långsträckta miljözoner i stället
  för enhetlig fördelning. Befintlig chunk-streaming kvar.
- Solen är äkta himmelsriktning (world-space), inte fast UV-prick;
  ingen positionsparallax från soldatens gång, men korrekta förändringar
  när kameran faktiskt vrids. Solen ligger lågt vid horisonten.

RIKTIGA FOTOGRAFISKA POLY HAVEN-TEXTURER (VALFRITT)
  python3 fetch_polyhaven.py --check
  python3 fetch_polyhaven.py
  python3 fetch_polyhaven.py --asset pine_bark
  python3 fetch_polyhaven.py --asset wood_planks
  python3 fetch_polyhaven.py --doctor
  python3 fetch_polyhaven.py --force  # återskapar gamla nedladdningar som 1024px

Hämtaren laddar nu 2K-källor, sparar 1K i assets/polyhaven/.
Material: brown_mud, brown_mud_02, mud_forest, roots, pine_bark,
bark_willow, wood_planks, wood_planks_grey, mossy_rock, wood_planks_dirt.
Fotografiska assetfilerna INGÅR INTE i ZIP:en. Avsiktligt för att
undvika stora repo-filer. Spelet fungerar offline med inbyggda texter.
Poly Haven: https://polyhaven.com/  (licens CC0 per asset).

TESTER
  python3 -m unittest discover -s tests -v

Verifierat i utvecklingsmiljön:
- 24/24 offline-tester (inkl. befintlig SoldierBrain och hinder)
- CPU-generering av 5 olika 80m-chunks, alla med ändliga koordinater.
- Cirka 0,7–1,4s per chunk offline. Verklig FPS/hack och GLSL-kompilering
  är INTE GPU-verifierade. Testa på GTX 1070.

VIKTIGA BEGRÄNSNINGAR
- Texturer och rundare enkla mesh = steg mot realism, INTE färdiga
  fotorealistiska GLB-modeller av träd/stensamlingar.
- Solen ska röra sig på skärmen vid KAMERAVRIDNING (som i verkligheten),
  men inte flytta sig när soldaten förflyttar sig några meter.
- Nya dekorationer placeras endast intill väggarna. Befintliga fysiska
  hinder och soldatens steering är oförändrade.
- Ökad polygonmängd kan ge CPU-ryck trots förgenerering, mät max-ms.
- Ingen push/merge till main/dev och ingen ändring av Skjutbanans
  fysiska accuracy- eller GameEngine-kod.
