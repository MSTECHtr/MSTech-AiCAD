# SPDX-License-Identifier: LGPL-2.1-or-later
"""Onay köşesi: bir özellik ya da çizim düzenlenirken 3B görünümün sağ üstünde ✓ / ✗.

Düğmeler etkin görev panelinin kendi Tamam/Kapat ve İptal düğmelerine basar; böylece
her komutun kendi kabul/ret mantığı aynen çalışır.
"""

import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from . import metin, stil
from .serit import gecerli

_ARALIK_MS = 250
_KENAR = 10
_KUTU = QtWidgets.QDialogButtonBox
_TAMAM_SIRASI = (_KUTU.Ok, _KUTU.Close, _KUTU.Apply, _KUTU.Yes)
_IPTAL_SIRASI = (_KUTU.Cancel, _KUTU.Abort, _KUTU.No)


class OnayKosesi(QtWidgets.QFrame):
    def __init__(self, mw):
        mdi = mw.findChild(QtWidgets.QMdiArea)
        super().__init__(mdi.viewport())
        self.mw = mw
        self.mdi = mdi
        self._gorev_paneli = None
        self.setObjectName("MSTechOnayKosesi")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        duzen = QtWidgets.QHBoxLayout(self)
        duzen.setContentsMargins(3, 3, 3, 3)
        duzen.setSpacing(2)
        self._tamam = self._dugme(":/icons/edit_OK.svg", metin.t("onay_tamam"))
        self._iptal = self._dugme(":/icons/edit_Cancel.svg", metin.t("onay_iptal"))
        self._tamam.clicked.connect(lambda: self._bas(_TAMAM_SIRASI))
        self._iptal.clicked.connect(lambda: self._bas(_IPTAL_SIRASI))
        duzen.addWidget(self._tamam)
        duzen.addWidget(self._iptal)
        self.stili_yenile()
        self.hide()

        self.mdi.viewport().installEventFilter(self)
        self._zaman = QtCore.QTimer(self)
        self._zaman.setInterval(_ARALIK_MS)
        self._zaman.timeout.connect(self._denetle)
        self._zaman.start()

    def stili_yenile(self):
        self.setStyleSheet(stil.onay_kosesi())

    def _dugme(self, simge, ipucu):
        dugme = QtWidgets.QToolButton(self)
        dugme.setIcon(QtGui.QIcon(simge))
        dugme.setIconSize(QtCore.QSize(30, 30))
        dugme.setAutoRaise(True)
        dugme.setFocusPolicy(QtCore.Qt.NoFocus)
        dugme.setToolTip(ipucu)
        return dugme

    def _dugme_kutusu(self):
        """Etkin görev panelinin görünür düğme kutusu."""
        if not gecerli(self._gorev_paneli):
            self._gorev_paneli = None
            for yigin in self.mw.findChildren(QtWidgets.QStackedWidget):
                if yigin.inherits("Gui::TaskView::TaskView"):
                    self._gorev_paneli = yigin
                    break
        if self._gorev_paneli is None:
            return None
        for kutu in self._gorev_paneli.findChildren(QtWidgets.QDialogButtonBox):
            if kutu.isVisible():
                return kutu
        return None

    @staticmethod
    def _bul(kutu, sira):
        for tur in sira:
            dugme = kutu.button(tur)
            if dugme is not None and dugme.isVisible() and dugme.isEnabled():
                return dugme
        return None

    def _bas(self, sira):
        kutu = self._dugme_kutusu()
        dugme = self._bul(kutu, sira) if kutu is not None else None
        if dugme is not None:
            dugme.click()
        self._denetle()

    def _denetle(self):
        alt = self.mdi.activeSubWindow()
        gorunum = alt.widget() if gecerli(alt) else None
        kutu = None
        if gecerli(gorunum) and gorunum.inherits("Gui::View3DInventor") and Gui.Control.activeDialog():
            kutu = self._dugme_kutusu()
        if kutu is None:
            if self.isVisible():
                self.hide()
            return
        tamam = self._bul(kutu, _TAMAM_SIRASI)
        iptal = self._bul(kutu, _IPTAL_SIRASI)
        self._tamam.setVisible(tamam is not None)
        self._iptal.setVisible(iptal is not None)
        if tamam is None and iptal is None:
            self.hide()
            return
        if not self.isVisible():
            self.show()
        self.raise_()
        self._konumla()

    def _konumla(self):
        alan = self.parentWidget()
        self.adjustSize()
        self.move(max(0, alan.width() - self.width() - _KENAR), _KENAR)

    def eventFilter(self, nesne, olay):
        if olay.type() == QtCore.QEvent.Resize and self.isVisible():
            self._konumla()
        return False

    def kapat(self):
        self._zaman.stop()
        try:
            self.mdi.viewport().removeEventFilter(self)
        except RuntimeError:
            pass
        self.hide()
        self.deleteLater()
