# SPDX-License-Identifier: LGPL-2.1-or-later
"""Claude'un FreeCAD'de kullandığı araçlar: Python çalıştırma, belge özeti, ekran görüntüsü.

Araçlar yalnızca ana (GUI) iş parçacığında çağrılmalıdır.
"""

import base64
import contextlib
import io
import os
import tempfile
import traceback

import FreeCAD as App
import FreeCADGui as Gui

ARACLAR = [
    {
        "name": "freecad_python",
        "description": (
            "FreeCAD (MSTech Ai-CAD) içinde Python kodu çalıştırır: parça çizmek, çizim (sketch) "
            "oluşturmak, kesmek, ölçü değiştirmek, montaj kurmak için. FreeCAD, FreeCADGui, Part, "
            "Sketcher ve standart kütüphane kullanılabilir; değişkenler çağrılar arasında korunur. "
            "Her çağrı tek bir geri alma (Ctrl+Z) adımıdır; hata olursa o çağrının değişiklikleri "
            "geri alınır. print() çıktısı, hata ve sonrasında belgenin özeti döner. Uzunluklar mm."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "aciklama": {
                    "type": "string",
                    "description": "Kullanıcıya gösterilecek kısa açıklama (ör. '40x25 dikdörtgen çiz').",
                },
                "kod": {"type": "string", "description": "Çalıştırılacak Python kodu."},
            },
            "required": ["aciklama", "kod"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "belge_ozeti",
        "description": (
            "Etkin belgedeki nesneleri listeler: ad, etiket, tür, görünürlük, sınır kutusu, hacim, "
            "konum; çizimler için kısıtlama sayısı ve serbestlik derecesi. Parçayı incelemek ve "
            "değişikliği doğrulamak için kullan."
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "strict": True,
    },
    {
        "name": "goruntu_al",
        "description": (
            "3B görünümün ekran görüntüsünü alır (parçaya bakmak, sonucu önizlemek için). "
            "İstenen yönden bakar ve isteğe bağlı olarak modeli sığdırır."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "yon": {
                    "type": "string",
                    "enum": ["mevcut", "izometrik", "on", "arka", "ust", "alt", "sag", "sol"],
                    "description": "Bakış yönü.",
                },
                "sigdir": {"type": "boolean", "description": "Modeli görünüme sığdır."},
            },
            "required": ["yon", "sigdir"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]

_YONLER = {
    "izometrik": "viewIsometric",
    "on": "viewFront",
    "arka": "viewRear",
    "ust": "viewTop",
    "alt": "viewBottom",
    "sag": "viewRight",
    "sol": "viewLeft",
}

_ORIJIN = ("App::Origin", "App::Line", "App::Plane", "App::Point")

# Claude'un kodları arasında korunan değişkenler
_ad_alani = {"__name__": "__claude__"}


def _ad_alanini_hazirla():
    if "App" not in _ad_alani:
        exec("import FreeCAD, FreeCADGui\nimport FreeCAD as App, FreeCADGui as Gui", _ad_alani)
        for modul in ("Part", "Sketcher"):
            with contextlib.suppress(ImportError):
                exec(f"import {modul}", _ad_alani)


def _sayi(deger):
    return round(float(deger), 3)


def belge_ozeti():
    belge = App.ActiveDocument
    if belge is None:
        return "Açık belge yok."
    nesneler = [n for n in belge.Objects if n.TypeId not in _ORIJIN]
    satirlar = [f"Belge: {belge.Name} ({belge.Label}), {len(nesneler)} nesne (orijin öğeleri hariç)"]
    for nesne in nesneler:
        parca = [f"- {nesne.Name} '{nesne.Label}' [{nesne.TypeId}]"]
        gorunum = getattr(nesne, "ViewObject", None)
        if gorunum is not None and not gorunum.Visibility:
            parca.append("gizli")
        sekil = getattr(nesne, "Shape", None)
        if sekil is not None and not sekil.isNull():
            kutu = sekil.BoundBox
            parca.append(
                f"kutu=({_sayi(kutu.XMin)},{_sayi(kutu.YMin)},{_sayi(kutu.ZMin)})-"
                f"({_sayi(kutu.XMax)},{_sayi(kutu.YMax)},{_sayi(kutu.ZMax)})"
            )
            if sekil.Volume > 1e-9:
                parca.append(f"hacim={_sayi(sekil.Volume)} mm3")
        if nesne.TypeId == "Sketcher::SketchObject":
            with contextlib.suppress(Exception):
                parca.append(
                    f"geometri={len(nesne.Geometry)} kisit={nesne.ConstraintCount} "
                    f"tam_tanimli={getattr(nesne, 'FullyConstrained', '?')}"
                )
        if "Invalid" in nesne.State or "Error" in nesne.State:
            parca.append(f"DURUM={','.join(nesne.State)}")
        satirlar.append(" ".join(parca))
    return "\n".join(satirlar)


def freecad_python(aciklama, kod):
    _ad_alanini_hazirla()
    belge = App.ActiveDocument
    if belge is not None:
        belge.openTransaction(f"Claude: {aciklama}"[:60])
    cikti = io.StringIO()
    hata = None
    try:
        with contextlib.redirect_stdout(cikti), contextlib.redirect_stderr(cikti):
            exec(compile(kod, "<claude>", "exec"), _ad_alani)
        if App.ActiveDocument is not None:
            App.ActiveDocument.recompute()
    except Exception:
        hata = traceback.format_exc(limit=4)
    if belge is not None and App.getDocument(belge.Name) is not None:
        if hata:
            belge.abortTransaction()
        else:
            belge.commitTransaction()
    if not hata and Gui.ActiveDocument is not None:
        # kullanıcı yapılışı canlı izlesin
        with contextlib.suppress(Exception):
            Gui.ActiveDocument.ActiveView.fitAll()
    Gui.updateGui()
    yanit = []
    if cikti.getvalue().strip():
        yanit.append("Çıktı:\n" + cikti.getvalue()[-6000:])
    if hata:
        yanit.append("HATA (bu çağrının değişiklikleri geri alındı):\n" + hata)
    else:
        yanit.append("Kod başarıyla çalıştı.")
    yanit.append(belge_ozeti())
    return "\n\n".join(yanit), bool(hata)


def goruntu_al(yon="mevcut", sigdir=True):
    gorunum = Gui.ActiveDocument.ActiveView if Gui.ActiveDocument else None
    if gorunum is None or not hasattr(gorunum, "saveImage"):
        return None, "Görüntü alınamadı: etkin bir 3B görünüm yok."
    if yon in _YONLER:
        getattr(gorunum, _YONLER[yon])()
    if sigdir:
        gorunum.fitAll()
    Gui.updateGui()
    dosya = os.path.join(tempfile.gettempdir(), "mstech_claude_goruntu.jpg")
    gorunum.saveImage(dosya, 1024, 640, "Current")
    with open(dosya, "rb") as f:
        veri = base64.standard_b64encode(f.read()).decode("ascii")
    return veri, None


def calistir(ad, girdi):
    """Aracı çalıştırır, tool_result içeriğini ve hata bilgisini döndürür."""
    try:
        if ad == "freecad_python":
            metin, hatali = freecad_python(girdi.get("aciklama", ""), girdi.get("kod", ""))
            return metin, hatali
        if ad == "belge_ozeti":
            return belge_ozeti(), False
        if ad == "goruntu_al":
            veri, hata = goruntu_al(girdi.get("yon", "mevcut"), bool(girdi.get("sigdir", True)))
            if hata:
                return hata, True
            return [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": veri}},
                {"type": "text", "text": "3B görünümün güncel görüntüsü."},
            ], False
        return f"Bilinmeyen araç: {ad}", True
    except Exception:
        return "Araç hatası:\n" + traceback.format_exc(limit=4), True
