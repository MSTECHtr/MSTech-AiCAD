# SPDX-License-Identifier: LGPL-2.1-or-later
"""3B görünümün üst ortasında yüzen görünüm çubuğu: sığdır, yön, görüntü stili, kesit."""

from PySide import QtCore, QtGui, QtWidgets

from . import stil
from .serit import GORUNUM_CUBUGU, YUZEN, KomutDugmesi, ayni, ayrac, fc_cubugu_mu, gecerli

KOMUTLAR = (
    "Std_ViewFitAll",
    "Std_ViewFitSelection",
    "Std_ViewBoxZoom",
    None,
    "Std_ViewGroup",
    "Std_AlignToSelection",
    None,
    "Std_DrawStyle",
    "Std_ToggleClipPlane",
    None,
    "Std_ToggleVisibility",
    "Std_SetAppearance",
)

_UST_BOSLUK = 8


class GorunumCubugu(QtWidgets.QFrame):
    def __init__(self, mw):
        mdi = mw.findChild(QtWidgets.QMdiArea)
        super().__init__(mdi.viewport())
        self.mw = mw
        self.mdi = mdi
        self.setObjectName("MSTechGorunumCubugu")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self._duzen = QtWidgets.QHBoxLayout(self)
        self._duzen.setContentsMargins(4, 3, 4, 3)
        self._duzen.setSpacing(1)
        self._imza = None
        self.stili_yenile()
        self.hide()

        self.mdi.viewport().installEventFilter(self)
        self.mdi.subWindowActivated.connect(self._pencere_degisti)
        mw.workbenchActivated.connect(self.kur)

    def stili_yenile(self):
        self.setStyleSheet(stil.gorunum_cubugu())

    def _kaynaklar(self):
        """Komut adı -> (eylem, kaynak düğme). Açılır menüler FreeCAD'in View çubuğundan alınır."""
        kaynaklar = {}
        for cubuk in self.mw.findChildren(QtWidgets.QToolBar, GORUNUM_CUBUGU):
            if fc_cubugu_mu(cubuk) and ayni(cubuk.parentWidget(), self.mw):
                for a in cubuk.actions():
                    if a.objectName():
                        kaynaklar.setdefault(a.objectName(), (a, cubuk.widgetForAction(a)))
        for ad in KOMUTLAR:
            if ad and ad not in kaynaklar:
                aksiyon = self.mw.findChild(QtGui.QAction, ad)
                if aksiyon is not None:
                    kaynaklar[ad] = (aksiyon, None)
        return kaynaklar

    @QtCore.Slot()
    def kur(self, _tezgah=None):
        kaynaklar = self._kaynaklar()
        imza = tuple(ad for ad in KOMUTLAR if ad is None or ad in kaynaklar)
        if imza == self._imza:
            return
        self._imza = imza
        while self._duzen.count():
            oge = self._duzen.takeAt(0)
            if oge.widget() is not None:
                oge.widget().deleteLater()
        onceki_ayrac = True
        for ad in imza:
            if ad is None:
                if not onceki_ayrac:
                    self._duzen.addWidget(ayrac(self, kisa=True), 0, QtCore.Qt.AlignVCenter)
                    onceki_ayrac = True
                continue
            aksiyon, kaynak = kaynaklar[ad]
            self._duzen.addWidget(KomutDugmesi(aksiyon, kaynak, YUZEN, self))
            onceki_ayrac = False
        self.adjustSize()
        self._konumla()

    def _pencere_degisti(self, alt_pencere=None):
        alt_pencere = alt_pencere or self.mdi.activeSubWindow()
        gorunum = alt_pencere.widget() if gecerli(alt_pencere) else None
        if gecerli(gorunum) and gorunum.inherits("Gui::View3DInventor"):
            if self._imza is None:
                self.kur()
            self.show()
            self.raise_()
            self._konumla()
        else:
            self.hide()

    def _konumla(self):
        alan = self.parentWidget()
        if alan is None:
            return
        self.adjustSize()
        self.move(max(0, (alan.width() - self.width()) // 2), _UST_BOSLUK)

    def eventFilter(self, nesne, olay):
        if olay.type() == QtCore.QEvent.Resize:
            self._konumla()
        elif olay.type() == QtCore.QEvent.ChildAdded and self.isVisible():
            # yeni açılan alt pencere çubuğun üstüne çıkmasın
            QtCore.QTimer.singleShot(0, self.raise_)
        return False

    def kapat(self):
        try:
            self.mdi.viewport().removeEventFilter(self)
            self.mdi.subWindowActivated.disconnect(self._pencere_degisti)
            self.mw.workbenchActivated.disconnect(self.kur)
        except (RuntimeError, TypeError):
            pass
        self.hide()
        self.deleteLater()
