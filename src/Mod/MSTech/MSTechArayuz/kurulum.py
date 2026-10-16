# SPDX-License-Identifier: LGPL-2.1-or-later
"""MSTech arayüzünü başlatır: menü çubuğu yerleşimi, komut şeridi ve görünüm çubuğu."""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from . import PARAM_YOLU, gorunum_cubugu, metin, onay_kosesi, serit

_GORSELLER = ("onay", "gorunum", "serit")
_durum = {"serit": None, "gorunum": None, "onay": None, "tema_gozlemcisi": None}


def _param():
    return App.ParamGet(PARAM_YOLU)


def _ilk_kurulum():
    """Bir kereye mahsus: Dosya/Düzen hızlı erişimi sola, tezgâh seçiciyi sağa, menü çubuğuna al;
    gezinme küpünü sağ alta taşı (sağ üst köşe onay düğmelerinin)."""
    p = _param()
    if p.GetBool("IlkKurulumYapildi", False):
        return
    sol = App.ParamGet("User parameter:BaseApp/MainWindow/MenuBarLeft")
    sag = App.ParamGet("User parameter:BaseApp/MainWindow/MenuBarRight")
    sol.SetInt("File", 0)
    sol.SetInt("Edit", 1)
    sag.SetInt("Workbench", 0)
    App.ParamGet("User parameter:BaseApp/Preferences/NaviCube").SetInt("CornerNaviCube", 3)
    # küp kendi eksen oklarını gösterir; sağ alttaki eksen üçlüsü küple çakışır
    App.ParamGet("User parameter:BaseApp/Preferences/View").SetBool("CornerCoordSystem", False)
    p.SetBool("IlkKurulumYapildi", True)


def serit_acik():
    return _param().GetBool("SeritArayuz", True)


def seridi_ac():
    if _durum["serit"] is not None:
        return
    mw = Gui.getMainWindow()
    # Tux'un araç çubuğu konumlarını geri yükleme özelliği şeritle anlamsız
    App.ParamGet("User parameter:Tux/PersistentToolbars").SetBool("Enabled", False)
    _durum["serit"] = serit.KomutSeridi(mw, _param())
    _durum["gorunum"] = gorunum_cubugu.GorunumCubugu(mw)
    _durum["onay"] = onay_kosesi.OnayKosesi(mw)
    if serit.tezgah_adi_al():
        _durum["gorunum"].kur()
        _durum["gorunum"]._pencere_degisti()


def seridi_kapat():
    for anahtar in _GORSELLER:
        nesne = _durum[anahtar]
        _durum[anahtar] = None
        if nesne is not None and serit.gecerli(nesne):
            nesne.kapat()
    App.ParamGet("User parameter:Tux/PersistentToolbars").SetBool("Enabled", True)


def _komut_durumunu_esitle(acik):
    aksiyon = Gui.getMainWindow().findChild(QtGui.QAction, "MSTech_ArayuzModu")
    if aksiyon is not None and aksiyon.isChecked() != acik:
        aksiyon.blockSignals(True)
        aksiyon.setChecked(acik)
        aksiyon.blockSignals(False)


class ArayuzModuKomutu:
    """Komut şeridi ile klasik araç çubukları arasında geçiş."""

    def GetResources(self):
        return {
            "Pixmap": "mstech-aicad",
            "MenuText": metin.t("serit_komut"),
            "ToolTip": metin.t("serit_ipucu"),
            "Checkable": serit_acik(),
        }

    def IsActive(self):
        return True

    def Activated(self, durum=None):
        acik = bool(durum) if durum is not None else not serit_acik()
        _param().SetBool("SeritArayuz", acik)
        if acik:
            seridi_ac()
        else:
            seridi_kapat()
        _komut_durumunu_esitle(acik)


class ClaudeKomutu:
    """Claude sohbet panelini açar/kapatır."""

    def GetResources(self):
        return {
            "Pixmap": "mstech-aicad",
            "MenuText": "Claude",
            "ToolTip": "Claude yapay zekâ asistanı: söyle, çizsin, düzenlesin.",
        }

    def IsActive(self):
        return True

    def Activated(self):
        dock = _durum.get("claude")
        if dock is None or not serit.gecerli(dock):
            from . import claude_paneli

            dock = _durum["claude"] = claude_paneli.panel_olustur(Gui.getMainWindow())
            dock.show()
        else:
            dock.setVisible(not dock.isVisible())
        if dock.isVisible():
            dock.raise_()


class _GorunumMenusu:
    """Komutu tüm tezgâhlarda Görünüm > Araç çubukları'nın altına ekler."""

    def modifyMenuBar(self):
        return [
            {"insert": "MSTech_ArayuzModu", "menuItem": "Std_ToolBarMenu", "after": ""},
            {"insert": "MSTech_Claude", "menuItem": "MSTech_ArayuzModu", "after": ""},
        ]


class _TemaGozlemcisi:
    """Tema değişince şerit ve görünüm çubuğunun renklerini yeniler."""

    def onChange(self, _grup, neden):
        if neden in ("Theme", "StyleSheet"):
            for anahtar in _GORSELLER:
                nesne = _durum[anahtar]
                if nesne is not None and serit.gecerli(nesne):
                    nesne.stili_yenile()


def _model_sekmesini_one_al(_tezgah=None):
    """Açılışta sol panelde Görevler değil Model sekmesi önde olsun (bir kez)."""
    mw = Gui.getMainWindow()
    try:
        mw.workbenchActivated.disconnect(_model_sekmesini_one_al)
    except (RuntimeError, TypeError):
        pass

    def one_al():
        model = mw.findChild(QtWidgets.QWidget, "Model")
        dock = model.parentWidget() if model is not None else None
        if isinstance(dock, QtWidgets.QDockWidget):
            dock.raise_()

    QtCore.QTimer.singleShot(0, one_al)


def baslat():
    _ilk_kurulum()
    Gui.getMainWindow().workbenchActivated.connect(_model_sekmesini_one_al)
    Gui.addCommand("MSTech_ArayuzModu", ArayuzModuKomutu())
    Gui.addCommand("MSTech_Claude", ClaudeKomutu())
    try:
        from . import claude_paneli

        _durum["claude"] = claude_paneli.panel_olustur(Gui.getMainWindow())
    except Exception as hata:
        App.Console.PrintError(f"Claude paneli oluşturulamadı: {hata}\n")
    Gui.addWorkbenchManipulator(_GorunumMenusu())
    gozlemci = _TemaGozlemcisi()
    App.ParamGet("User parameter:BaseApp/Preferences/MainWindow").Attach(gozlemci)
    _durum["tema_gozlemcisi"] = gozlemci
    if serit_acik():
        seridi_ac()
