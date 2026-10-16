# SPDX-License-Identifier: LGPL-2.1-or-later
"""Şerit ve görünüm çubuğu stilleri; açık/koyu temaya göre renk seçer."""

import FreeCAD as App

_ACIK = {
    "zemin": "#FBFCFD",
    "kenar": "#D5DAE1",
    "yazi": "#1E2530",
    "soluk": "#5B6472",
    "pasif": "#A0A8B4",
    "vurgu": "#1F7AE0",
    "vurgu_yazi": "#0F4C9C",
    "uzerinde": "#E6F0FC",
    "uzerinde_kenar": "#B9D3F4",
    "basili": "#D3E5FA",
    "basili_kenar": "#8DB8EE",
    "sekme_secili": "#FFFFFF",
    "yuzen_zemin": "rgba(255, 255, 255, 225)",
    "yuzen_kenar": "rgba(30, 37, 48, 40)",
    "ok": "darkgray",
    "ok_vurgu": "blue",
}

_KOYU = {
    "zemin": "#2B2F36",
    "kenar": "#3C424B",
    "yazi": "#E3E7ED",
    "soluk": "#AAB2BE",
    "pasif": "#6C7480",
    "vurgu": "#4C9AF0",
    "vurgu_yazi": "#8EC1FA",
    "uzerinde": "#36404D",
    "uzerinde_kenar": "#4A6A92",
    "basili": "#2F4A6B",
    "basili_kenar": "#4C9AF0",
    "sekme_secili": "#23272D",
    "yuzen_zemin": "rgba(43, 47, 54, 225)",
    "yuzen_kenar": "rgba(255, 255, 255, 40)",
    "ok": "lightgray",
    "ok_vurgu": "white",
}


def renkler():
    tema = App.ParamGet("User parameter:BaseApp/Preferences/MainWindow").GetString("Theme", "")
    return _KOYU if "dark" in tema.lower() else _ACIK


def serit():
    r = renkler()
    return f"""
#MSTechSerit {{
    background: {r['zemin']};
    border-bottom: 1px solid {r['kenar']};
}}
#MSTechSerit QScrollArea, #MSTechSerit QStackedWidget, #MSTechSerit #MSTechSeritSayfa,
#MSTechSerit QWidget#qt_scrollarea_viewport {{
    background: transparent;
    border: none;
}}
#MSTechSerit QToolButton {{
    color: {r['yazi']};
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 2px 4px;
    margin: 0px;
}}
#MSTechSerit QToolButton:hover {{
    background: {r['uzerinde']};
    border-color: {r['uzerinde_kenar']};
}}
#MSTechSerit QToolButton:pressed, #MSTechSerit QToolButton:checked {{
    background: {r['basili']};
    border-color: {r['basili_kenar']};
}}
#MSTechSerit QToolButton:disabled {{
    color: {r['pasif']};
}}
#MSTechSerit QToolButton[toolButtonStyle="2"] {{
    padding: 1px 6px 1px 3px;
}}
#MSTechSerit QToolButton[popupMode="1"] {{
    padding-right: 14px;
}}
#MSTechSerit QToolButton::menu-button {{
    border: none;
    width: 13px;
}}
#MSTechSerit QToolButton::menu-arrow {{
    image: url(qss:images_classic/arrow-down-{r['ok']}.svg);
    height: 11px;
}}
#MSTechSerit QToolButton::menu-arrow:hover, #MSTechSerit QToolButton::menu-arrow:open {{
    image: url(qss:images_classic/arrow-down-{r['ok_vurgu']}.svg);
}}
#MSTechSerit QScrollBar:horizontal {{
    height: 6px;
    background: transparent;
    border: none;
    margin: 0px;
}}
#MSTechSerit QScrollBar::handle:horizontal {{
    background: {r['kenar']};
    border-radius: 3px;
    min-width: 40px;
}}
#MSTechSerit QScrollBar::add-line:horizontal, #MSTechSerit QScrollBar::sub-line:horizontal {{
    width: 0px;
    border: none;
}}
#MSTechSerit QScrollBar::add-page:horizontal, #MSTechSerit QScrollBar::sub-page:horizontal {{
    background: transparent;
}}
#MSTechSerit #MSTechAyrac {{
    background: {r['kenar']};
    border: none;
}}
#MSTechSerit QTabBar {{
    background: transparent;
}}
#MSTechSerit QTabBar::tab {{
    color: {r['soluk']};
    background: transparent;
    border: 1px solid transparent;
    border-top: none;
    padding: 3px 14px 4px 14px;
    margin-right: 1px;
}}
#MSTechSerit QTabBar::tab:hover:!selected {{
    color: {r['vurgu']};
}}
#MSTechSerit QTabBar::tab:selected {{
    color: {r['vurgu_yazi']};
    background: {r['sekme_secili']};
    border-color: {r['kenar']};
    border-bottom: 2px solid {r['vurgu']};
    font-weight: bold;
}}
"""


def onay_kosesi():
    r = renkler()
    return f"""
#MSTechOnayKosesi {{
    background: {r['yuzen_zemin']};
    border: 1px solid {r['yuzen_kenar']};
    border-radius: 7px;
}}
#MSTechOnayKosesi QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 3px;
}}
#MSTechOnayKosesi QToolButton:hover {{
    background: {r['uzerinde']};
    border-color: {r['uzerinde_kenar']};
}}
#MSTechOnayKosesi QToolButton:pressed {{
    background: {r['basili']};
}}
"""


def gorunum_cubugu():
    r = renkler()
    return f"""
#MSTechGorunumCubugu {{
    background: {r['yuzen_zemin']};
    border: 1px solid {r['yuzen_kenar']};
    border-radius: 7px;
}}
#MSTechGorunumCubugu QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 2px;
    margin: 0px;
}}
#MSTechGorunumCubugu QToolButton:hover {{
    background: {r['uzerinde']};
    border-color: {r['uzerinde_kenar']};
}}
#MSTechGorunumCubugu QToolButton:pressed, #MSTechGorunumCubugu QToolButton:checked {{
    background: {r['basili']};
    border-color: {r['basili_kenar']};
}}
#MSTechGorunumCubugu QToolButton[popupMode="1"] {{
    padding-right: 11px;
}}
#MSTechGorunumCubugu QToolButton::menu-button {{
    border: none;
    width: 10px;
}}
#MSTechGorunumCubugu QToolButton::menu-arrow {{
    image: url(qss:images_classic/arrow-down-{r['ok']}.svg);
    height: 9px;
}}
#MSTechGorunumCubugu QToolButton::menu-arrow:hover, #MSTechGorunumCubugu QToolButton::menu-arrow:open {{
    image: url(qss:images_classic/arrow-down-{r['ok_vurgu']}.svg);
}}
#MSTechGorunumCubugu #MSTechAyrac {{
    background: {r['kenar']};
    border: none;
}}
"""
