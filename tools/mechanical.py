#!/usr/bin/env python3
"""
Mechanical package for the NA522-compatible card:
  * re-derives socket / peg coordinates from the underside photograph with a
    4-point homography (board corners -> 83.5 x 50.5 mm) for BOTH boards and
    cross-checks them (the T and B boards are mirror images),
  * writes annotated photographs and dimensioned drawings (T and B),
  * writes common/mechanical/connector_positions.csv.
usage: work/venv/bin/python tools/mechanical.py
"""
import os, sys, csv
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from placement import SOCKETS_T, PEG_T, PEG_DIA, BOARD_W, BOARD_H
from circuit import CONNECTOR_NETS

OUT = os.path.join(ROOT, "common", "mechanical")
PHOTO_UNDER = os.path.join(ROOT, "PXL_20261112_171350076.jpg")   # both cards, solder side up
PHOTO_MOBO = os.path.join(ROOT, "PXL_20261112_171250260.jpg")    # NAC82 with cards removed
PHOTO_INSITU = os.path.join(ROOT, "PXL_20261112_170813063.jpg")  # cards fitted

# Pixel measurements in PHOTO_UNDER (1723 x 795). Board corners from colour
# segmentation (bottom edge reduced ~5 px for the visible PCB edge thickness);
# socket centres = centre of the gold box contact; peg = hole centre.
# NOTE: turning the pair over swapped them: the board on the RIGHT of this
# photo is the T board, the LEFT one is the B board (verified against the
# motherboard pin pattern in PHOTO_MOBO).
MEAS = {
    "T": {"corners": [(874, 154), (1594, 141), (1622, 565), (883, 576)],
          "pts": {"S1": (903, 416), "S2": (1036, 276), "S3": (1513, 168), "S4": (1605, 296), "peg": (1110, 293)}},
    "B": {"corners": [(81, 143), (827, 154), (829, 579), (63, 575)],
          "pts": {"S1": (180, 176), "S2": (96, 309), "S3": (670, 288), "S4": (805, 426), "peg": (593, 298)}},
}
# socket -> connector name (T board); B uses the mirror partner
SOCK2P_T = {"S1": "P1", "S2": "P2", "S3": "P3", "S4": "P4"}
SOCK2P_B = {"S4": "P1", "S3": "P2", "S1": "P3", "S2": "P4"}
# motherboard pins in PHOTO_MOBO (1549 x 1163)
MOBO = {"T": {"P1": (88, 380), "P2": (190, 482), "P3": (592, 577), "P4": (655, 462), "peg": (245, 470)},
        "B": {"P4": (845, 465), "P3": (910, 577), "P2": (1300, 502), "P1": (1415, 386), "peg": (1250, 480)}}


def homography(src, dst):
    A = []
    for (x, y), (u, v) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u]); A.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    _, _, Vt = np.linalg.svd(np.array(A, float))
    h = Vt[-1].reshape(3, 3)
    return h / h[2, 2]


def apply(h, p):
    v = h @ np.array([p[0], p[1], 1.0])
    return v[:2] / v[2]


def measure():
    """returns dict hand -> name -> (X, Y) in installed frame (Y up)"""
    res = {}
    for hand, m in MEAS.items():
        # photo shows the underside; image top edge = board edge nearest the rear panel?  The
        # underside view is the installed view flipped about the horizontal axis, so the
        # distance from the image TOP edge equals the installed Y (from the bottom edge).
        h = homography(m["corners"], [(0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H)])
        mp = SOCK2P_T if hand == "T" else SOCK2P_B
        res[hand] = {}
        for k, p in m["pts"].items():
            X, Yd = apply(h, p)
            res[hand][mp.get(k, k)] = (float(X), float(Yd))
    return res


def main():
    os.makedirs(OUT, exist_ok=True)
    r = measure()
    rows = []
    for name in ("P1", "P2", "P3", "P4", "peg"):
        t = r["T"][name]; b = r["B"][name]
        bm = (BOARD_W - b[0], b[1])
        used = SOCKETS_T[name] if name != "peg" else PEG_T
        rows.append([name, CONNECTOR_NETS.get(name, "retaining peg"), "%.1f" % t[0], "%.1f" % t[1], "%.1f" % bm[0], "%.1f" % bm[1],
                     "%.1f" % abs(t[0] - bm[0]), "%.1f" % abs(t[1] - bm[1]), "%.1f" % used[0], "%.1f" % used[1],
                     "%.1f" % (BOARD_W - used[0]), "%.1f" % used[1]])
    hdr = ["item", "function (inferred)", "T meas X", "T meas Y", "B meas mirrored X", "B meas Y", "|dX| T vs B", "|dY| T vs B",
           "T design X", "T design Y", "B design X", "B design Y"]
    with open(os.path.join(OUT, "connector_positions.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(hdr); w.writerows(rows)
    print("\n".join(", ".join(x) for x in [hdr] + rows))

    # ---------- annotated underside photo
    im = Image.open(PHOTO_UNDER).convert("RGB")
    dr = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    except Exception:
        font = ImageFont.load_default()
    for hand, m in MEAS.items():
        dr.polygon(m["corners"], outline=(255, 255, 0), width=2)
        mp = SOCK2P_T if hand == "T" else SOCK2P_B
        for k, (x, y) in m["pts"].items():
            col = (255, 0, 255) if k == "peg" else (255, 40, 40)
            dr.ellipse([x - 9, y - 9, x + 9, y + 9], outline=col, width=3)
            nm = mp.get(k, "peg")
            dr.text((x + 11, y - 12), "%s %s" % (nm, CONNECTOR_NETS.get(nm, "")), fill=col, font=font)
        cx = sum(c[0] for c in m["corners"]) / 4
        dr.text((cx - 60, 105), "%s board (underside)" % hand, fill=(255, 255, 0), font=font)
    im.save(os.path.join(OUT, "annotated_underside_photo.jpg"), quality=92)

    im = Image.open(PHOTO_MOBO).convert("RGB")
    dr = ImageDraw.Draw(im)
    for hand, pts in MOBO.items():
        for nm, (x, y) in pts.items():
            col = (255, 0, 255) if nm == "peg" else (255, 40, 40)
            dr.ellipse([x - 12, y - 12, x + 12, y + 12], outline=col, width=3)
            dr.text((x + 14, y - 30), "%s %s %s" % (hand, nm, CONNECTOR_NETS.get(nm, "")), fill=col, font=font)
    dr.text((20, 1100), "Pin functions INFERRED: P3 wide trace to input-cable screen (GND); P2 thin trace via series R to selector (OUT); "
            "P4/P1 no top-side trace (IN / +24 V) - VERIFY", fill=(255, 255, 0), font=font)
    im.save(os.path.join(OUT, "annotated_motherboard_pins.jpg"), quality=92)

    # ---------- dimensioned drawings
    for hand in ("T", "B"):
        fig, ax = plt.subplots(figsize=(12, 8))
        mir = (lambda x: BOARD_W - x) if hand == "B" else (lambda x: x)
        ax.add_patch(Polygon([(0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H)], fill=False, lw=2))
        for nm, (x, y) in SOCKETS_T.items():
            X = mir(x)
            ax.add_patch(Circle((X, y), 2.8, fill=False, lw=1, color="C1"))
            ax.add_patch(Circle((X, y), 2.05, fill=False, lw=1, ls="--", color="C1"))
            ax.add_patch(Circle((X, y), 1.5, fill=False, lw=1.5, color="r", ls=":"))  # +/-1.5 mm uncertainty
            ax.plot([X], [y], "k+")
            ax.annotate("%s %s\n(%.1f, %.1f)" % (nm, CONNECTOR_NETS[nm], X, y), (X, y), xytext=(X + (4 if X < 60 else -22), y + 4),
                        fontsize=9, arrowprops=dict(arrowstyle="-", lw=.5))
            ax.plot([0, X], [y, y], ":", color="grey", lw=.6); ax.plot([X, X], [0, y], ":", color="grey", lw=.6)
            mx, my = r[hand][nm]
            mxx = mx if hand == "T" else mx
            ax.plot([mxx], [my], "bx")
        px, py = mir(PEG_T[0]), PEG_T[1]
        ax.add_patch(Circle((px, py), PEG_DIA / 2, fill=False, color="m", lw=1.5))
        ax.add_patch(Circle((px, py), 3.6, fill=False, color="m", lw=.6, ls="--"))
        ax.annotate("retaining peg hole d%.1f NPTH\n(%.1f, %.1f)" % (PEG_DIA, px, py), (px, py), xytext=(px + 4, py - 9), fontsize=9,
                    arrowprops=dict(arrowstyle="-", lw=.5))
        ax.set_xlim(-6, BOARD_W + 6); ax.set_ylim(-6, BOARD_H + 6); ax.set_aspect("equal"); ax.grid(alpha=.25)
        ax.set_title("NA522-compatible card, %s board - outline %.1f x %.1f mm, viewed from COMPONENT side as installed\n"
                     "origin = bottom-left corner; +Y towards NAC82 rear panel. Sockets (Mill-Max 0391) fitted on underside.\n"
                     "orange: 5.6 mm pad / 4.1 mm hole; red dotted: +/-1.5 mm position uncertainty; blue x: raw photo measurement"
                     % (hand, BOARD_W, BOARD_H), fontsize=9)
        ax.set_xlabel("mm"); ax.set_ylabel("mm")
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "mechanical_%s.png" % hand), dpi=130)
        fig.savefig(os.path.join(OUT, "mechanical_%s.pdf" % hand))
        plt.close(fig)


if __name__ == "__main__":
    main()
