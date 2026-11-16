#!/usr/bin/env python3
"""
Build, autoroute, DRC and export the NA522-compatible PCBs.

Must be run with KiCad's bundled python (it needs `pcbnew`):
  KPY=~/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
  $KPY tools/build_pcb.py tht T      # design (tht|smd), board hand (T|B)

Steps: place footprints from tools/placement.py, assign nets from tools/circuit.py,
draw outline/peg hole/silkscreen, export Specctra DSN, run Freerouting headless,
import the session, add GND pours (both layers), fill, save, then kicad-cli
DRC + Gerber/drill/position/SVG/3D-render export.
"""
import os, sys, subprocess, shutil, math, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pcbnew
from circuit import TOPOLOGY, DESIGNS, CONNECTOR_NETS, fmt
from placement import PLACEMENTS, SOCKETS_T, PEG_T, PEG_DIA, BOARD_W, BOARD_H

KAPP = os.path.expanduser("~/Applications/KiCad/KiCad.app/Contents")
KCLI = os.path.join(KAPP, "MacOS", "kicad-cli")
FPLIB = os.path.join(KAPP, "SharedSupport", "footprints")
JAVA = "/opt/homebrew/opt/openjdk/bin/java"
FREEROUTING = os.path.join(ROOT, "work", "bin", "freerouting.jar")
LOCAL_LIB = os.path.join(ROOT, "common", "kicad_lib", "NA5xx.pretty")
DIRS = {"tht": "design1_tht", "smd": "design2_smd"}
ORIGIN = (100.0, 100.0)  # KiCad page position of the board's top-left corner

# ---------------------------------------------------------------- footprints
FP = {
    "tht": {
        "R": ("Resistor_THT", "R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal"),
        "Q": ("Package_TO_SOT_THT", "TO-92_Inline"),
        "C1": ("Capacitor_THT", "CP_Radial_Tantal_D5.5mm_P5.00mm"),
        "C7": ("Capacitor_THT", "CP_Radial_Tantal_D5.5mm_P5.00mm"),
        "C3": ("Capacitor_THT", "CP_Radial_D6.3mm_P2.50mm"),
        "C5": ("Capacitor_THT", "CP_Radial_D6.3mm_P2.50mm"),
        "C8": ("Capacitor_THT", "CP_Radial_D6.3mm_P2.50mm"),
        "C10": ("Capacitor_THT", "CP_Radial_D5.0mm_P2.00mm"),
        "C2": ("Capacitor_THT", "C_Rect_L7.2mm_W2.5mm_P5.00mm_FKS2_FKP2_MKS2_MKP2"),
        "C6B": ("Capacitor_THT", "C_Rect_L7.2mm_W2.5mm_P5.00mm_FKS2_FKP2_MKS2_MKP2"),
        "C9": ("Capacitor_THT", "C_Rect_L7.2mm_W2.5mm_P5.00mm_FKS2_FKP2_MKS2_MKP2"),
        "C4": ("Capacitor_THT", "C_Rect_L7.2mm_W3.0mm_P5.00mm_FKS2_FKP2_MKS2_MKP2"),
        "C6": ("Capacitor_THT", "C_Rect_L7.2mm_W4.5mm_P5.00mm_FKS2_FKP2_MKS2_MKP2"),
        # BC550C / BC560C TO-92: 1=C 2=B 3=E
        "QPINS": {"NPN": ("1", "2", "3"), "PNP": ("1", "2", "3"), "NPN_P": ("1", "2", "3")},
        "QFP": {},
    },
    "smd": {
        "R": ("Resistor_SMD", "R_0805_2012Metric"),
        "Q": ("Package_TO_SOT_SMD", "SOT-23"),
        "C1": ("Capacitor_SMD", "C_2220_5750Metric"),
        "C2": ("Capacitor_SMD", "C_0805_2012Metric"),
        "C6B": ("Capacitor_SMD", "C_0805_2012Metric"),
        "C9": ("Capacitor_SMD", "C_0805_2012Metric"),
        "C4": ("Capacitor_SMD", "C_1206_3216Metric"),
        "C6": ("Capacitor_SMD", "C_1206_3216Metric"),
        "C3": ("Capacitor_SMD", "CP_Elec_8x10"),
        "C5": ("Capacitor_SMD", "CP_Elec_8x10"),
        "C8": ("Capacitor_SMD", "CP_Elec_10x10"),
        "C7": ("Capacitor_SMD", "CP_Elec_6.3x7.7"),
        "C10": ("Capacitor_SMD", "CP_Elec_5x5.8"),
        # BC850C/BC860C SOT-23: 1=B 2=E 3=C ; BCX56 SOT-89: 1=B 2=C 3=E
        "QPINS": {"NPN": ("3", "1", "2"), "PNP": ("3", "1", "2"), "NPN_P": ("2", "1", "3")},
        "QFP": {"NPN_P": ("Package_TO_SOT_SMD", "SOT-89-3")},
    },
}

SOCKET_FP = "Socket_MillMax_0391_Hole4.1mm"
PEG_FP = "Peg_Hole_3.2mm"


def write_local_lib():
    os.makedirs(LOCAL_LIB, exist_ok=True)
    sock = """(footprint "%s"
	(version 20241229)
	(generator "na522_build")
	(layer "F.Cu")
	(descr "Receptacle for the NAC82 0.8 x 1.7 mm blade pins: Mill-Max 0391-0-15-15-07-27-10-0 (#07 contact, 1.65-2.08 mm), recommended mounting hole 4.09 mm. Socket fitted from the BOTTOM side. Pad 5.6 mm.")
	(tags "Naim NA522 NAC82 socket Mill-Max 0391")
	(attr through_hole)
	(property "Reference" "P?" (at 0 -4.2 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
	(property "Value" "%s" (at 0 4.2 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
	(fp_circle (center 0 0) (end 3.3 0) (stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd"))
	(fp_circle (center 0 0) (end 3.3 0) (stroke (width 0.05) (type solid)) (fill no) (layer "B.CrtYd"))
	(fp_circle (center 0 0) (end 3.05 0) (stroke (width 0.12) (type solid)) (fill no) (layer "F.SilkS"))
	(fp_circle (center 0 0) (end 2.0 0) (stroke (width 0.1) (type solid)) (fill no) (layer "B.Fab"))
	(pad "1" thru_hole circle (at 0 0) (size 5.6 5.6) (drill 4.1) (layers "*.Cu" "*.Mask"))
)
""" % (SOCKET_FP, SOCKET_FP)
    peg = """(footprint "%s"
	(version 20241229)
	(generator "na522_build")
	(layer "F.Cu")
	(descr "Non-plated hole for the NAC82 plastic snap-in retaining peg; 3.2 mm, keep-out 3.6 mm radius")
	(attr exclude_from_pos_files exclude_from_bom)
	(property "Reference" "H?" (at 0 -4.5 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
	(property "Value" "PEG" (at 0 4.5 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
	(fp_circle (center 0 0) (end 3.6 0) (stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd"))
	(fp_circle (center 0 0) (end 3.6 0) (stroke (width 0.05) (type solid)) (fill no) (layer "B.CrtYd"))
	(fp_circle (center 0 0) (end 3.4 0) (stroke (width 0.12) (type solid)) (fill no) (layer "F.SilkS"))
	(pad "" np_thru_hole circle (at 0 0) (size 3.2 3.2) (drill 3.2) (layers "*.Cu" "*.Mask"))
)
""" % PEG_FP
    open(os.path.join(LOCAL_LIB, SOCKET_FP + ".kicad_mod"), "w").write(sock)
    open(os.path.join(LOCAL_LIB, PEG_FP + ".kicad_mod"), "w").write(peg)


def mm(v):
    return pcbnew.FromMM(v)


def to_kicad(x, y):
    """placement frame (Y up, origin bottom-left) -> KiCad page coords (Y down)"""
    return ORIGIN[0] + x, ORIGIN[1] + (BOARD_H - y)


def load_fp(lib, name):
    path = LOCAL_LIB if lib == "NA5xx" else os.path.join(FPLIB, lib + ".pretty")
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise RuntimeError("footprint not found %s:%s" % (lib, name))
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def place_centre(fp, x, y, rot):
    """place so the courtyard/bbox centre lands on (x, y) in placement frame"""
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(pcbnew.VECTOR2I(0, 0))
    bb = fp.GetBoundingBox(False)
    c = bb.GetCenter()
    kx, ky = to_kicad(x, y)
    fp.SetPosition(pcbnew.VECTOR2I(mm(kx) - c.x, mm(ky) - c.y))


def add_line(board, layer, pts, width=0.1):
    for (x1, y1), (x2, y2) in zip(pts[:-1], pts[1:]):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1)))
        s.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
        s.SetLayer(layer)
        s.SetWidth(mm(width))
        board.Add(s)


def add_text(board, text, x, y, size=1.0, layer=pcbnew.F_SilkS, mirror=False, rot=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    kx, ky = to_kicad(x, y)
    t.SetPosition(pcbnew.VECTOR2I(mm(kx), mm(ky)))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(size * 0.15))
    t.SetTextAngleDegrees(rot)
    if mirror:
        t.SetMirrored(True)
    board.Add(t)


def outline_points(sockets):
    """Rectangle 83.5 x 50.5 with a 0.5 mm corner chamfer, plus small 'ears'
    where a socket pad would come closer than 0.4 mm to the edge (P1/P4 sit
    ~2-2.6 mm from the edge on the original, the Mill-Max pad needs 3.2 mm)."""
    W, H = BOARD_W, BOARD_H
    need = 2.8 + 0.6
    ears = {"L": [], "R": [], "B": [], "T": []}
    for name, (x, y) in sockets.items():
        if x < need: ears["L"].append((y, need - x))
        if W - x < need: ears["R"].append((y, need - (W - x)))
        if y < need: ears["B"].append((x, need - y))
        if H - y < need: ears["T"].append((x, need - (H - y)))
    c = 0.5
    pts = [(c, 0)]
    for (x0, d) in sorted(ears["B"]):
        pts += [(x0 - 4, 0), (x0 - 3, -d), (x0 + 3, -d), (x0 + 4, 0)]
    pts += [(W - c, 0), (W, c)]
    for (y0, d) in sorted(ears["R"]):
        pts += [(W, y0 - 4), (W + d, y0 - 3), (W + d, y0 + 3), (W, y0 + 4)]
    pts += [(W, H - c), (W - c, H)]
    for (x0, d) in sorted(ears["T"], reverse=True):
        pts += [(x0 + 4, H), (x0 + 3, H + d), (x0 - 3, H + d), (x0 - 4, H)]
    pts += [(c, H), (0, H - c)]
    for (y0, d) in sorted(ears["L"], reverse=True):
        pts += [(0, y0 + 4), (-d, y0 + 3), (-d, y0 - 3), (0, y0 - 4)]
    pts += [(0, c), (c, 0)]
    return pts, ears


def build(key, hand):
    write_local_lib()
    D = DESIGNS[key]
    vals = D["values"]
    fpd = FP[key]
    place = PLACEMENTS[key]
    W = BOARD_W
    mirror = (hand == "B")

    def P(x, y, rot=0):
        if mirror:
            return W - x, y, (180 - rot) % 360
        return x, y, rot

    outdir = os.path.join(ROOT, DIRS[key], "pcb_%s" % hand)
    os.makedirs(outdir, exist_ok=True)
    base = "na522_%s_%s" % (key, hand)
    pcbpath = os.path.join(outdir, base + ".kicad_pcb")

    board = pcbnew.BOARD()
    board.SetCopperLayerCount(2)
    ds = board.GetDesignSettings()
    nc = ds.m_NetSettings.GetDefaultNetclass()
    clr = 0.3 if key == "tht" else 0.25
    nc.SetClearance(mm(clr)); nc.SetTrackWidth(mm(0.4)); nc.SetViaDiameter(mm(0.8)); nc.SetViaDrill(mm(0.4))
    pwr = pcbnew.NETCLASS("Power")
    pwr.SetClearance(mm(clr)); pwr.SetTrackWidth(mm(0.6)); pwr.SetViaDiameter(mm(0.9)); pwr.SetViaDrill(mm(0.45))
    ds.m_NetSettings.SetNetclass("Power", pwr)
    for n in ("GND", "VCC", "V24"):
        ds.m_NetSettings.SetNetclassPatternAssignment(n, "Power")
    ds.m_MinClearance = mm(0.2)
    ds.m_TrackMinWidth = mm(0.2)
    ds.m_CopperEdgeClearance = mm(0.5)

    nets = {}

    def net(name):
        if name not in nets:
            n = pcbnew.NETINFO_ITEM(board, name)
            board.Add(n)
            nets[name] = n
        return nets[name]

    # ---- components
    for ref, (typ, pins) in TOPOLOGY.items():
        if ref not in place:
            raise RuntimeError("no placement for " + ref)
        if typ in ("NPN", "PNP", "NPN_P"):
            lib, name = fpd["QFP"].get(typ, fpd["Q"])
            padnums = fpd["QPINS"][typ]
            val = {"tht": {"NPN": "BC550C", "PNP": "BC560C", "NPN_P": "BC550C"},
                   "smd": {"NPN": "BC850C", "PNP": "BC860C", "NPN_P": "BCX56-16"}}[key][typ]
        elif typ == "R":
            lib, name = fpd["R"]
            padnums = ("1", "2")
            v = vals.get(ref)
            val = ("0R link" if v == 0 else fmt(v)) if v is not None else "DNF"
        else:
            lib, name = fpd[ref]
            padnums = ("1", "2")
            val = fmt(vals.get(ref), "F")
        fp = load_fp(lib, name)
        fp.SetReference(ref)
        fp.SetValue(val)
        x, y, rot = P(*place[ref])
        place_centre(fp, x, y, rot)
        board.Add(fp)
        for pn, netname in zip(padnums, pins):
            for pad in fp.Pads():
                if pad.GetNumber() == pn:
                    pad.SetNet(net(netname))
        if vals.get(ref, 1) is None:
            fp.SetDNP(True) if hasattr(fp, "SetDNP") else None

    # ---- sockets + peg
    sockets = {}
    for pname, (sx, sy) in SOCKETS_T.items():
        x, y, _ = P(sx, sy)
        sockets[pname] = (x, y)
        fp = load_fp("NA5xx", SOCKET_FP)
        fp.SetReference(pname)
        fp.SetValue("Mill-Max 0391 (%s)" % CONNECTOR_NETS[pname])
        fp.Reference().SetVisible(False)
        place_centre(fp, x, y, 0)
        board.Add(fp)
        for pad in fp.Pads():
            pad.SetNet(net(CONNECTOR_NETS[pname]))
    px, py, _ = P(*PEG_T)
    fp = load_fp("NA5xx", PEG_FP)
    fp.SetReference("H1")
    place_centre(fp, px, py, 0)
    board.Add(fp)

    # ---- outline
    pts, ears = outline_points(sockets)
    add_line(board, pcbnew.Edge_Cuts, [to_kicad(x, y) for x, y in pts], 0.1)

    # ---- silkscreen
    labels = {"P1": "+24V", "P2": "OUT", "P3": "GND", "P4": "IN"}
    for pname, (x, y) in sockets.items():
        dx = 0
        dy = 4.6 if y < BOARD_H - 6 else -4.6
        if pname == "P3":
            dy, dx = 0, (-5.6 if x > BOARD_W / 2 else 5.6)
        add_text(board, labels[pname], x + dx, y + dy, 1.0)
    title = "NA522-compatible MM  %s  board %s" % ("D1 THT" if key == "tht" else "D2 SMD", hand)
    tx0 = 52 if key == "tht" else 36
    tx = tx0 if not mirror else W - tx0
    add_text(board, title, tx, 35.6 if key == "tht" else 48.6, 1.0)
    add_text(board, hand, 4.0 if not mirror else W - 4.0, 47.5 if key == "smd" else 3.0, 2.5)
    add_text(board, "%s rev A  sockets on THIS side - verify pinout before power-up" % hand,
             W / 2, 1.6 if key == "tht" else 2.0, 0.9, layer=pcbnew.B_SilkS, mirror=True)

    # ---- 1 mm no-track keep-out strips along the edges (Freerouting ignores edge clearance)
    kw = 1.0
    for (x0, y0, x1, y1) in ((0, 0, BOARD_W, kw), (0, BOARD_H - kw, BOARD_W, BOARD_H),
                             (0, 0, kw, BOARD_H), (BOARD_W - kw, 0, BOARD_W, BOARD_H)):
        k = pcbnew.ZONE(board)
        k.SetIsRuleArea(True)
        k.SetDoNotAllowTracks(True); k.SetDoNotAllowVias(True)
        k.SetDoNotAllowPads(False); k.SetDoNotAllowFootprints(False)
        k.SetDoNotAllowZoneFills(False) if hasattr(k, "SetDoNotAllowZoneFills") else k.SetDoNotAllowCopperPour(False)
        ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.B_Cu)
        k.SetLayerSet(ls)
        o = k.Outline(); o.NewOutline()
        for (x, y) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            kx, ky = to_kicad(x, y); o.Append(mm(kx), mm(ky))
        board.Add(k)

    pcbnew.SaveBoard(pcbpath, board)
    if os.environ.get("NOROUTE"):
        return pcbpath, outdir, base

    # ---- route with Freerouting
    dsn = os.path.join(outdir, base + ".dsn")
    ses = os.path.join(outdir, base + ".ses")
    if not pcbnew.ExportSpecctraDSN(board, dsn):
        raise RuntimeError("DSN export failed")
    if os.path.exists(ses):
        os.remove(ses)
    log = open(os.path.join(outdir, "freerouting.log"), "w")
    subprocess.run([JAVA, "-jar", FREEROUTING, "-de", dsn, "-do", ses, "-mp", "40", "--gui.enabled=false"],
                   stdout=log, stderr=subprocess.STDOUT, timeout=1800, cwd=outdir)
    log.close()
    if not os.path.exists(ses):
        raise RuntimeError("Freerouting produced no session - see freerouting.log")
    if not pcbnew.ImportSpecctraSES(board, ses):
        raise RuntimeError("SES import failed")

    # ---- GND pours on both layers
    for layer in (pcbnew.B_Cu, pcbnew.F_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(net("GND"))
        z.SetLocalClearance(mm(0.4 if key == "tht" else 0.3))
        z.SetMinThickness(mm(0.3))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(mm(0.4))
        z.SetThermalReliefSpokeWidth(mm(0.5))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        ol = z.Outline()
        ol.NewOutline()
        i_, c_ = 0.6, 1.2
        for x, y in ((c_, i_), (BOARD_W - c_, i_), (BOARD_W - i_, c_), (BOARD_W - i_, BOARD_H - c_),
                     (BOARD_W - c_, BOARD_H - i_), (c_, BOARD_H - i_), (i_, BOARD_H - c_), (i_, c_)):
            kx, ky = to_kicad(x, y)
            ol.Append(mm(kx), mm(ky))
        board.Add(z)
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(pcbpath, board)
    # pads whose thermal relief is starved by tracks -> solid connection, refill
    for it in range(3):
        drc = os.path.join(outdir, "drc_tmp.json")
        subprocess.run([KCLI, "pcb", "drc", "--format", "json", "-o", drc, pcbpath], capture_output=True)
        starved = []
        for v in json.load(open(drc)).get("violations", []):
            if v["type"] == "starved_thermal":
                for i in v["items"]:
                    if "pad" in i["description"]:
                        starved.append(i["description"])
        os.remove(drc)
        if not starved:
            break
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                d = "pad %s [%s] of %s" % (pad.GetNumber(), pad.GetNetname(), fp.GetReference())
                if any(d in st for st in starved):
                    pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        filler.Fill(board.Zones())
        pcbnew.SaveBoard(pcbpath, board)
    for f in (dsn,):
        pass
    return pcbpath, outdir, base


def export(pcbpath, outdir, base):
    rep = {}
    drc = os.path.join(outdir, "drc_report.json")
    subprocess.run([KCLI, "pcb", "drc", "--format", "json", "--schematic-parity", "-o", drc, pcbpath], capture_output=True)
    if not os.path.exists(drc):
        subprocess.run([KCLI, "pcb", "drc", "--format", "json", "-o", drc, pcbpath], capture_output=True)
    try:
        d = json.load(open(drc))
        rep["violations"] = [(v["type"], v["severity"], v["description"]) for v in d.get("violations", [])]
        rep["unconnected"] = len(d.get("unconnected_items", []))
    except Exception as e:
        rep["error"] = str(e)
    g = os.path.join(outdir, "gerbers")
    shutil.rmtree(g, ignore_errors=True)
    os.makedirs(g)
    subprocess.run([KCLI, "pcb", "export", "gerbers", "--layers",
                    "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts",
                    "--subtract-soldermask", "-o", g + "/", pcbpath], capture_output=True)
    subprocess.run([KCLI, "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th",
                    "--generate-map", "--map-format", "pdf", "-o", g + "/", pcbpath], capture_output=True)
    subprocess.run([KCLI, "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
                    "-o", os.path.join(outdir, base + "_pos.csv"), pcbpath], capture_output=True)
    shutil.make_archive(os.path.join(outdir, base + "_gerbers"), "zip", g)
    subprocess.run([KCLI, "pcb", "export", "pdf", "--layers", "F.Cu,F.SilkS,Edge.Cuts,F.Fab", "--mode-single",
                    "-o", os.path.join(outdir, base + "_assembly_top.pdf"), pcbpath], capture_output=True)
    for side in ("top", "bottom"):
        subprocess.run([KCLI, "pcb", "render", "--side", side, "--quality", "high", "--width", "1600", "--height", "1000",
                        "--zoom", "1.0", "-o", os.path.join(outdir, "%s_render_%s.png" % (base, side)), pcbpath],
                       capture_output=True)
    subprocess.run([KCLI, "pcb", "render", "--side", "top", "--perspective", "--rotate", "-45,0,30", "--quality", "high",
                    "--width", "1600", "--height", "1000", "-o", os.path.join(outdir, "%s_render_3d.png" % base), pcbpath],
                   capture_output=True)
    for lay, nm in (("F.Cu,Edge.Cuts", "top_copper"), ("B.Cu,Edge.Cuts", "bottom_copper")):
        subprocess.run([KCLI, "pcb", "export", "svg", "--layers", lay, "--mode-single", "--exclude-drawing-sheet",
                        "--fit-page-to-board", "-o", os.path.join(outdir, "%s_%s.svg" % (base, nm)), pcbpath],
                       capture_output=True)
    json.dump(rep, open(os.path.join(outdir, "drc_summary.json"), "w"), indent=1)
    return rep


if __name__ == "__main__":
    key, hand = sys.argv[1], sys.argv[2]
    only_export = "--export-only" in sys.argv
    if only_export:
        outdir = os.path.join(ROOT, DIRS[key], "pcb_%s" % hand)
        base = "na522_%s_%s" % (key, hand)
        pcbpath = os.path.join(outdir, base + ".kicad_pcb")
    else:
        pcbpath, outdir, base = build(key, hand)
    rep = export(pcbpath, outdir, base)
    from collections import Counter
    print("unconnected:", rep.get("unconnected"), "violations:", Counter((v[0], v[1]) for v in rep.get("violations", [])))
