# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sekmeli komut şeridi.

FreeCAD'in araç çubukları gizlenir ama yerinde kalır ve komutların sahibi olmaya
devam eder; şerit aynı QAction nesnelerine bağlı düğmeler gösterir. Böylece
komutların etkinliği, kısayollar ve bağlamsal araç çubukları (ör. çizim düzenleme
modu) FreeCAD'in kendi mantığıyla çalışır.
"""

import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from . import metin, stil

try:
    import shiboken6 as shiboken
except ImportError:
    import shiboken2 as shiboken

# Gui::ToolBarItem::DefaultVisibility::Hidden
_POLITIKA_GIZLI = 1

# Şeride alınmayan araç çubukları
MENU_CUBUGUNDAKILER = ("File", "Edit", "Workbench")  # menü çubuğundaki hızlı erişim
GORUNUM_CUBUGU = "View"  # 3B görünümün üstündeki yüzen çubukta

# "cubuklar": FreeCAD araç çubuğu adları, "komutlar": tek tek komutlar (None = ayraç),
# "haric": bu sekmede gösterilmeyen komutlar, "son": genel sekmelerden sonra gelir.
SEKMELER = (
    {
        "kimlik": "ozellikler",
        "cubuklar": (
            "Part Design Helper Features",
            "Part Design Modeling Features",
            "Part Design Dress-Up Features",
            "Part Design Transformation Features",
        ),
        "haric": ("Sketcher_ValidateSketch", "Part_CheckGeometry"),
    },
    {"kimlik": "parca", "cubuklar": ("Solids", "Part Tools", "Boolean Tools")},
    {"kimlik": "cizim", "cubuklar": ("Sketcher", "Edit Mode", "Geometries", "Visual Helpers")},
    {"kimlik": "kisitlar", "cubuklar": ("Constraints",)},
    {
        "kimlik": "cizim_araclari",
        "cubuklar": ("Sketcher Tools", "B-Spline Tools", "Sketcher Edit Tools"),
    },
    {"kimlik": "montaj", "cubuklar": ("Assembly", "Assembly Joints")},
    {
        "kimlik": "degerlendir",
        "son": True,
        "komutlar": (
            "Std_Measure",
            "Std_MassProperties",
            None,
            "Part_CheckGeometry",
            "Sketcher_ValidateSketch",
        ),
    },
    {
        "kimlik": "araclar",
        "son": True,
        "cubuklar": ("Structure", "Help"),
        "komutlar": (
            "MSTech_Claude",
            None,
            "Std_DlgMacroRecord",
            "Std_DlgMacroExecute",
            None,
            "Std_DlgCustomize",
            "Std_DlgPreferences",
            "MSTech_ArayuzModu",
        ),
    },
)


def _teknik_resim_sekmesi(cubuk_adi):
    """TechDraw'ın çok sayıdaki araç çubuğunu üç sekmede toplar."""
    ad = cubuk_adi.lower()
    if "dimension" in ad:
        return "teknik_olcu"
    if any(k in ad for k in ("page", "view", "stack", "file", "clip")):
        return "teknik_sayfa"
    return "teknik_aciklama"


def tezgah_adi_al():
    """Etkin tezgâhın adı; açılışta henüz tezgâh yokken boş."""
    try:
        return Gui.activeWorkbench().name()
    except Exception:  # tezgâh yokken AssertionError, NoneWorkbench'te AttributeError
        return ""


def gecerli(nesne):
    return nesne is not None and shiboken.isValid(nesne)


def ayni(a, b):
    return gecerli(a) and gecerli(b) and shiboken.getCppPointer(a)[0] == shiboken.getCppPointer(b)[0]


def fc_cubugu_mu(cubuk):
    return cubuk.metaObject().className() == "Gui::ToolBar"


def kullanilabilir_mi(cubuk):
    """FreeCAD bu araç çubuğunu şu an sunuyor mu (bağlamsal çubuklar düzenleme dışında sunulmaz)."""
    gecis = cubuk.toggleViewAction()
    politika = gecis.property("DefaultVisibility")
    return gecis.isVisible() and politika != _POLITIKA_GIZLI


def _temiz(yazi):
    yazi = yazi.replace("&&", "\0").replace("&", "").replace("\0", "&")
    return yazi.replace("…", "").rstrip(". ").strip()


def _metni_sar(yazi, sinir=11):
    """Uzun düğme yazılarını SolidWorks'teki gibi iki satıra böler."""
    if len(yazi) <= sinir or " " not in yazi:
        return yazi
    orta = len(yazi) / 2
    i = min((i for i, c in enumerate(yazi) if c == " "), key=lambda i: abs(i - orta))
    return yazi[:i] + "\n" + yazi[i + 1 :]


def ayrac(ebeveyn, kisa=False):
    cizgi = QtWidgets.QFrame(ebeveyn)
    cizgi.setObjectName("MSTechAyrac")
    cizgi.setFixedWidth(1)
    if kisa:
        cizgi.setFixedHeight(28)
    cizgi.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
    return cizgi


# Düğme boyları: (simge, metinli stil)
BUYUK, KUCUK, YUZEN = "buyuk", "kucuk", "yuzen"
# Şerit sayfası yazı seviyeleri
TAM, ORTA, SIMGE = "tam", "orta", "simge"
_BOYLAR = {
    BUYUK: (28, QtCore.Qt.ToolButtonTextUnderIcon),
    KUCUK: (16, QtCore.Qt.ToolButtonTextBesideIcon),
    YUZEN: (20, QtCore.Qt.ToolButtonIconOnly),
}


class KomutDugmesi(QtWidgets.QToolButton):
    """Bir FreeCAD komutunun QAction'ına bağlı düğme."""

    def __init__(self, aksiyon, kaynak_dugme, boy, ebeveyn):
        super().__init__(ebeveyn)
        self._aksiyon = aksiyon
        self.boy = boy
        self._kaynak_menu = None
        self.setAutoRaise(True)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        simge = _BOYLAR[boy][0]
        self.setIconSize(QtCore.QSize(simge, simge))

        # Açılır komut grupları (ör. desenler): menü FreeCAD'de araç çubuğu düğmesinde durur.
        # Menünün kendisi yerine eylemleri kopyalanır; FreeCAD araç çubuğunu yeniden
        # kursa bile bu düğme çalışmaya devam eder.
        if isinstance(kaynak_dugme, QtWidgets.QToolButton) and kaynak_dugme.menu() is not None:
            self._kaynak_menu = kaynak_dugme.menu()
            menu = QtWidgets.QMenu(self)
            menu.addActions(self._kaynak_menu.actions())
            menu.aboutToShow.connect(self._menuyu_hazirla)
            self.setMenu(menu)
            self.setPopupMode(kaynak_dugme.popupMode())

        aksiyon.changed.connect(self._esitle)
        self.clicked.connect(self._tiklandi)
        self.metin_modu(True)
        self._esitle()

    def metin_modu(self, metinli):
        stil_ = _BOYLAR[self.boy][1] if metinli else QtCore.Qt.ToolButtonIconOnly
        if stil_ != self.toolButtonStyle():
            self.setToolButtonStyle(stil_)
            # [toolButtonStyle=...] stil kuralları yeniden değerlendirilsin
            self.style().unpolish(self)
            self.style().polish(self)

    def _esitle(self):
        a = self._aksiyon
        if not gecerli(a):
            self.hide()
            return
        self.setIcon(a.icon())
        yazi = _temiz(a.iconText() or a.text())
        self.setText(_metni_sar(yazi) if self.boy == BUYUK else yazi)
        self.setToolTip(a.toolTip())
        self.setStatusTip(a.statusTip())
        self.setEnabled(a.isEnabled())
        self.setCheckable(a.isCheckable())
        if a.isCheckable():
            self.setChecked(a.isChecked())
        self.setVisible(a.isVisible())

    def _tiklandi(self):
        if gecerli(self._aksiyon) and self._aksiyon.isEnabled():
            self._aksiyon.trigger()
        self._esitle()

    def _menuyu_hazirla(self):
        kaynak = self._kaynak_menu
        if not gecerli(kaynak):
            return
        # FreeCAD bazı grupların durumunu menü açılırken günceller
        kaynak.aboutToShow.emit()
        menu = self.menu()
        menu.clear()
        menu.addActions(kaynak.actions())


def _parcala(grup):
    """Ayraçlarla ayrılmış parçalar."""
    parcalar, parca = [], []
    for oge in grup:
        if oge is None:
            if parca:
                parcalar.append(parca)
            parca = []
        else:
            parca.append(oge)
    if parca:
        parcalar.append(parca)
    return parcalar


class SeritSayfasi(QtWidgets.QScrollArea):
    """Bir sekmenin düğmeleri, SolidWorks CommandManager düzeninde: her parçanın ilk iki komutu
    büyük, kalanlar üçerli sütunlarda küçük. Sığmazsa yalnızca simgeler gösterilir."""

    def __init__(self, gruplar, ebeveyn):
        super().__init__(ebeveyn)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        icerik = QtWidgets.QWidget()
        icerik.setObjectName("MSTechSeritSayfa")
        duzen = QtWidgets.QHBoxLayout(icerik)
        duzen.setContentsMargins(6, 2, 6, 2)
        duzen.setSpacing(2)
        self.dugmeler = []
        for gi, grup in enumerate(gruplar):
            for pi, parca in enumerate(_parcala(grup)):
                if gi or pi:
                    duzen.addSpacing(3)
                    duzen.addWidget(ayrac(icerik, kisa=pi > 0), 0, QtCore.Qt.AlignVCenter)
                    duzen.addSpacing(3)
                buyukler, kucukler = (parca, []) if len(parca) <= 3 else (parca[:2], parca[2:])
                for aksiyon, kaynak in buyukler:
                    dugme = KomutDugmesi(aksiyon, kaynak, BUYUK, icerik)
                    duzen.addWidget(dugme, 0, QtCore.Qt.AlignVCenter)
                    self.dugmeler.append(dugme)
                for i in range(0, len(kucukler), 3):
                    sutun = QtWidgets.QVBoxLayout()
                    sutun.setSpacing(0)
                    sutun.setContentsMargins(0, 0, 0, 0)
                    for aksiyon, kaynak in kucukler[i : i + 3]:
                        dugme = KomutDugmesi(aksiyon, kaynak, KUCUK, icerik)
                        sutun.addWidget(dugme, 0, QtCore.Qt.AlignLeft)
                        self.dugmeler.append(dugme)
                    sutun.addStretch(1)
                    duzen.addLayout(sutun)
        duzen.addStretch(1)
        self.setWidget(icerik)
        self._seviye = TAM
        self._genislikler = {}

    def _mod(self, seviye):
        self._seviye = seviye
        for d in self.dugmeler:
            d.metin_modu(seviye == TAM or (seviye == ORTA and d.boy == BUYUK))

    def _genislik(self, seviye):
        """Bu seviyede stil sayfası uygulanmış gerçek genişlik (önbellekli)."""
        if seviye not in self._genislikler:
            self._mod(seviye)
            for d in self.dugmeler:
                d.ensurePolished()
            self.widget().layout().activate()
            self._genislikler[seviye] = self.widget().sizeHint().width()
        return self._genislikler[seviye]

    def onbellegi_sil(self):
        self._genislikler.clear()

    def uyarla(self, metinli, genislik):
        """Sığan en zengin görünüm: tüm yazılar > yalnızca büyük düğmelerin yazısı > simgeler."""
        seviyeler = (TAM, ORTA, SIMGE) if metinli else (SIMGE,)
        hedef = next((sv for sv in seviyeler if self._genislik(sv) <= genislik), seviyeler[-1])
        if hedef != self._seviye:
            self._mod(hedef)


class KomutSeridi(QtWidgets.QWidget):
    """Ana pencerenin üstündeki sekmeli komut şeridi (sekmeler altta)."""

    def __init__(self, mw, param):
        super().__init__()
        self.mw = mw
        self._param = param
        self.setObjectName("MSTechSerit")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._baglam_menusu)

        self._sayfalar = QtWidgets.QStackedWidget(self)
        self._sekmeler = QtWidgets.QTabBar(self)
        self._sekmeler.setShape(QtWidgets.QTabBar.RoundedSouth)
        self._sekmeler.setDrawBase(False)
        self._sekmeler.setExpanding(False)
        self._sekmeler.setUsesScrollButtons(True)
        self._sekmeler.setFocusPolicy(QtCore.Qt.NoFocus)
        self._sekmeler.currentChanged.connect(self._sekme_degisti)

        duzen = QtWidgets.QVBoxLayout(self)
        duzen.setContentsMargins(0, 0, 0, 0)
        duzen.setSpacing(0)
        duzen.addWidget(self._sayfalar)
        alt = QtWidgets.QHBoxLayout()
        alt.setContentsMargins(6, 0, 6, 0)
        alt.addWidget(self._sekmeler)
        alt.addStretch(1)
        duzen.addLayout(alt)

        # Şerit, FreeCAD'in yönetmediği sade bir QToolBar içinde durur
        self.kap = QtWidgets.QToolBar(metin.t("serit_adi"), mw)
        self.kap.setObjectName("MSTech_SeritCubugu")
        self.kap.setMovable(False)
        self.kap.setFloatable(False)
        self.kap.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)
        self.kap.toggleViewAction().setVisible(False)
        self.kap.layout().setContentsMargins(0, 0, 0, 0)
        self.kap.layout().setSpacing(0)
        self.kap.addWidget(self)
        mw.addToolBar(QtCore.Qt.TopToolBarArea, self.kap)
        self.stili_yenile()

        self._izlenen = {}  # ad -> FreeCAD araç çubuğu (olay süzgeci ve sinyal bağlı)
        self._imza = None
        self._kimlikler = []
        self._sunulan = set()
        self._tezgah = None
        self._son_sekme = {}  # tezgâh -> en son seçilen sekme
        self._baglam_oncesi = None  # bağlamsal sekmeye geçmeden önceki sekme
        self._kurulum_bekliyor = False
        self._gizlenecek = []

        mw.workbenchActivated.connect(self._tezgah_degisti)
        self.planla()

    # --- görünüm ----------------------------------------------------------------

    def metinli(self):
        return self._param.GetBool("SeritMetinleri", True)

    def stili_yenile(self):
        self.kap.setStyleSheet(
            stil.serit()
            + "QToolBar#MSTech_SeritCubugu { border: none; padding: 0px; margin: 0px;"
            " spacing: 0px; background: transparent; }"
        )
        fm = self.fontMetrics()
        # metinli düğme: simge + iki satır yazı + kenar boşlukları
        self._sayfalar.setFixedHeight(28 + 2 * fm.lineSpacing() + 18)
        for i in range(self._sayfalar.count()):
            self._sayfalar.widget(i).onbellegi_sil()
        self._uyarla()

    def resizeEvent(self, olay):
        super().resizeEvent(olay)
        self._uyarla()

    def _uyarla(self):
        sayfa = self._sayfalar.currentWidget()
        if sayfa is not None:
            sayfa.uyarla(self.metinli(), self._sayfalar.width())

    def _baglam_menusu(self, konum):
        menu = QtWidgets.QMenu(self)
        metinler = menu.addAction(metin.t("metin_goster"))
        metinler.setCheckable(True)
        metinler.setChecked(self.metinli())
        menu.addSeparator()
        klasik = menu.addAction(metin.t("klasik"))
        secim = menu.exec(self.mapToGlobal(konum))
        if secim is metinler:
            self._param.SetBool("SeritMetinleri", metinler.isChecked())
            self._uyarla()
        elif secim is klasik:
            Gui.runCommand("MSTech_ArayuzModu", 0)

    # --- FreeCAD araç çubukları ---------------------------------------------------

    def _fc_cubuklari(self):
        return [
            c
            for c in self.mw.findChildren(QtWidgets.QToolBar)
            if c.objectName() and fc_cubugu_mu(c) and ayni(c.parentWidget(), self.mw)
        ]

    def _gizlenmeli_mi(self, cubuk):
        return cubuk.objectName() not in MENU_CUBUGUNDAKILER and ayni(cubuk.parentWidget(), self.mw)

    def _izle(self, cubuk):
        ad = cubuk.objectName()
        onceki = self._izlenen.get(ad)
        if ayni(onceki, cubuk):
            return
        self._izlenen[ad] = cubuk
        cubuk.installEventFilter(self)
        cubuk.toggleViewAction().changed.connect(self.planla)

    def eventFilter(self, nesne, olay):
        # FreeCAD bir araç çubuğunu gösterirse (bağlam değişimi, menüden açma) gizle.
        # Gizleme kuyruğa alınır: boyama düşük öncelikli olduğu için ekrana hiç yansımaz.
        if olay.type() == QtCore.QEvent.Show and isinstance(nesne, QtWidgets.QToolBar):
            if self._gizlenmeli_mi(nesne):
                self._gizlenecek.append(nesne)
                QtCore.QMetaObject.invokeMethod(self, "_bekleyenleri_gizle", QtCore.Qt.QueuedConnection)
        return False

    @QtCore.Slot()
    def _bekleyenleri_gizle(self):
        bekleyenler, self._gizlenecek = self._gizlenecek, []
        for cubuk in bekleyenler:
            if gecerli(cubuk) and self._gizlenmeli_mi(cubuk):
                cubuk.hide()

    # --- kurulum --------------------------------------------------------------------

    def _tezgah_degisti(self, _ad=None):
        # Sinyal FreeCAD araç çubuklarını kurduktan hemen sonra gelir; ekran boyanmadan
        # önce eşzamanlı gizlemek araç çubuklarının bir an görünmesini engeller.
        self._kur()

    @QtCore.Slot()
    def planla(self):
        if not self._kurulum_bekliyor:
            self._kurulum_bekliyor = True
            QtCore.QMetaObject.invokeMethod(self, "_kur", QtCore.Qt.QueuedConnection)

    @QtCore.Slot()
    def _kur(self):
        self._kurulum_bekliyor = False
        if not gecerli(self.mw):
            return
        tezgah_adi = tezgah_adi_al()

        cubuklar = self._fc_cubuklari()
        for c in cubuklar:
            self._izle(c)
            if self._gizlenmeli_mi(c) and c.isVisible():
                c.hide()

        sunulan = [c for c in cubuklar if kullanilabilir_mi(c)]
        model = self._model(sunulan, tezgah_adi, cubuklar)
        imza = (
            tezgah_adi,
            tuple(
                (k, tuple(shiboken.getCppPointer(o[0])[0] for g in gr for o in g if o))
                for k, _, gr in model
            ),
        )
        sunulan_adlar = {c.objectName() for c in sunulan}
        tezgah_degisti = tezgah_adi != self._tezgah
        gelen = set() if tezgah_degisti else sunulan_adlar - self._sunulan
        giden = set() if tezgah_degisti else self._sunulan - sunulan_adlar
        self._sunulan = sunulan_adlar
        self._tezgah = tezgah_adi

        if imza != self._imza:
            self._imza = imza
            self._sayfalari_kur(model)

        self._sekme_sec(model, tezgah_degisti, gelen, giden)

    def _ogeler(self, cubuk, haric=()):
        """Araç çubuğundaki (eylem, kaynak düğme) çiftleri; ayraçlar None."""
        ogeler = []
        for a in cubuk.actions():
            if a.isSeparator():
                if ogeler and ogeler[-1] is not None:
                    ogeler.append(None)
                continue
            if isinstance(a, QtWidgets.QWidgetAction):
                continue
            if a.objectName() in haric:
                continue
            ogeler.append((a, cubuk.widgetForAction(a)))
        while ogeler and ogeler[-1] is None:
            ogeler.pop()
        return ogeler

    def _komut_ogeleri(self, adlar, kaynaklar):
        ogeler = []
        for ad in adlar:
            if ad is None:
                if ogeler and ogeler[-1] is not None:
                    ogeler.append(None)
                continue
            oge = kaynaklar.get(ad)
            if oge is None:
                aksiyon = self.mw.findChild(QtGui.QAction, ad)
                oge = (aksiyon, None) if aksiyon is not None else None
            if oge is not None:
                ogeler.append(oge)
        while ogeler and ogeler[-1] is None:
            ogeler.pop()
        return ogeler

    def _model(self, sunulan, tezgah_adi, cubuklar):
        """[(kimlik, başlık, [grup, ...]), ...]; grup = [(eylem, kaynak düğme) | None, ...]"""
        adlar = {c.objectName(): c for c in sunulan}
        kaynaklar = {}
        for c in cubuklar:
            for a in c.actions():
                if a.objectName() and not a.isSeparator():
                    kaynaklar.setdefault(a.objectName(), (a, c.widgetForAction(a)))

        kullanilan = set(MENU_CUBUGUNDAKILER) | {GORUNUM_CUBUGU}
        bas, son = [], []
        for tanim in SEKMELER:
            gruplar = []
            for ad in tanim.get("cubuklar", ()):
                if ad in adlar:
                    gruplar.append(self._ogeler(adlar[ad], tanim.get("haric", ())))
                    kullanilan.add(ad)
            if "komutlar" in tanim:
                gruplar.append(self._komut_ogeleri(tanim["komutlar"], kaynaklar))
            gruplar = [g for g in gruplar if g]
            if gruplar:
                kimlik = tanim["kimlik"]
                (son if tanim.get("son") else bas).append((kimlik, metin.t(kimlik), gruplar))

        genel = []
        teknik = {}
        for c in sunulan:
            ad = c.objectName()
            if ad in kullanilan:
                continue
            ogeler = self._ogeler(c)
            if not ogeler:
                continue
            if tezgah_adi == "TechDrawWorkbench":
                kimlik = _teknik_resim_sekmesi(ad)
                if kimlik not in teknik:
                    teknik[kimlik] = (kimlik, metin.t(kimlik), [])
                    genel.append(teknik[kimlik])
                teknik[kimlik][2].append(ogeler)
            else:
                genel.append((ad, c.windowTitle(), [ogeler]))
        return bas + genel + son

    def _sayfalari_kur(self, model):
        secili = self._secili_kimlik()
        self._sekmeler.blockSignals(True)
        while self._sekmeler.count():
            self._sekmeler.removeTab(0)
        while self._sayfalar.count():
            sayfa = self._sayfalar.widget(0)
            self._sayfalar.removeWidget(sayfa)
            sayfa.deleteLater()
        self._kimlikler = []
        for kimlik, baslik, gruplar in model:
            self._sayfalar.addWidget(SeritSayfasi(gruplar, self._sayfalar))
            self._sekmeler.addTab(baslik)
            self._kimlikler.append(kimlik)
        if secili in self._kimlikler:
            self._sekmeleri_ayarla(self._kimlikler.index(secili))
        self._sekmeler.blockSignals(False)

    def _secili_kimlik(self):
        i = self._sekmeler.currentIndex()
        return self._kimlikler[i] if 0 <= i < len(self._kimlikler) else None

    def _sekmeleri_ayarla(self, i):
        self._sekmeler.setCurrentIndex(i)
        self._sayfalar.setCurrentIndex(i)
        self._uyarla()

    def _sekme_sec(self, model, tezgah_degisti, gelen, giden):
        """gelen/giden: bu tezgâhta yeni sunulan / artık sunulmayan bağlamsal araç çubukları."""
        if not self._kimlikler:
            return
        hedef = None
        if gelen:
            # ör. çizim düzenlemeye girildi: ilgili sekmeye geç
            for kimlik, _, gruplar in model:
                if any(self._grup_cubugu(g) in gelen for g in gruplar):
                    hedef = kimlik
                    break
            if hedef is not None and self._baglam_oncesi is None:
                self._baglam_oncesi = self._secili_kimlik()
        elif tezgah_degisti:
            hedef = self._son_sekme.get(self._tezgah)
            self._baglam_oncesi = None
        elif giden and self._baglam_oncesi:
            # bağlam bitti (ör. çizim düzenlemeden çıkıldı): önceki sekmeye dön
            hedef = self._baglam_oncesi
            self._baglam_oncesi = None
        if hedef not in self._kimlikler:
            hedef = self._secili_kimlik() or self._kimlikler[0]
        self._sekmeler.blockSignals(True)
        self._sekmeleri_ayarla(self._kimlikler.index(hedef))
        self._sekmeler.blockSignals(False)

    @staticmethod
    def _grup_cubugu(grup):
        for oge in grup:
            if oge is not None and gecerli(oge[1]):
                ebeveyn = oge[1].parentWidget()
                if isinstance(ebeveyn, QtWidgets.QToolBar):
                    return ebeveyn.objectName()
        return None

    def _sekme_degisti(self, i):
        self._sayfalar.setCurrentIndex(i)
        self._uyarla()
        kimlik = self._secili_kimlik()
        if kimlik is not None and self._tezgah is not None:
            self._son_sekme[self._tezgah] = kimlik

    # --- kapatma ----------------------------------------------------------------------

    def kapat(self):
        """Şeridi kaldırır, FreeCAD araç çubuklarını eski haline getirir."""
        try:
            self.mw.workbenchActivated.disconnect(self._tezgah_degisti)
        except (RuntimeError, TypeError):
            pass
        for cubuk in self._izlenen.values():
            if not gecerli(cubuk):
                continue
            cubuk.removeEventFilter(self)
            try:
                cubuk.toggleViewAction().changed.disconnect(self.planla)
            except (RuntimeError, TypeError):
                pass
        self._izlenen.clear()
        for cubuk in self._fc_cubuklari():
            politika = cubuk.toggleViewAction().property("DefaultVisibility")
            if kullanilabilir_mi(cubuk) and politika in (None, 0):
                cubuk.show()
        self.mw.removeToolBar(self.kap)
        self.kap.deleteLater()
