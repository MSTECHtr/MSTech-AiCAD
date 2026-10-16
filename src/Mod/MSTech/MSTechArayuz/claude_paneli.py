# SPDX-License-Identifier: LGPL-2.1-or-later
"""Claude sohbet paneli: Claude parçayı görür, FreeCAD'de kendisi çizer ve düzenler.

API çağrıları arka plan iş parçacığında yapılır (arayüz donmaz); araçlar FreeCAD'in
ana iş parçacığında çalışır.
"""

import glob
import html
import json
import os
import shutil
import sys
import threading

import FreeCAD as App
from PySide import QtCore, QtGui, QtWidgets

from . import PARAM_YOLU, claude_araclari

MODEL = "claude-opus-5-5"
EN_FAZLA_TUR = 30  # bir mesajda en fazla araç turu

SISTEM = """Sen MSTech Ai-CAD içindeki tasarım asistanısın (FreeCAD tabanlı CAD). Kullanıcının isteğini \
araçlarınla doğrudan programda, kullanıcı ekranda izlerken gerçekleştirirsin.

Konuşma:
- Kullanıcının dilinde (genellikle Türkçe), samimi ve kısa konuş.
- Birden fazla parçadan oluşan ya da ölçüleri belirsiz bir proje istendiğinde, başlamadan önce 2-4 kısa
  ve yerinde soru sor (ana ölçüler, kullanım amacı, malzeme/kalınlık, bağlantı şekli gibi) ve cevabı bekle.
  Basit ve ölçüleri net isteklerde soru sormadan başla. Kullanıcı "sen karar ver" derse makul değerler seç.
- Çalışırken her araç çağrısından önce ne yapacağını tek cümleyle söyle ("Şimdi taban plakasını
  çiziyorum."), sonucu kontrol ettikten sonra ne gördüğünü kısaca söyle ("Plaka 200x100 mm oldu, şimdi
  delikleri açıyorum."). Kullanıcı yapılışı adım adım izliyor; anlatımın onun için.
- Bitince kısa bir özet ver ve bir sonraki adım için öneri ya da soru sun.

Modelleme:
- freecad_python ile FreeCAD Python API'sini kullan. Birimler mm. Her çağrıda TEK bir özellik ekle
  (bir eskiz, bir pad, bir delik...); hepsini tek seferde yapma ki kullanıcı adımları görsün.
- Parametrik parçalar için PartDesign: Body -> Sketch (kısıtlamalı) -> Pad / Pocket / Revolution / Fillet.
  Profiller (kare, boru, sigma, C, U, I) için kapalı eskiz çizip uzat. Hızlı katılar için Part da olur.
- Makine/montajda her parçayı ayrı gövde yap, anlamlı Label ver, doğru konumla.
- Belge yoksa App.newDocument ile oluştur. Var olan nesneleri silmeden önce emin ol.
- Adımları belge_ozeti ile doğrula; önemli aşamalarda goruntu_al ile bak. Hata alırsan düzelt.
- Dosya sistemine, ağa veya FreeCAD dışındaki şeylere kullanıcı açıkça istemedikçe dokunma."""


def _param():
    return App.ParamGet(PARAM_YOLU)


def _api_anahtari():
    return _param().GetString("ClaudeAPIAnahtari", "") or os.environ.get("ANTHROPIC_API_KEY", "")


def _ant_yolu():
    """Anthropic CLI (ant): tarayıcıyla hesap girişi için."""
    yerel = os.path.expanduser("~/.local/bin/ant")
    return yerel if os.path.exists(yerel) else shutil.which("ant")


def _claude_yolu():
    """Kurulu Claude Code (aboneliğinle giriş yapılmış resmî CLI)."""
    adaylar = [shutil.which("claude"), os.path.expanduser("~/.claude/local/claude")]
    adaylar += glob.glob(os.path.expanduser("~/.local/share/claude/versions/*"))
    adaylar += glob.glob(os.path.expanduser(
        "~/.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude"))
    adaylar = [a for a in adaylar if a and os.path.isfile(a) and os.access(a, os.X_OK)]
    return max(adaylar, key=os.path.getmtime) if adaylar else None


def _motor():
    """API anahtarı girildiyse API, yoksa Claude Code (abonelik; kurulu değilse kurulum önerilir)."""
    return "api" if _api_anahtari() else "claude_code"


CC_ARACLARI = "mcp__mstech__freecad_python,mcp__mstech__belge_ozeti,mcp__mstech__goruntu_al"


def _giris_yapildi_mi():
    """ant auth login ile kaydedilmiş bir hesap profili var mı."""
    kok = os.environ.get("ANTHROPIC_CONFIG_DIR", os.path.expanduser("~/.config/anthropic"))
    kimlik = os.path.join(kok, "credentials")
    return os.path.isdir(kimlik) and any(f.endswith(".json") for f in os.listdir(kimlik))


class _Isci(QtCore.QObject):
    """API isteğini arka planda yapar; sonucu ana iş parçacığına sinyalle iletir."""

    bitti = QtCore.Signal(object)
    hata = QtCore.Signal(str, bool)  # mesaj, anahtar sorunu mu

    def baslat(self, mesajlar):
        threading.Thread(target=self._calis, args=(list(mesajlar),), daemon=True).start()

    def _calis(self, mesajlar):
        try:
            import anthropic
        except ImportError:
            self.hata.emit("Python 'anthropic' paketi bulunamadı.", False)
            return
        try:
            anahtar = _api_anahtari()
            if not anahtar:
                # boş bir ANTHROPIC_API_KEY bile hesap profilinin önüne geçer
                os.environ.pop("ANTHROPIC_API_KEY", None)
            istemci = anthropic.Anthropic(api_key=anahtar) if anahtar else anthropic.Anthropic()
            yanit = istemci.beta.messages.create(
                model=_param().GetString("ClaudeModel", MODEL),
                max_tokens=16000,
                system=SISTEM,
                tools=claude_araclari.ARACLAR,
                messages=mesajlar,
                output_config={"effort": _param().GetString("ClaudeEfor", "medium")},
                cache_control={"type": "ephemeral"},
                # güvenlik sınıflandırıcısı reddederse sunucu uygun modele yönlendirir
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            self.bitti.emit(yanit)
        except anthropic.AuthenticationError:
            self.hata.emit("Giriş geçersiz ya da süresi dolmuş. 'Giriş yap' ile tekrar giriş yapın.", True)
        except anthropic.RateLimitError:
            self.hata.emit("Hız sınırına takıldı, biraz bekleyip tekrar deneyin.", False)
        except anthropic.APIStatusError as e:
            self.hata.emit(f"API hatası ({e.status_code}): {e.message}", False)
        except anthropic.APIConnectionError:
            self.hata.emit("Bağlantı kurulamadı. İnternet bağlantısını kontrol edin.", False)
        except Exception as e:  # ör. hiç kimlik bilgisi yok
            anahtar_yok = "auth" in str(e).lower() or "api_key" in str(e).lower()
            self.hata.emit(f"{type(e).__name__}: {e}", anahtar_yok)


class _Giris(QtWidgets.QPlainTextEdit):
    gonder = QtCore.Signal()

    def keyPressEvent(self, olay):
        if olay.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter) and not (
            olay.modifiers() & QtCore.Qt.ShiftModifier
        ):
            self.gonder.emit()
            return
        super().keyPressEvent(olay)


class ClaudePaneli(QtWidgets.QWidget):
    def __init__(self, ebeveyn=None):
        super().__init__(ebeveyn)
        self.setObjectName("MSTechClaudePaneli")
        self._mesajlar = []
        self._calisiyor = False
        self._durdur = False
        self._tur = 0
        self._isci = _Isci()
        self._isci.bitti.connect(self._yanit_geldi)
        self._isci.hata.connect(self._hata_geldi)

        self._sohbet = QtWidgets.QTextBrowser()
        self._sohbet.setOpenExternalLinks(True)
        self._giris = _Giris()
        self._giris.setPlaceholderText(
            "Claude'a ne yapacağını yaz… ör. '40x40x2 mm kare profil, 500 mm boyunda çiz'"
        )
        self._giris.setFixedHeight(70)
        self._giris.gonder.connect(self._gonder)

        self._gonder_dugmesi = QtWidgets.QPushButton("Gönder")
        self._gonder_dugmesi.setDefault(True)
        self._gonder_dugmesi.clicked.connect(self._gonder)
        self._durdur_dugmesi = QtWidgets.QPushButton("Durdur")
        self._durdur_dugmesi.setEnabled(False)
        self._durdur_dugmesi.clicked.connect(self._durdur_istendi)
        yeni = QtWidgets.QToolButton()
        yeni.setText("Yeni sohbet")
        yeni.clicked.connect(self.yeni_sohbet)
        self._giris_dugmesi = QtWidgets.QPushButton("Giriş yap")
        self._giris_dugmesi.setToolTip("Tarayıcıda Claude (Anthropic) hesabınızla giriş yapın")
        self._giris_dugmesi.clicked.connect(self.giris_yap)
        anahtar = QtWidgets.QToolButton()
        anahtar.setText("API anahtarı")
        anahtar.setToolTip("Hesap girişi yerine API anahtarı kullanmak için")
        anahtar.clicked.connect(self.anahtar_sor)
        self._giris_durumu = QtWidgets.QLabel()
        self._model_secici = QtWidgets.QComboBox()
        self._model_secici.setToolTip("Claude modeli (Sonnet ve Haiku daha az kullanım limiti harcar)")
        for etiket, deger in (("Varsayılan model", ""), ("Opus", "opus"), ("Sonnet", "sonnet"), ("Haiku", "haiku")):
            self._model_secici.addItem(etiket, deger)
        secili = self._model_secici.findData(_param().GetString("ClaudeCodeModel", ""))
        self._model_secici.setCurrentIndex(max(0, secili))
        self._model_secici.currentIndexChanged.connect(
            lambda _: _param().SetString("ClaudeCodeModel", self._model_secici.currentData()))
        self._giris_sureci = None
        self._cc_surec = None
        self._cc_oturum = None
        self._cc_tampon = b""
        self._kopru = None
        self._bilinen = set()
        self._onay = QtWidgets.QCheckBox("Kodu çalıştırmadan önce sor")
        self._onay.setChecked(_param().GetBool("ClaudeKodOnayi", False))
        self._onay.toggled.connect(lambda v: _param().SetBool("ClaudeKodOnayi", v))
        self._durum = QtWidgets.QLabel()

        ust = QtWidgets.QHBoxLayout()
        ust.addWidget(yeni)
        ust.addStretch(1)
        ust.addWidget(self._giris_durumu)
        ust.addWidget(self._model_secici)
        ust.addWidget(self._giris_dugmesi)
        ust.addWidget(anahtar)
        alt = QtWidgets.QHBoxLayout()
        alt.addWidget(self._onay)
        alt.addStretch(1)
        alt.addWidget(self._durdur_dugmesi)
        alt.addWidget(self._gonder_dugmesi)
        duzen = QtWidgets.QVBoxLayout(self)
        duzen.setContentsMargins(4, 4, 4, 4)
        duzen.addLayout(ust)
        duzen.addWidget(self._sohbet, 1)
        duzen.addWidget(self._durum)
        duzen.addWidget(self._giris)
        duzen.addLayout(alt)
        self._karsila()
        self._giris_durumunu_goster()

    # --- görünüm ---------------------------------------------------------------------

    def _karsila(self):
        self._sohbet.clear()
        self._ekle_markdown(
            "**Claude** burada. Ne çizmemi istersin? Örnekler:\n\n"
            "- *100x60x5 mm, köşeleri 8 mm yuvarlatılmış plaka çiz*\n"
            "- *200 mm boyunda sigma profil çiz*\n"
            "- *Bu parçanın ortasından 10 mm delik aç ve kesitini göster*\n"
            "- *Basit bir redüktör kutusu tasarla*"
        )

    def _yeni_blok(self):
        imlec = self._sohbet.textCursor()
        imlec.movePosition(QtGui.QTextCursor.End)
        if not self._sohbet.document().isEmpty():
            imlec.insertBlock(QtGui.QTextBlockFormat(), QtGui.QTextCharFormat())
        return imlec

    def _ekle_html(self, metin):
        self._yeni_blok().insertHtml(metin)
        self._sohbet.ensureCursorVisible()

    def _ekle_markdown(self, metin):
        self._yeni_blok().insertMarkdown(metin + "\n")
        self._sohbet.ensureCursorVisible()

    def _kullanici_mesaji(self, metin):
        self._ekle_html(
            "<table width='100%' cellpadding='6' style='margin-top:8px'><tr>"
            "<td style='background-color:#E3EEFB'><b style='color:#0F4C9C'>Sen</b><br>"
            + html.escape(metin).replace("\n", "<br>") + "</td></tr></table>")

    def _sonucu_goster(self, metin):
        """Araç sonucundan yeni eklenen parçaları ve hataları gösterir."""
        if not isinstance(metin, str):
            return
        if "HATA" in metin[:200]:
            ilk = next((s for s in metin.splitlines() if "Error" in s or "HATA" in s), "Hata")
            self._ekle_html(f"<span style='color:#B85C00'>⚠ {html.escape(ilk[:160])}</span>")
        for satir in metin.splitlines():
            if not satir.startswith("- "):
                continue
            parcalar = satir[2:].split(" ")
            ad = parcalar[0]
            if ad in self._bilinen:
                continue
            self._bilinen.add(ad)
            etiket = satir.split("'")[1] if satir.count("'") >= 2 else ad
            tur = satir[satir.find("[") + 1:satir.find("]")] if "[" in satir else ""
            ayrinti = " ".join(p for p in parcalar if p.startswith(("kutu=", "hacim=")) or p == "mm3")
            self._ekle_html(
                f"<span style='color:#1B7F2A'>➕ <b>{html.escape(etiket)}</b></span> "
                f"<span style='color:#7A8089'>{html.escape(tur.split('::')[-1])} {html.escape(ayrinti)}</span>")

    def _calisma_durumu(self, calisiyor, durum=""):
        self._calisiyor = calisiyor
        self._gonder_dugmesi.setEnabled(not calisiyor)
        self._durdur_dugmesi.setEnabled(calisiyor)
        self._durum.setText(durum)

    # --- akış ------------------------------------------------------------------------

    def yeni_sohbet(self):
        if self._calisiyor:
            return
        self._mesajlar = []
        self._cc_oturum = None
        self._bilinen = set()
        self._karsila()

    def anahtar_sor(self):
        mevcut = _param().GetString("ClaudeAPIAnahtari", "")
        anahtar, tamam = QtWidgets.QInputDialog.getText(
            self,
            "Claude API anahtarı",
            "Anthropic API anahtarınız (console.anthropic.com):\n"
            "Boş bırakılırsa ANTHROPIC_API_KEY ortam değişkeni kullanılır.",
            QtWidgets.QLineEdit.Password,
            mevcut,
        )
        if tamam:
            _param().SetString("ClaudeAPIAnahtari", anahtar.strip())
            self._giris_durumunu_goster()

    def _giris_durumunu_goster(self):
        self._model_secici.setVisible(_motor() == "claude_code")
        if _motor() == "claude_code":
            self._cc_durumu_denetle()
            return
        self._giris_dugmesi.setVisible(True)
        if _api_anahtari():
            self._giris_durumu.setText("API anahtarı ile")
        elif _giris_yapildi_mi():
            self._giris_durumu.setText("✓ Giriş yapıldı")
            self._giris_dugmesi.setText("Hesap değiştir")
        else:
            self._giris_durumu.setText("Giriş yapılmadı")
            self._giris_dugmesi.setText("Giriş yap")

    # --- Claude Code: kurulum ve giriş ---------------------------------------------------

    def _cc_durumu_denetle(self):
        yol = _claude_yolu()
        self._cc_giris = None
        if not yol:
            self._giris_durumu.setText("Claude Code kurulu değil")
            self._giris_dugmesi.setText("Claude Code'u kur")
            self._giris_dugmesi.setVisible(True)
            return
        self._giris_durumu.setText("Claude hesabı denetleniyor…")
        self._giris_dugmesi.setVisible(False)
        surec = QtCore.QProcess(self)
        ortam = QtCore.QProcessEnvironment.systemEnvironment()
        ortam.remove("ANTHROPIC_API_KEY")
        surec.setProcessEnvironment(ortam)
        surec.finished.connect(lambda *_: self._cc_durum_geldi(surec))
        surec.start(yol, ["auth", "status", "--json"])

    def _cc_durum_geldi(self, surec):
        try:
            durum = json.loads(bytes(surec.readAllStandardOutput()).decode("utf-8", "replace"))
        except ValueError:
            durum = {}
        self._cc_giris = bool(durum.get("loggedIn"))
        if self._cc_giris:
            plan = durum.get("subscriptionType") or durum.get("authMethod") or ""
            self._giris_durumu.setText(f"✓ {durum.get('email', 'Claude')} ({plan.capitalize()})")
            self._giris_dugmesi.setVisible(False)
        else:
            self._giris_durumu.setText("Claude'a giriş yapılmadı")
            self._giris_dugmesi.setText("Claude ile giriş yap")
            self._giris_dugmesi.setVisible(True)
            self._ekle_html("<p>Claude'u kullanmak için sağ üstteki <b>Claude ile giriş yap</b> "
                            "düğmesine bas; tarayıcıda Claude hesabınla (Pro/Max) giriş yap.</p>")

    def _cc_giris_baslat(self):
        yol = _claude_yolu()
        if yol:
            self._ekle_html("<p style='color:#5B6472'>Tarayıcıda Claude giriş sayfası açılıyor… "
                            "Giriş yapıp izin ver, sonra buraya dön.</p>")
            program, argumanlar = yol, ["auth", "login", "--claudeai"]
        else:
            self._ekle_html("<p style='color:#5B6472'>Claude Code kuruluyor (resmî kurulum betiği)…</p>")
            program, argumanlar = "bash", ["-c", "curl -fsSL https://claude.ai/install.sh | bash"]
        surec = QtCore.QProcess(self)
        ortam = QtCore.QProcessEnvironment.systemEnvironment()
        ortam.remove("ANTHROPIC_API_KEY")
        surec.setProcessEnvironment(ortam)
        surec.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        surec.finished.connect(lambda kod, _d: self._cc_islem_bitti(surec, kod))
        self._giris_sureci = surec
        self._giris_dugmesi.setEnabled(False)
        surec.start(program, argumanlar)

    def _cc_islem_bitti(self, surec, kod):
        self._giris_sureci = None
        self._giris_dugmesi.setEnabled(True)
        if kod != 0:
            cikti = bytes(surec.readAll()).decode("utf-8", "replace").strip()
            self._ekle_html(f"<p style='color:#C62828'>İşlem tamamlanamadı: {html.escape(cikti[-300:])}</p>")
        self._cc_durumu_denetle()

    def giris_yap(self):
        if _motor() == "claude_code":
            self._cc_giris_baslat()
            return
        ant = _ant_yolu()
        if not ant:
            self._ekle_html(
                "<p style='color:#C62828'>Giriş aracı (ant) bulunamadı. "
                "github.com/anthropics/anthropic-cli adresinden kurulabilir.</p>"
            )
            return
        if self._giris_sureci is not None:
            return
        self._ekle_html("<p style='color:#5B6472'>Tarayıcıda giriş sayfası açılıyor… "
                        "Hesabınızla giriş yapıp izin verin, sonra buraya dönün.</p>")
        surec = QtCore.QProcess(self)
        ortam = QtCore.QProcessEnvironment.systemEnvironment()
        ortam.remove("ANTHROPIC_API_KEY")
        surec.setProcessEnvironment(ortam)
        surec.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        surec.finished.connect(self._giris_bitti)
        self._giris_sureci = surec
        surec.start(ant, ["auth", "login"])

    def _giris_bitti(self, kod, _durum):
        cikti = bytes(self._giris_sureci.readAll()).decode("utf-8", "replace").strip()
        self._giris_sureci = None
        if kod == 0:
            self._ekle_html("<p style='color:#1B7F2A'><b>Giriş başarılı.</b> Artık yazabilirsiniz.</p>")
        else:
            self._ekle_html(f"<p style='color:#C62828'>Giriş tamamlanamadı: {html.escape(cikti[-300:])}</p>")
        self._giris_durumunu_goster()

    def _gonder(self):
        metin = self._giris.toPlainText().strip()
        if not metin or self._calisiyor:
            return
        if _motor() == "claude_code":
            if not _claude_yolu() or getattr(self, "_cc_giris", None) is False:
                self._ekle_html("<p style='color:#B85C00'>Önce sağ üstteki düğmeyle Claude Code'u "
                                "kur / Claude hesabınla giriş yap.</p>")
                return
            self._giris.clear()
            self._kullanici_mesaji(metin)
            self._cc_gonder(metin)
            return
        if not _api_anahtari() and not _giris_yapildi_mi():
            self._ekle_html("<p style='color:#B85C00'>Önce sağ üstteki <b>Giriş yap</b> "
                            "ile Claude hesabınıza girin.</p>")
            return
        self._giris.clear()
        self._kullanici_mesaji(metin)
        blok = {"type": "text", "text": metin}
        if self._mesajlar and self._mesajlar[-1]["role"] == "user":
            # yarıda durdurulmuş bir turun araç sonuçlarına ekle
            self._mesajlar[-1]["content"].append(blok)
        else:
            self._mesajlar.append({"role": "user", "content": [blok]})
        self._durdur = False
        self._tur = 0
        self._istek()

    def _istek(self):
        self._calisma_durumu(True, "Claude düşünüyor…")
        self._isci.baslat(self._mesajlar)

    def _durdur_istendi(self):
        self._durdur = True
        self._durum.setText("Durduruluyor…")
        if self._cc_surec is not None:
            self._cc_surec.terminate()

    # --- Claude Code motoru (abonelik) -------------------------------------------------

    def _cc_gonder(self, metin):
        from . import kopru

        if self._kopru is None:
            try:
                self._kopru = kopru.Kopru(onay=self._kod_onayi_gerekirse, ebeveyn=self)
            except RuntimeError as e:
                self._ekle_html(f"<p style='color:#C62828'>{html.escape(str(e))}</p>")
                return
        klasor = os.path.join(App.getUserAppDataDir(), "ClaudeCode")
        os.makedirs(klasor, exist_ok=True)
        python = os.path.join(sys.prefix, "bin", "python3")
        ayar = {"mcpServers": {"mstech": {
            "command": python if os.path.exists(python) else (shutil.which("python3") or "python3"),
            "args": [os.path.join(os.path.dirname(__file__), "mstech_mcp_sunucu.py")],
            "env": {"MSTECH_KOPRU_PORT": str(self._kopru.port), "MSTECH_KOPRU_JETON": self._kopru.jeton},
        }}}
        ayar_dosyasi = os.path.join(klasor, "mcp.json")
        with open(os.open(ayar_dosyasi, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
            json.dump(ayar, f)

        argumanlar = ["-p", "--output-format", "stream-json", "--verbose",
                      "--tools", "", "--mcp-config", ayar_dosyasi, "--strict-mcp-config",
                      "--allowedTools", CC_ARACLARI, "--append-system-prompt", SISTEM]
        if self._cc_oturum:
            argumanlar += ["--resume", self._cc_oturum]
        model = _param().GetString("ClaudeCodeModel", "")
        if model:
            argumanlar += ["--model", model]

        surec = QtCore.QProcess(self)
        ortam = QtCore.QProcessEnvironment.systemEnvironment()
        ortam.remove("ANTHROPIC_API_KEY")  # aboneliğin kullanılsın, ücretli API değil
        surec.setProcessEnvironment(ortam)
        surec.setWorkingDirectory(klasor)
        surec.readyReadStandardOutput.connect(self._cc_oku)
        surec.finished.connect(self._cc_bitti)
        self._cc_surec = surec
        self._cc_tampon = b""
        self._cc_sonuc_geldi = False
        self._durdur = False
        self._calisma_durumu(True, "💭 Claude düşünüyor…")
        surec.start(_claude_yolu(), argumanlar)
        surec.write(metin.encode("utf-8"))
        surec.closeWriteChannel()

    def _cc_oku(self):
        self._cc_tampon += bytes(self._cc_surec.readAllStandardOutput())
        *satirlar, self._cc_tampon = self._cc_tampon.split(b"\n")
        for satir in satirlar:
            try:
                olay = json.loads(satir)
            except ValueError:
                continue
            tur = olay.get("type")
            if olay.get("session_id"):
                self._cc_oturum = olay["session_id"]
            if tur == "assistant":
                for blok in olay.get("message", {}).get("content", []):
                    if blok.get("type") == "text" and blok.get("text", "").strip():
                        self._ekle_markdown("**Claude:** " + blok["text"])
                        self._durum.setText("💬 " + blok["text"].strip().splitlines()[0][:90])
                    elif blok.get("type") == "tool_use":
                        girdi = blok.get("input") or {}
                        aciklama = girdi.get("aciklama") or {
                            "mcp__mstech__belge_ozeti": "Parça inceleniyor",
                            "mcp__mstech__goruntu_al": "Görüntü alınıyor",
                        }.get(blok.get("name"), blok.get("name"))
                        self._ekle_html(f"<p style='color:#5B6472'>🔧 {html.escape(aciklama)}</p>")
                        self._durum.setText("🔧 " + aciklama[:90])
            elif tur == "user":
                for blok in olay.get("message", {}).get("content", []) or []:
                    if isinstance(blok, dict) and blok.get("type") == "tool_result":
                        icerik = blok.get("content")
                        if isinstance(icerik, list):
                            icerik = "\n".join(c.get("text", "") for c in icerik if isinstance(c, dict))
                        self._sonucu_goster(icerik)
            elif tur == "result":
                self._cc_sonuc_geldi = True
                if olay.get("is_error"):
                    hata = olay.get("result") or olay.get("subtype", "hata")
                    self._ekle_html(f"<p style='color:#C62828'><b>Hata:</b> {html.escape(str(hata))}</p>")

    def _cc_bitti(self, kod, _durum):
        hata_ciktisi = bytes(self._cc_surec.readAllStandardError()).decode("utf-8", "replace").strip()
        self._cc_surec = None
        if self._durdur:
            self._ekle_html("<p style='color:#B85C00'>Durduruldu.</p>")
        elif kod != 0 and not self._cc_sonuc_geldi:
            self._ekle_html(f"<p style='color:#C62828'><b>Claude Code hatası:</b> "
                            f"{html.escape(hata_ciktisi[-500:] or str(kod))}</p>")
        self._calisma_durumu(False)

    def _kod_onayi_gerekirse(self, girdi):
        return not self._onay.isChecked() or self._kod_onayi(girdi)

    def _hata_geldi(self, mesaj, anahtar_sorunu):
        self._calisma_durumu(False)
        self._ekle_html(f"<p style='color:#C62828'><b>Hata:</b> {html.escape(mesaj)}</p>")
        if anahtar_sorunu and not _api_anahtari():
            self._ekle_html("<p>Sağ üstteki <b>Giriş yap</b> düğmesiyle Claude hesabınıza girin.</p>")

    def _yanit_geldi(self, yanit):
        # yanıt olduğu gibi geçmişe eklenir (düşünce blokları dahil, değiştirilmeden)
        self._mesajlar.append({"role": "assistant", "content": yanit.content})
        for blok in yanit.content:
            if blok.type == "text" and blok.text.strip():
                self._ekle_markdown("**Claude:** " + blok.text)

        if yanit.stop_reason == "refusal":
            self._ekle_html("<p style='color:#C62828'>Claude bu isteği yanıtlayamadı.</p>")
            self._calisma_durumu(False)
            return
        if yanit.stop_reason == "max_tokens":
            self._ekle_html("<p style='color:#B85C00'>Yanıt uzunluk sınırında kesildi.</p>")
        if yanit.stop_reason == "pause_turn":
            self._istek()
            return
        araclar = [b for b in yanit.content if b.type == "tool_use"]
        if yanit.stop_reason != "tool_use" or not araclar:
            self._calisma_durumu(False)
            return

        sonuclar = []
        for blok in araclar:
            girdi = blok.input if isinstance(blok.input, dict) else {}
            if self._durdur:
                sonuclar.append(self._sonuc(blok.id, "Kullanıcı durdurdu.", True))
                continue
            aciklama = girdi.get("aciklama") or {"belge_ozeti": "Parça inceleniyor",
                                                 "goruntu_al": "Görüntü alınıyor"}.get(blok.name, blok.name)
            self._ekle_html(f"<p style='color:#5B6472'>🔧 {html.escape(aciklama)}</p>")
            if blok.name == "freecad_python" and self._onay.isChecked() and not self._kod_onayi(girdi):
                sonuclar.append(self._sonuc(blok.id, "Kullanıcı bu kodu çalıştırmayı reddetti.", True))
                continue
            icerik, hatali = claude_araclari.calistir(blok.name, girdi)
            if hatali:
                self._ekle_html("<p style='color:#B85C00'>⚠ Araç hata verdi, Claude düzeltmeyi deneyecek.</p>")
            self._sonucu_goster(icerik)
            sonuclar.append(self._sonuc(blok.id, icerik, hatali))
        self._mesajlar.append({"role": "user", "content": sonuclar})

        self._tur += 1
        if self._durdur or self._tur >= EN_FAZLA_TUR:
            if not self._durdur:
                self._ekle_html("<p style='color:#B85C00'>Adım sınırına ulaşıldı; devam etmek için yaz.</p>")
            self._calisma_durumu(False)
            return
        self._istek()

    @staticmethod
    def _sonuc(kimlik, icerik, hatali):
        sonuc = {"type": "tool_result", "tool_use_id": kimlik, "content": icerik}
        if hatali:
            sonuc["is_error"] = True
        return sonuc

    def _kod_onayi(self, girdi):
        kutu = QtWidgets.QMessageBox(self)
        kutu.setWindowTitle("Claude kodu çalıştırmak istiyor")
        kutu.setText(girdi.get("aciklama", ""))
        kutu.setDetailedText(girdi.get("kod", ""))
        kutu.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        kutu.button(QtWidgets.QMessageBox.Yes).setText("Çalıştır")
        kutu.button(QtWidgets.QMessageBox.No).setText("Reddet")
        return kutu.exec() == QtWidgets.QMessageBox.Yes


def panel_olustur(mw):
    """Claude panelini sağ kenara yerleştirir; panelin QDockWidget'ını döndürür."""
    dock = QtWidgets.QDockWidget("Claude", mw)
    dock.setObjectName("MSTechClaude")
    dock.setWidget(ClaudePaneli(dock))
    mw.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
    dock.setMinimumWidth(320)
    return dock
