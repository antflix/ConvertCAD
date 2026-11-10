"""
make_icon.py — regenerate the application icon files in assets/.

The icon is drawn once, as SVG, in convertcad/ui/icons.py (APP_ICON_SVG).
This script renders it to:

    assets/icon.svg   the source drawing (for the README, the web, ...)
    assets/icon.png   256 x 256 PNG
    assets/icon.ico   multi-size Windows icon (16 ... 256 px) used by
                      PyInstaller for ConvertCAD.exe
    assets/icon.icns  macOS icon (16 ... 1024 px) for ConvertCAD.app
                      (made at build time, not kept in the repository)

Only PySide6 is needed (already a dependency). Run from the repository root:

    python scripts/make_icon.py
"""

import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")   # no window needed

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402

from convertcad.ui.icons import APP_ICON_SVG  # noqa: E402

SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)   # sizes Windows asks for
ASSETS = os.path.join(ROOT, "assets")
# macOS .icns entries holding PNG data: type -> size in pixels
ICNS_TYPES = (("icp4", 16), ("icp5", 32), ("icp6", 64), ("ic07", 128),
              ("ic08", 256), ("ic09", 512), ("ic10", 1024),
              ("ic11", 32), ("ic12", 64), ("ic13", 256), ("ic14", 512))


def render_png(renderer: QSvgRenderer, px: int) -> bytes:
    """Render the SVG at px x px and return PNG bytes."""
    img = QImage(px, px, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, px, px))
    painter.end()
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return bytes(data)


def write_ico(path: str, images: dict) -> None:
    """Pack PNG images into one .ico file (PNG entries, Windows Vista+).

    ICO layout: 6-byte header, one 16-byte directory entry per image, then
    the PNG data. A width/height byte of 0 means 256 px.
    """
    sizes = sorted(images)
    offset = 6 + 16 * len(sizes)
    header = struct.pack("<HHH", 0, 1, len(sizes))
    entries, blobs = b"", b""
    for px in sizes:
        png = images[px]
        dim = 0 if px >= 256 else px
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32,
                               len(png), offset)
        blobs += png
        offset += len(png)
    with open(path, "wb") as fh:
        fh.write(header + entries + blobs)


def write_icns(path: str, images: dict) -> None:
    """Pack PNG images into one .icns file (macOS 10.7+ reads PNG entries).

    Layout: 'icns' + total length (big-endian), then for each entry its
    4-letter type + entry length (8-byte header included) + the PNG data.
    """
    body = b""
    for kind, px in ICNS_TYPES:
        png = images[px]
        body += kind.encode("ascii") + struct.pack(">I", len(png) + 8) + png
    with open(path, "wb") as fh:
        fh.write(b"icns" + struct.pack(">I", len(body) + 8) + body)


def main() -> int:
    app = QGuiApplication(sys.argv[:1])          # noqa: F841 (needed by Qt)
    os.makedirs(ASSETS, exist_ok=True)
    renderer = QSvgRenderer(QByteArray(APP_ICON_SVG.encode("utf-8")))
    if not renderer.isValid():
        print("ERROR: APP_ICON_SVG is not a valid SVG drawing.")
        return 1
    images = {px: render_png(renderer, px)
              for px in set(SIZES) | {px for _, px in ICNS_TYPES}}
    with open(os.path.join(ASSETS, "icon.svg"), "w", encoding="utf-8") as fh:
        fh.write(APP_ICON_SVG + "\n")
    with open(os.path.join(ASSETS, "icon.png"), "wb") as fh:
        fh.write(images[256])
    write_ico(os.path.join(ASSETS, "icon.ico"),
              {px: images[px] for px in SIZES})
    write_icns(os.path.join(ASSETS, "icon.icns"), images)
    print("Written: assets/icon.svg, assets/icon.png, assets/icon.ico, "
          "assets/icon.icns "
          f"({', '.join(str(s) for s in SIZES)} px)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
