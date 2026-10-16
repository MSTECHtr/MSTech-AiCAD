# SPDX-License-Identifier: LGPL-2.1-or-later
"""Arayüz metinleri. Arayüz dili Türkçe değilse İngilizce metin kullanılır."""

import FreeCADGui as Gui

_METINLER = {
    # şerit sekmeleri
    "ozellikler": ("Özellikler", "Features"),
    "cizim": ("Çizim", "Sketch"),
    "kisitlar": ("Kısıtlamalar", "Constraints"),
    "cizim_araclari": ("Çizim Araçları", "Sketch Tools"),
    "parca": ("Parça", "Part"),
    "montaj": ("Montaj", "Assembly"),
    "teknik_sayfa": ("Sayfa ve Görünüşler", "Sheets & Views"),
    "teknik_olcu": ("Ölçülendirme", "Dimensions"),
    "teknik_aciklama": ("Açıklamalar", "Annotations"),
    "degerlendir": ("Değerlendir", "Evaluate"),
    "araclar": ("Araçlar", "Tools"),
    # şerit ve komutlar
    "serit_adi": ("Komut şeridi", "Command ribbon"),
    "gorunum_adi": ("Görünüm çubuğu", "View toolbar"),
    "metin_goster": ("Simgelerin altında metin göster", "Show text under icons"),
    "klasik": ("Klasik araç çubuklarına dön", "Switch to classic toolbars"),
    "serit_komut": ("MSTech komut şeridi", "MSTech command ribbon"),
    "onay_tamam": ("Tamam", "OK"),
    "onay_iptal": ("İptal", "Cancel"),
    "serit_ipucu": (
        "Komutları sekmeli komut şeridinde toplar. Kapalıyken klasik araç çubukları kullanılır.",
        "Groups commands in a tabbed command ribbon. When off, the classic toolbars are used.",
    ),
}


def _turkce_mi():
    try:
        dil = Gui.getLocale().lower()
    except Exception:
        return True
    return dil.startswith(("turkish", "tr"))


_TURKCE = _turkce_mi()


def t(anahtar):
    tr, en = _METINLER[anahtar]
    return tr if _TURKCE else en
