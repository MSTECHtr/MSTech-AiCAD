# SPDX-License-Identifier: LGPL-2.1-or-later
# MSTech Ai-CAD arayüz modülü: komut şeridi, görünüm çubuğu ve ilk açılış ayarları.

SET(MSTech_SRCS
    InitGui.py
    MSTechArayuz/__init__.py
    MSTechArayuz/claude_araclari.py
    MSTechArayuz/claude_paneli.py
    MSTechArayuz/gorunum_cubugu.py
    MSTechArayuz/kopru.py
    MSTechArayuz/kurulum.py
    MSTechArayuz/mstech_mcp_sunucu.py
    MSTechArayuz/metin.py
    MSTechArayuz/onay_kosesi.py
    MSTechArayuz/serit.py
    MSTechArayuz/stil.py
)

SET(MSTech_Ayarlar
    Ayarlar/MSTech-varsayilan.cfg
)

SOURCE_GROUP("" FILES ${MSTech_SRCS} ${MSTech_Ayarlar})

ADD_CUSTOM_TARGET(MSTech ALL
    SOURCES ${MSTech_SRCS} ${MSTech_Ayarlar}
)

fc_copy_sources(MSTech "${CMAKE_BINARY_DIR}/Mod/MSTech" ${MSTech_SRCS} ${MSTech_Ayarlar})

INSTALL(FILES InitGui.py DESTINATION Mod/MSTech)
INSTALL(DIRECTORY MSTechArayuz DESTINATION Mod/MSTech FILES_MATCHING PATTERN "*.py")
INSTALL(FILES ${MSTech_Ayarlar} DESTINATION Mod/MSTech/Ayarlar)
