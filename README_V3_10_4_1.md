# Skyttegrav V3.10.4.1 – Pillow-kompatibilitet

**Bas: installerad V3.10.4.** Fix för äldre Ubuntu/Pillow-versioner där
`PIL.Image.Transpose` och `PIL.Image.Resampling` inte finns.

Packa upp ZIP:en i roten av `~/infinite_trench_3d_test/` och skriv över
filerna. ZIP:en innehåller hela ersättningsfiler, inga installationsskript.

Ändringar:
- `trench_3d_test.py`: använder äldre och brett stödda
  `Image.FLIP_TOP_BOTTOM` vid initiering av bladtextur.
- `generate_tree_materials.py` och `generate_soldier_v392_materials.py`:
  `Resampling`-konstanter med fallback till äldre Pillow.

Ingen ändring av fiende-AI, mesh, materialbilder, skott eller streaming.
Inga redan genererade PNG-filer behöver ändras.

Validerat: syntax för alla tre filer, PIL-transponering RGBA-data,
resampling på nuvarande testmiljös Pillow 12.3, full ZIP-integritet.
Äldre Pillow är kontrollerat på API-nivå; hela spelet har inte körts här.
