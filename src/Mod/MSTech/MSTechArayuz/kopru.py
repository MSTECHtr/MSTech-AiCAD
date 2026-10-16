# SPDX-License-Identifier: LGPL-2.1-or-later
"""MCP sunucusunun araç çağrılarını programın ana iş parçacığında çalıştıran yerel köprü.

Yalnızca 127.0.0.1'i dinler ve her istekte rastgele bir jeton ister.
"""

import json
import secrets

from PySide import QtCore, QtNetwork

from . import claude_araclari


class Kopru(QtCore.QObject):
    def __init__(self, onay=None, ebeveyn=None):
        super().__init__(ebeveyn)
        self._onay = onay  # freecad_python için isteğe bağlı kullanıcı onayı
        self._tamponlar = {}
        self.jeton = secrets.token_hex(24)
        self._sunucu = QtNetwork.QTcpServer(self)
        if not self._sunucu.listen(QtNetwork.QHostAddress.LocalHost, 0):
            raise RuntimeError("Yerel köprü başlatılamadı: " + self._sunucu.errorString())
        self.port = self._sunucu.serverPort()
        self._sunucu.newConnection.connect(self._yeni_baglanti)

    def _yeni_baglanti(self):
        while self._sunucu.hasPendingConnections():
            soket = self._sunucu.nextPendingConnection()
            self._tamponlar[id(soket)] = b""
            soket.readyRead.connect(lambda s=soket: self._oku(s))
            soket.disconnected.connect(lambda s=soket: self._tamponlar.pop(id(s), None))

    def _oku(self, soket):
        tampon = self._tamponlar.get(id(soket), b"") + bytes(soket.readAll())
        self._tamponlar[id(soket)] = tampon
        if not tampon.endswith(b"\n"):
            return
        try:
            istek = json.loads(tampon)
        except ValueError:
            soket.abort()
            return
        if not secrets.compare_digest(str(istek.get("jeton", "")), self.jeton):
            soket.abort()
            return
        arac, girdi = istek.get("arac", ""), istek.get("girdi") or {}
        if arac == "freecad_python" and self._onay is not None and not self._onay(girdi):
            icerik, hatali = "Kullanıcı bu kodu çalıştırmayı reddetti.", True
        else:
            icerik, hatali = claude_araclari.calistir(arac, girdi)
        soket.write((json.dumps({"icerik": icerik, "hatali": hatali}) + "\n").encode())
        soket.flush()
        soket.disconnectFromHost()
