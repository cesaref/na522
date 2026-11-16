#!/usr/bin/env python3
"""
Draw the schematic (SVG + PNG + PDF) for each design from tools/circuit.py values.
usage: work/venv/bin/python tools/draw_schematic.py
"""
import os, sys
import schemdraw
import schemdraw.elements as elm
import matplotlib
matplotlib.use("Agg")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from circuit import DESIGNS, QMODELS, CONNECTOR_NETS, fmt

DIRS = {"tht": "design1_tht", "smd": "design2_smd"}
VCC_Y, GND_Y = 14.0, -2.0


def lab(v, unit=""):
    if v is None:
        return "DNF"
    if v == 0:
        return "0R link"
    return fmt(v, unit)


def R(d, ref, vals, a, b, loc="bottom"):
    return d.add(elm.Resistor().endpoints(a, b).label("%s\n%s" % (ref, lab(vals.get(ref))), loc=loc, fontsize=8))


def C(d, ref, vals, a, b, pol=False, loc="bottom"):
    e = elm.Capacitor(polar=True) if pol else elm.Capacitor()
    return d.add(e.endpoints(a, b).label("%s\n%s" % (ref, lab(vals.get(ref), "F")), loc=loc, fontsize=8))


def L(d, *pts):
    for a, b in zip(pts[:-1], pts[1:]):
        d.add(elm.Line().endpoints(a, b))


def dot(d, p):
    d.add(elm.Dot().at(p))


def gnd(d, p):
    d.add(elm.Ground().at(p))


def lbl(d, p, t, fs=8):
    d.add(elm.Label().at(p).label(t, fontsize=fs))


def stage(d, vals, key, X, refs, fb):
    """One Naim gain stage on an explicit grid. Input = base of Qa at (X, 5).
    Returns output node (x, 5) and the x where the stage ends."""
    qm = QMODELS[key]
    Y = 5.0
    qa = d.add(elm.BjtNpn(circle=True).anchor("base").at((X, Y)))
    lbl(d, (X - 1.0, 3.8), "%s\n%s" % (refs["qa"], qm["NPN"]))
    N = (X + 0.75, 8.0)
    L(d, qa.collector, N); dot(d, N)
    R(d, refs["rla"], vals, N, (N[0], VCC_Y), loc="top")
    qb = d.add(elm.BjtPnp(circle=True).anchor("base").at((X + 2.2, 8.0)))
    lbl(d, (X + 4.2, 8.9), "%s\n%s" % (refs["qb"], qm["PNP"]))
    L(d, N, qb.base)
    R(d, refs["reb"], vals, qb.emitter, (qb.emitter[0], VCC_Y), loc="bottom")
    M = (qb.collector[0], 6.4)
    L(d, qb.collector, M); dot(d, M)
    R(d, refs["rlb"], vals, M, (M[0], 4.2), loc="top"); gnd(d, (M[0], 4.2))
    L(d, M, (X + 3.9, 6.4))
    R(d, refs["rbase"], vals, (X + 3.9, 6.4), (X + 3.9, 10.0), loc="bottom")
    qc = d.add(elm.BjtNpn(circle=True).anchor("base").at((X + 6.0, 10.0)))
    L(d, (X + 3.9, 10.0), qc.base)
    lbl(d, (X + 7.9, 10.0), "%s\n%s" % (refs["qc"], qm["NPN_P"]))
    L(d, qc.collector, (qc.collector[0], VCC_Y)); dot(d, (qc.collector[0], VCC_Y))
    O = (qc.emitter[0], Y)
    L(d, qc.emitter, O); dot(d, O)
    # emitter node of Qa and feedback line at y = 3
    E = (X + 0.75, 3.0)
    L(d, qa.emitter, E); dot(d, E)
    fb(d, E, O, X)
    # current sink to the right
    xs = X + 9.8
    L(d, O, (xs, Y)); dot(d, (xs, Y))
    q5 = d.add(elm.BjtNpn(circle=True).anchor("collector").at((xs, 3.2)))
    L(d, (xs, Y), (xs, 3.2))
    lbl(d, (xs + 1.3, 2.5), "%s\n%s" % (refs["qs"], qm["NPN_P"]))
    Z = (xs, 0.2)
    L(d, q5.emitter, Z); dot(d, Z)
    R(d, refs["rs"], vals, Z, (xs, GND_Y), loc="bottom")
    q4 = d.add(elm.BjtNpn(circle=True).reverse().anchor("base").at((xs - 0.7, 0.2)))
    L(d, q4.base, Z)
    lbl(d, (q4.collector[0] - 1.3, -0.8), "%s\n%s" % (refs["qk"], qm["NPN"]))
    L(d, q4.emitter, (q4.emitter[0], GND_Y))
    Yn = (q4.collector[0], q5.base[1])
    L(d, q4.collector, Yn, q5.base); dot(d, Yn)
    xb = Yn[0] - 0.6
    L(d, Yn, (xb, Yn[1]))
    R(d, refs["rbias"], vals, (xb, Yn[1]), (xb, VCC_Y), loc="top")
    return O, xs + 0.8


def draw(key):
    vals = DESIGNS[key]["values"]
    d = schemdraw.Drawing(show=False)
    d.config(unit=2.0, fontsize=9)
    XEND = 63.0
    L(d, (1.5, VCC_Y), (XEND, VCC_Y))
    L(d, (-1.5, GND_Y), (XEND, GND_Y))
    lbl(d, (XEND - 2, VCC_Y + 0.5), "VCC (~23.4 V)")
    # supply
    d.add(elm.Dot(open=True).at((-1.5, 16.5)).label("P1  +24 V", loc="left"))
    R(d, "R25", vals, (-1.5, 16.5), (1.5, 16.5), loc="top")
    L(d, (1.5, 16.5), (1.5, VCC_Y)); dot(d, (1.5, VCC_Y))
    C(d, "C8", vals, (1.5, VCC_Y), (1.5, 11.2), pol=True, loc="bottom"); gnd(d, (1.5, 11.2))
    L(d, (4.0, VCC_Y), (4.0, VCC_Y)); dot(d, (4.0, VCC_Y))
    C(d, "C9", vals, (4.0, VCC_Y), (4.0, 11.2), loc="bottom"); gnd(d, (4.0, 11.2))
    d.add(elm.Dot(open=True).at((-1.5, GND_Y)).label("P3  GND", loc="left"))
    # input network
    Y = 5.0
    d.add(elm.Dot(open=True).at((-1.5, Y)).label("P4  IN", loc="left"))
    L(d, (-1.5, Y), (0.0, Y)); dot(d, (0.0, Y))
    R(d, "R1", vals, (0.0, Y), (0.0, GND_Y), loc="bottom")
    C(d, "C1", vals, (2.6, Y), (0.0, Y), pol=(key == "tht"), loc="bottom")   # + towards bias node B1
    B1 = (3.0, Y)
    L(d, (2.6, Y), B1); dot(d, B1)
    R(d, "R2", vals, B1, (B1[0], GND_Y), loc="bottom")
    B1F = (3.0, 8.6)
    R(d, "R26", vals, B1, B1F, loc="bottom"); dot(d, B1F)
    R(d, "R3", vals, B1F, (3.0, VCC_Y), loc="bottom"); dot(d, (3.0, VCC_Y))
    L(d, B1F, (5.2, 8.6))
    C(d, "C10", vals, (5.2, 8.6), (5.2, 6.4), pol=True, loc="bottom"); gnd(d, (5.2, 6.4))
    R(d, "R4", vals, B1, (6.3, Y), loc="bottom")
    dot(d, (6.3, Y))
    C(d, "C2", vals, (6.3, Y), (6.3, GND_Y), loc="bottom")
    lbl(d, (1.5, 3.4), "B1", 7)

    def fb1(d, E, O, X):
        L(d, E, (O[0], E[1]))
        R(d, "R10", vals, O, (O[0], E[1]), loc="bottom")
        dot(d, (O[0], E[1])) if False else None
        R(d, "R6", vals, E, (E[0], 0.4), loc="top")
        C(d, "C3", vals, (E[0], 0.4), (E[0], GND_Y), pol=True, loc="top")

    X1 = 8.5
    L(d, (6.3, Y), (X1, Y))
    refs1 = dict(qa="Q1", qb="Q2", qc="Q3", qs="Q5", qk="Q4", rla="R5", reb="R7", rlb="R8",
                 rbase="R9", rs="R13", rbias="R11")
    O1, xe = stage(d, vals, key, X1, refs1, fb1)
    lbl(d, (O1[0] + 0.6, Y + 0.5), "O1", 8)
    # 75 us network
    x0 = xe + 0.5
    L(d, (xe - 0.8, Y), (x0, Y))
    R(d, "R12", vals, (x0, Y), (x0 + 2.8, Y), loc="top")
    p = (x0 + 2.8, Y); dot(d, p)
    C(d, "C4", vals, p, (p[0], GND_Y), loc="bottom")
    lbl(d, (x0 + 1.4, 3.0), "75 us", 7)

    def fb2(d, E, O, X):
        L(d, E, (E[0] - 1.3, E[1]))
        R(d, "R15", vals, (E[0] - 1.3, E[1]), (E[0] - 1.3, GND_Y), loc="top")
        R(d, "R16", vals, E, (E[0], 0.4), loc="bottom")
        C(d, "C5", vals, (E[0], 0.4), (E[0], GND_Y), pol=True, loc="bottom")
        L(d, E, (X + 1.4, 3.0))
        R(d, "R17", vals, (X + 1.4, 3.0), (X + 3.4, 3.0), loc="bottom")
        F = (X + 3.6, 3.0)
        L(d, (X + 3.4, 3.0), F); dot(d, F)
        R(d, "R21", vals, F, (O[0], 3.0), loc="top")
        L(d, (O[0], 3.0), O)
        dot(d, (O[0], 3.0))
        L(d, F, (F[0], 1.4))
        C(d, "C6", vals, (F[0], 1.4), (O[0], 1.4), loc="bottom")
        L(d, (O[0], 1.4), (O[0], 3.0))
        L(d, F, (F[0], 1.4))
        L(d, (F[0], 1.4), (F[0], 0.2)) if False else None
        lbl(d, (F[0] - 0.2, 3.5), "F2", 7)
        # C6B (trim, parallel to C6) drawn below C6
        L(d, (F[0], 1.4), (F[0], -0.4))
        C(d, "C6B", vals, (F[0], -0.4), (O[0], -0.4), loc="bottom")
        L(d, (O[0], -0.4), (O[0], 1.4))

    X2 = p[0] + 3.0
    L(d, p, (X2, Y))
    refs2 = dict(qa="Q6", qb="Q7", qc="Q8", qs="Q10", qk="Q9", rla="R14", reb="R18", rlb="R19",
                 rbase="R22", rs="R20", rbias="R23")
    O2, xe2 = stage(d, vals, key, X2, refs2, fb2)
    lbl(d, (O2[0] + 0.6, Y + 0.5), "O2", 8)
    xo = xe2 + 0.5
    L(d, (xe2 - 0.8, Y), (xo, Y))
    C(d, "C7", vals, (xo, Y), (xo + 2.6, Y), pol=True, loc="top")
    po = (xo + 3.2, Y)
    L(d, (xo + 2.6, Y), po); dot(d, po)
    R(d, "R24", vals, po, (po[0], GND_Y), loc="bottom")
    L(d, po, (po[0] + 2.0, Y))
    d.add(elm.Dot(open=True).at((po[0] + 2.0, Y)).label("P2  OUT", loc="right"))
    lbl(d, (30, 19.0), DESIGNS[key]["name"], 13)
    lbl(d, (30, -5.0), "Topology: Naim NA322/4 as traced by M. Stockert (2019). P1-P4 are the card sockets (pin functions inferred from photos - VERIFY). "
        "R20 = second 'R19 68R' of the original drawing.", 8)
    lbl(d, (30, -6.0), "R26/C10: optional bias-supply filter (design 1 default: R26 = 0R link, C10 not fitted). C6B: optional RIAA trim. "
        "Values generated from tools/circuit.py.", 8)
    out = os.path.join(ROOT, DIRS[key], "schematic")
    os.makedirs(out, exist_ok=True)
    for ext in ("svg", "png", "pdf"):
        fn = os.path.join(out, "na522_%s_schematic.%s" % (key, ext))
        d.save(fn, dpi=150) if ext == "png" else d.save(fn)


if __name__ == "__main__":
    for k in ("tht", "smd"):
        draw(k)
        print("drew", k)
