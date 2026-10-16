<div align="center">

<img src="src/Gui/Icons/mstech-aicad.svg" width="110" alt="MSTech Ai-CAD logo">

# MSTech Ai-CAD

**AI-assisted parametric 3D CAD — describe it, watch it get built.**

[![Release](https://img.shields.io/github/v/release/MSTECHtr/MSTech-AiCAD?include_prereleases&label=release)](https://github.com/MSTECHtr/MSTech-AiCAD/releases)
[![Build](https://img.shields.io/github/actions/workflow/status/MSTECHtr/MSTech-AiCAD/mstech_release.yml?label=build)](https://github.com/MSTECHtr/MSTech-AiCAD/actions)
[![License: LGPL-2.1](https://img.shields.io/badge/license-LGPL--2.1--or--later-blue)](LICENSE)
![Platforms](https://img.shields.io/badge/platforms-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)

[Download](#download) · [Features](#features) · [Claude assistant](#claude-assistant) · [Build from source](#build-from-source) · [Türkçe](#türkçe)

</div>

---

MSTech Ai-CAD is a professional 3D parametric modeler built on [FreeCAD](https://www.freecad.org).
It combines a familiar, SolidWorks-style workflow with a built-in AI design assistant powered by
[Claude](https://claude.com): ask for a part in plain language and the assistant asks clarifying
questions, then models it feature by feature while you watch.

## Download

Get the latest installers from the **[Releases](https://github.com/MSTECHtr/MSTech-AiCAD/releases)** page.

| Platform | Package |
|---|---|
| Windows 10/11 (64-bit) | `…-Windows-x86_64-installer.exe` · portable `.7z` |
| Ubuntu / Debian / Mint | `.deb` |
| Fedora / openSUSE | `.rpm` |
| Arch / Manjaro | `.pkg.tar.zst` |
| Any Linux | `.AppImage` |
| macOS (Apple Silicon M1–M4) | `…-macOS11-arm64.dmg` |
| macOS (Intel) | `…-macOS10-x86_64.dmg` |

> Builds are not yet code-signed. On Windows choose *More info → Run anyway*; on macOS right-click the app and choose *Open* the first time.

## Features

- **Command ribbon** — tabbed CommandManager-style ribbon with large primary commands and compact
  secondary columns; switches automatically to sketch tools while editing a sketch.
- **Heads-up view toolbar** and **confirmation corner** (✓ / ✗) inside the 3D view.
- **Property-manager workflow** — task panels open next to the model tree.
- **Familiar navigation** — SolidWorks-style mouse controls, blue/white gradient viewport,
  orange pre-selection and blue selection highlighting.
- **MSTech Light & Dark themes**, Turkish and English interface.
- **Full FreeCAD power** — Part Design, Sketcher, Assembly, TechDraw, BIM, Mesh and more;
  files are fully compatible with FreeCAD (`.FCStd`).

## Claude assistant

The Claude panel (right side) turns requests such as *"draw a 200 mm sigma profile"* or
*"design a simple gearbox housing"* into real, parametric geometry:

- asks about dimensions, purpose and material before larger projects;
- builds step by step, narrating each step and listing the parts it adds;
- inspects the model and takes snapshots of the 3D view to verify its own work;
- every step is a single undo step (Ctrl+Z); failed steps are rolled back automatically.

**Sign-in options**

1. **Claude subscription (Pro / Max)** — the panel uses [Claude Code](https://claude.com/claude-code)
   on your computer and offers one-click installation and sign-in. Intended for personal use.
2. **Anthropic API key** — enter it via the *API key* button; usage is billed to your API account.

## Build from source

Requires [pixi](https://pixi.sh) (installs all dependencies without root). The source path must not
contain spaces.

```bash
git clone https://github.com/MSTECHtr/MSTech-AiCAD.git
cd MSTech-AiCAD
pixi install
pixi run cmake --preset conda-linux-release -B build/release -DENABLE_DEVELOPER_TESTS=OFF
pixi run cmake --build build/release
pixi run build/release/bin/FreeCAD
```

## License & attribution

MSTech Ai-CAD is free software licensed under the **LGPL-2.1-or-later**. It is a modified version of
FreeCAD; all FreeCAD copyright and license notices are preserved (see [LICENSE](LICENSE)). The first
commit of this repository is the unmodified FreeCAD source (main, `d732e2f`); MSTech changes are in
the commits that follow. FreeCAD is a trademark of the FreeCAD project; MSTech Ai-CAD is not
affiliated with or endorsed by the FreeCAD project or Dassault Systèmes.

---

## Türkçe

**MSTech Ai-CAD**, FreeCAD tabanlı, yapay zekâ destekli parametrik 3B CAD programıdır. SolidWorks'e
benzer tanıdık bir arayüzü, Claude ile çalışan yerleşik bir tasarım asistanıyla birleştirir: ne
istediğini yaz, Claude sorularını sorsun ve parçayı adım adım, sen izlerken çizsin.

- **İndir:** [Sürümler](https://github.com/MSTECHtr/MSTech-AiCAD/releases) sayfasından Windows,
  Linux (.deb, .rpm, Arch, AppImage) ve macOS (Intel / Apple Silicon) paketleri.
- **Komut şeridi, görünüm çubuğu, onay köşesi**, MSTech Açık/Koyu temalar, Türkçe arayüz.
- **Claude asistanı:** Claude aboneliğinle (Claude Code üzerinden, tek tıkla kurulum ve giriş) ya da
  Anthropic API anahtarıyla çalışır. Her adım Ctrl+Z ile geri alınabilir.
- **Lisans:** LGPL-2.1-or-later; FreeCAD'in değiştirilmiş bir sürümüdür.
