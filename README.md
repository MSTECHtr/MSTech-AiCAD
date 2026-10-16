<img src="src/Gui/Icons/mstech-aicad.svg" height="100" width="100">

# MSTech Ai-CAD

**Yapay zekâ destekli 3B parametrik CAD.** [FreeCAD](https://www.freecad.org) tabanlıdır.

## Özellikler

- **SolidWorks tarzı arayüz:** sekmeli komut şeridi (büyük ana komutlar, küçük ikincil komut sütunları),
  3B görünümde yüzen görünüm çubuğu, sağ üstte ✓/✗ onay köşesi, model ağacının yanında açılan görev paneli.
- **Claude asistanı:** sağdaki panelde ne istediğini yaz; Claude soru sorar, parçayı adım adım çizer,
  inceler, düzenler. Her adım Ctrl+Z ile geri alınabilir.
- **MSTech Açık / Koyu temalar,** SolidWorks fare kontrolleri, Türkçe arayüz.

## Claude'u kullanmak

İki yol var:

1. **Claude aboneliği (Pro/Max):** panel bilgisayardaki [Claude Code](https://claude.com/claude-code)'u
   kullanır. İlk açılışta panel Claude Code'u kurmayı ve tarayıcıda giriş yapmayı tek düğmeyle sunar.
   Bu yol yalnızca kendi bilgisayarında, kendi kullanımın içindir.
2. **Anthropic API anahtarı:** panelde *API anahtarı* düğmesiyle girilir; kullanım API hesabına
   ücretlendirilir.

## Derleme (Linux)

[pixi](https://pixi.sh) gerekir (bağımlılıkları kendisi kurar, sudo istemez).

```bash
git clone https://github.com/<kullanıcı>/MSTech-AiCAD.git && cd MSTech-AiCAD
pixi install
pixi run cmake --preset conda-linux-release -B build/release -DENABLE_DEVELOPER_TESTS=OFF
pixi run cmake --build build/release
pixi run build/release/bin/FreeCAD
```

Klasör yolunda boşluk olmamalıdır (FreeCAD'in derleme betikleri boşluklu yollarda bozuluyor).

## Lisans

LGPL-2.1-or-later. MSTech Ai-CAD, FreeCAD'in değiştirilmiş bir sürümüdür; FreeCAD'in telif ve lisans
bildirimleri korunmuştur (bkz. [LICENSE](LICENSE)). İlk commit değiştirilmemiş FreeCAD kaynağıdır
(main, d732e2f); MSTech değişiklikleri sonraki commit'lerdedir.
