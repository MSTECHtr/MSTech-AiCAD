# SPDX-License-Identifier: LGPL-2.1-or-later
"""MSTech Ai-CAD MCP sunucusu (Claude Code başlatır, stdio üzerinden konuşur).

Araç çağrılarını açık MSTech Ai-CAD'deki köprüye (127.0.0.1, jetonlu) iletir; araçlar
programın içinde çalışır. FreeCAD'e bağımlı değildir, ayrı bir Python sürecinde çalışır.
"""

import base64
import json
import os
import socket

from mcp.server.fastmcp import FastMCP, Image

PORT = int(os.environ["MSTECH_KOPRU_PORT"])
JETON = os.environ["MSTECH_KOPRU_JETON"]

sunucu = FastMCP("mstech")


def _cagir(arac, girdi):
    with socket.create_connection(("127.0.0.1", PORT), timeout=900) as baglanti:
        baglanti.sendall((json.dumps({"jeton": JETON, "arac": arac, "girdi": girdi}) + "\n").encode())
        veri = b""
        while not veri.endswith(b"\n"):
            parca = baglanti.recv(1 << 16)
            if not parca:
                break
            veri += parca
    yanit = json.loads(veri)
    return yanit["icerik"], yanit["hatali"]


@sunucu.tool()
def freecad_python(aciklama: str, kod: str) -> str:
    """MSTech Ai-CAD (FreeCAD) içinde Python kodu çalıştırır: parça çizmek, eskiz oluşturmak, kesmek,
    ölçü değiştirmek, montaj kurmak için. FreeCAD, FreeCADGui, Part, Sketcher kullanılabilir;
    değişkenler çağrılar arasında korunur. Her çağrı tek bir geri alma (Ctrl+Z) adımıdır; hata olursa
    o çağrının değişiklikleri geri alınır. print() çıktısı, hata ve belgenin özeti döner. Birimler mm.
    aciklama: kullanıcıya gösterilecek kısa açıklama."""
    icerik, hatali = _cagir("freecad_python", {"aciklama": aciklama, "kod": kod})
    return icerik if not hatali else "[HATA]\n" + icerik


@sunucu.tool()
def belge_ozeti() -> str:
    """Etkin belgedeki nesneleri listeler: ad, etiket, tür, sınır kutusu, hacim; eskizler için
    kısıtlama durumu. Parçayı incelemek ve değişikliği doğrulamak için kullan."""
    return _cagir("belge_ozeti", {})[0]


@sunucu.tool()
def goruntu_al(yon: str = "izometrik", sigdir: bool = True):
    """3B görünümün ekran görüntüsünü alır (parçaya bakmak, sonucu önizlemek için).
    yon: mevcut, izometrik, on, arka, ust, alt, sag, sol. sigdir: modeli görünüme sığdır."""
    icerik, hatali = _cagir("goruntu_al", {"yon": yon, "sigdir": sigdir})
    if hatali:
        return icerik
    return Image(data=base64.standard_b64decode(icerik[0]["source"]["data"]), format="jpeg")


if __name__ == "__main__":
    sunucu.run()
