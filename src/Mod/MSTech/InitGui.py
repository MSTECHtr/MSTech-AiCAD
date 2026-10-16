# SPDX-License-Identifier: LGPL-2.1-or-later
"""MSTech Ai-CAD arayüzünü (komut şeridi, görünüm çubuğu) başlatır."""

import traceback

import FreeCAD

try:
    from MSTechArayuz import kurulum

    kurulum.baslat()
except Exception:
    # Arayüz eklentisindeki bir hata programın açılmasını engellememeli
    FreeCAD.Console.PrintError("MSTech arayüzü yüklenemedi:\n" + traceback.format_exc())
