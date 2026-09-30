"""Generate the printable FieldTest Recorder test card (150 x 105 mm) as a 600-dpi PNG and an A4 PDF.

Layout = colour_engine's canonical 1000 x 700 units (1 unit = 0.15 mm): four ArUco 4x4 markers (18 mm),
24 colour patches (10.5 mm, ColorChecker design values rendered for D65), two well circles, a package-label
zone, a 50 mm scale bar. Print at 100% scale on matte paper; verify the scale bar with a ruler.
"""
import sys
import zlib
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / "research"))
import colour_engine as ce  # noqa: E402
import sim  # noqa: E402

DPI = 600
MM = DPI / 25.4
CARD_MM = (150, 105)
U = CARD_MM[0] * MM / ce.CARD_W                     # pixels per canonical unit
OUT = HERE / "docs" / "validation" / "card"


def px(v):
    return int(round(v * U))


def build():
    W, H = px(ce.CARD_W), px(ce.CARD_H)
    img = Image.new("RGB", (W, H), (245, 245, 243))
    d = ImageDraw.Draw(img)
    for mid, (x, y) in ce.MARKERS.items():
        m = cv2.aruco.generateImageMarker(ce.ARUCO, mid, px(ce.MARKER))
        img.paste(Image.fromarray(m).convert("RGB"), (px(x), px(y)))
    srgb = np.clip(sim.srgb_encode(sim.CARD_LIN_D65 / sim.CARD_LIN_D65[sim.WHITE_IDX].max() * 0.95), 0, 1)
    for i in range(24):
        x, y, w, h = ce.patch_rect(i)
        d.rectangle([px(x), px(y), px(x + w) - 1, px(y + h) - 1], fill=tuple(int(v * 255 + 0.5) for v in srgb[i]))
    font = ImageFont.load_default(size=int(1.8 * MM))    # 1.8 mm tall text; the bitmap default prints at ~0.4 mm
    roles = {"W1": "SAMPLE well", "W2": "BLANK well (reagent only)"}      # v2: blank in every photo (E17)
    for k, (wid, (cx, cy)) in enumerate(ce.WELLS.items()):
        r = px(ce.WELL_R)
        d.ellipse([px(cx) - r, px(cy) - r, px(cx) + r, px(cy) + r], outline=(90, 90, 90), width=max(2, px(1.5)))
        d.text((px(cx) - r, px(cy) + r + px(6)), f"{wid}  {roles.get(wid, 'place well / tube here')}", fill=(60, 60, 60), font=font)
    d.rectangle([px(640), px(560), px(850), px(685)], outline=(90, 90, 90), width=max(2, px(1.2)))
    d.text((px(648), px(566)), "PACKAGE LABEL (P-n) HERE", fill=(60, 60, 60), font=font)
    d.line([px(150), px(530), px(150) + int(50 * MM), px(530)], fill=(0, 0, 0), width=max(3, px(2)))
    d.text((px(150), px(540)), "50 mm scale check", fill=(0, 0, 0), font=font)
    d.text((px(150), px(600)), "FieldTest Recorder TEST CARD v2 - design values - NOT FOR EVIDENTIAL USE",
           fill=(0, 0, 0), font=font)
    d.text((px(150), px(625)), "Print at 100% on matte paper. Characterise each print batch before use.",
           fill=(0, 0, 0), font=font)
    return img


def write_pdf(img, path, dpi):
    """One-page PDF with the image stored losslessly (Flate). Pillow's PDF writer uses JPEG, which shifts patch colours."""
    w, h = img.size
    pw, ph = w * 72 / dpi, h * 72 / dpi
    data = zlib.compress(img.convert("RGB").tobytes(), 9)
    content = f"q {pw:.2f} 0 0 {ph:.2f} 0 0 cm /Im0 Do Q".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {pw:.2f} {ph:.2f}] "
            f"/Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>".encode(),
            f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB "
            f"/BitsPerComponent 8 /Filter /FlateDecode /Length {len(data)} >>\nstream\n".encode() + data + b"\nendstream",
            f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    Path(path).write_bytes(out)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    card = build()
    card.save(OUT / "ftr-card-150x105mm.png", dpi=(DPI, DPI))
    a4 = Image.new("RGB", (int(210 * MM), int(297 * MM)), (255, 255, 255))
    ox, oy = (a4.width - card.width) // 2, (a4.height - card.height) // 2
    a4.paste(card, (ox, oy))
    d = ImageDraw.Draw(a4)
    L = int(8 * MM)
    for (x, y) in ((ox, oy), (ox + card.width, oy), (ox, oy + card.height), (ox + card.width, oy + card.height)):
        d.line([x - L, y, x - int(2 * MM), y], fill=0, width=3); d.line([x + int(2 * MM), y, x + L, y], fill=0, width=3)
        d.line([x, y - L, x, y - int(2 * MM)], fill=0, width=3); d.line([x, y + int(2 * MM), x, y + L], fill=0, width=3)
    write_pdf(a4, OUT / "ftr-card-150x105mm.pdf", DPI)
    # self-check: the engine must find all four markers on the flat card image
    rgb = np.array(card)
    small = cv2.resize(rgb, (ce.CARD_W + 300, int((ce.CARD_W + 300) * rgb.shape[0] / rgb.shape[1])), interpolation=cv2.INTER_AREA)
    pad = cv2.copyMakeBorder(small, 80, 80, 80, 80, cv2.BORDER_CONSTANT, value=(40, 40, 40))
    print("card:", card.size, "px at", DPI, "dpi =", CARD_MM, "mm; engine finds card:", ce.rectify(pad) is not None)


if __name__ == "__main__":
    main()
