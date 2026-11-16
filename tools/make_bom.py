#!/usr/bin/env python3
"""
Generate BOMs (CSV + Markdown) for both designs from tools/circuit.py, with
manufacturer part numbers and a DC-voltage-vs-rating check for every capacitor
using the simulated operating point (simulation/results.json).
usage: python3 tools/make_bom.py
"""
import csv, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from circuit import TOPOLOGY, DESIGNS, POLARISED, fmt

DIRS = {"tht": "design1_tht", "smd": "design2_smd"}


def vishay_mbb(v):
    if v < 100:
        code = ("%.1f" % v).replace(".", "R")[:4].ljust(4, "0")
    else:
        e = 0
        x = v
        while x >= 1000:
            x /= 10.0
            e += 1
        code = "%03d%d" % (round(x), e)
    return "MBB02070C%sFC100" % code


def tnpw(v):
    if v < 1000:
        s = ("%.4g" % v)
        code = (s.replace(".", "R") + "R")[:4] if "." not in s else s.replace(".", "R")
        if "R" not in code:
            code = s + "R"
        code = code.ljust(4, "0")
    elif v < 1e6:
        k = v / 1e3
        s = "%.4g" % k
        code = s.replace(".", "K") if "." in s else s + "K"
        code = code.ljust(4, "0")
    else:
        code = ("%.4g" % (v / 1e6)).replace(".", "M")
    return "TNPW0805%sBEEA" % code


# rated voltages and parts for capacitors / transistors
PARTS = {
    "tht": {
        "C1": ("Tantalum, dipped radial, 10 uF 35 V 10 %, P=5 mm", "KEMET", "T350E106K035AT", 35,
               "As original (Naim used tantalum). Alt: Vishay 199D106X9035DA1. + to bias node."),
        "C7": ("Tantalum, dipped radial, 10 uF 35 V 10 %, P=5 mm", "KEMET", "T350E106K035AT", 35, "+ to O2 (transistor side)."),
        "C3": ("Al. electrolytic radial 47 uF 50 V, 6.3x11, P=2.5 mm", "Panasonic", "EEU-FR1H470", 50,
               "Original: S.L.C.E. CO31SP axial 47 uF 40 V (obsolete)."),
        "C5": ("Al. electrolytic radial 47 uF 50 V, 6.3x11, P=2.5 mm", "Panasonic", "EEU-FR1H470", 50, "In RIAA feedback leg."),
        "C8": ("Al. electrolytic radial 47 uF 50 V, 6.3x11, P=2.5 mm", "Panasonic", "EEU-FR1H470", 50, "Supply decoupling."),
        "C10": ("Al. electrolytic radial 10 uF 50 V, 5x11, P=2 mm", "Panasonic", "EEU-FR1H100", 50,
                "NOT FITTED in faithful build (optional bias filter, fit together with R26 = 165k and R3 = 165k)."),
        "C2": ("Polypropylene film 470 pF 100 V 5 %, P=5 mm", "WIMA", "FKP2 series", 100,
               "Original: polystyrene (Styroflex). Sets RF filter with R4 and loads the cartridge (~470 pF)."),
        "C4": ("Polypropylene film 22 nF 100 V 2.5-5 %, P=5 mm", "WIMA", "MKP2 series (or FKP2)", 100,
               "RIAA 75 us. Hand-match within 1 % between channels if possible."),
        "C6": ("Polypropylene film 68 nF 100 V 2.5-5 %, P=5 mm, W=4.5", "WIMA", "MKP2 series", 100,
               "RIAA 3180/318 us. Hand-match within 1 % between channels if possible."),
        "C6B": ("Polypropylene film 1 nF 100 V, P=5 mm", "WIMA", "FKP2 series", 100, "NOT FITTED (RIAA trim position)."),
        "C9": ("Polyester film 100 nF 63 V, P=5 mm", "WIMA", "MKS2 series", 63, "NOT FITTED in faithful build (optional HF bypass)."),
        "NPN": ("NPN low-noise, hFE group C, TO-92, pinout C-B-E", "Diotec / CDIL", "BC550C", None,
                "Original used Zetex ZTX384C (E-line). Check pinout against footprint (1=C, 2=B, 3=E)."),
        "NPN_P": ("NPN, hFE group C, TO-92 (Pd ~0.13 W)", "Diotec / CDIL", "BC550C", None,
                  "Follower / current sink (~9.3 mA, ~0.13 W). ZTX450/ZTX651 (E-line, 1 W) are cooler alternatives - check pinout."),
        "PNP": ("PNP low-noise, hFE group C, TO-92, pinout C-B-E", "Diotec / CDIL", "BC560C", None, "Original: Zetex ZTX214C."),
        "R": ("Metal film 0207, 0.4 W, 1 %, 50 ppm/K", "Vishay", None, None, ""),
        "R0": ("Wire link (0.6 mm tinned copper) - or 0R 0207", "-", "wire link", None, "Faithful build: R26 = link, R3 = 330k."),
        "SOCK": ("Receptacle for 0.8 x 1.7 mm blade pin (1.65-2.08 mm #07 contact), gold", "Mill-Max", "0391-0-15-15-07-27-10-0", None,
                 "Fitted from the UNDERSIDE. Test-fit samples on the NAC82 pins before ordering in quantity."),
    },
    "smd": {
        "C1": ("MLCC C0G/NP0 1 uF 50 V 5 %, 2220", "TDK", "C5750C0G1H105J230KA", 50,
               "Non-polar. 0.96 Hz with the 165k bias network. Alt: PPS/PEN film SMD 1 uF >= 25 V."),
        "C2": ("MLCC C0G 470 pF 50 V 5 %, 0805", "Murata", "GRM2165C1H471JA01D", 50, "Cartridge load ~470 pF (as original)."),
        "C4": ("MLCC C0G 22 nF 50 V 5 %, 1206", "Murata", "GRM3195C1H223JA01D", 50, "RIAA 75 us. Alt: Panasonic ECHU (PPS film) 22 nF 2 %."),
        "C6": ("MLCC C0G 68 nF 50 V 5 %, 1206", "TDK", "C3216C0G1H683J160AA", 50, "RIAA 3180/318 us. Alt: Panasonic ECHU (PPS film) 68 nF 2 %."),
        "C6B": ("MLCC C0G 1 nF 50 V 5 %, 0805", "Murata", "GRM2165C1H102JA01D", 50, "NOT FITTED (RIAA trim position)."),
        "C3": ("Al. electrolytic SMD 220 uF 35 V, 8x10.2", "Panasonic", "EEE-FK1V221P", 35, "Stage-1 feedback leg."),
        "C5": ("Al. electrolytic SMD 220 uF 35 V, 8x10.2", "Panasonic", "EEE-FK1V221P", 35, "Stage-2 RIAA feedback leg."),
        "C7": ("Al. electrolytic SMD 47 uF 35 V, 6.3x7.7", "Panasonic", "EEE-FK1V470P", 35, "Output coupling; + to O2."),
        "C8": ("Al. electrolytic SMD 470 uF 35 V, 10x10.2", "Panasonic", "EEE-FK1V471P", 35, "Supply reservoir (5 Hz filter with R25)."),
        "C9": ("MLCC X7R 100 nF 50 V, 0805", "Murata", "GRM21BR71H104KA01L", 50, "HF bypass."),
        "C10": ("Al. electrolytic SMD 10 uF 50 V, 5x5.8", "Panasonic", "EEE-FK1H100P", 50, "Bias-supply filter."),
        "NPN": ("NPN low-noise BC850C, SOT-23 (1=B 2=E 3=C)", "Nexperia", "BC850C,215", None, ""),
        "NPN_P": ("NPN medium power BCX56-16, SOT-89 (1=B 2=C 3=E)", "Nexperia", "BCX56-16,115", None,
                  "Followers / current sinks, ~9.2 mA, ~0.13 W each."),
        "PNP": ("PNP low-noise BC860C, SOT-23 (1=B 2=E 3=C)", "Nexperia", "BC860C,215", None, ""),
        "R": ("Thin film 0805, 0.125 W, 0.1 %, 25 ppm/K", "Vishay", None, None, ""),
        "SOCK": ("Receptacle for 0.8 x 1.7 mm blade pin (1.65-2.08 mm #07 contact), gold", "Mill-Max", "0391-0-15-15-07-27-10-0", None,
                 "Fitted from the UNDERSIDE (through-hole, hand solder). Test-fit samples first."),
    },
}


def node_v(op, n):
    if n == "GND":
        return 0.0
    if n == "IN" or n == "OUT":
        return 0.0
    if n == "B1F" and "B1F" not in op["nodes"]:
        return op["nodes"].get("B1")  # R26 = 0 in faithful build
    return op["nodes"].get(n)


def bom(key):
    vals = DESIGNS[key]["values"]
    P = PARTS[key]
    try:
        res = json.load(open(os.path.join(ROOT, DIRS[key], "simulation", "results.json")))
        op = res["op"]
    except Exception:
        op = None
    rows = []
    for ref, (typ, pins) in TOPOLOGY.items():
        v = vals.get(ref)
        vdc = None
        if typ == "R":
            if v == 0:
                desc, mfr, mpn, rating, note = P.get("R0", P["R"])
                value = "0R"
            else:
                desc, mfr, _, _, note = P["R"]
                mpn = vishay_mbb(v) if key == "tht" else tnpw(v)
                value = fmt(v)
                if ref == "R12":
                    note = "RIAA 75 us - 1 %/50 ppm minimum (original spec)"
                if ref in ("R17", "R21", "R16"):
                    note = "RIAA network"
            fp = "0207 axial P=10.16" if key == "tht" else "0805"
        elif typ == "C":
            desc, mfr, mpn, rating, note = P[ref]
            value = fmt(v, "F") if v is not None else fmt(DESIGNS[key]["values"].get(ref) or 0, "F")
            fp = desc.split(",")[-1].strip()
            if op:
                a, b = node_v(op, pins[0]), node_v(op, pins[1])
                if a is not None and b is not None:
                    vdc = a - b
        else:
            desc, mfr, mpn, rating, note = P[typ]
            value = mpn
            fp = "TO-92" if key == "tht" else ("SOT-89" if typ == "NPN_P" else "SOT-23")
            if op:
                q = op["q"].get(ref)
                if q:
                    note = (note + " " if note else "") + "OP: Ic=%.2f mA, Vce=%.1f V, Pd=%.0f mW." % (abs(q["ic"]) * 1e3, abs(q["vce"]), q["pd"] * 1e3)
        dnf = (v is None and typ in ("R", "C"))
        if typ == "C" and v is None:
            # value for the DNF position (suggested)
            value = {"C6B": "1nF", "C9": "100nF", "C10": "10uF"}.get(ref, "")
        chk = ""
        if vdc is not None and rating:
            pol = ref in POLARISED
            chk = "Vdc=%.1f V (rated %d V, %.0f %%)%s" % (vdc, rating, 100 * abs(vdc) / rating,
                                                          " REVERSE BIAS!" if pol and vdc < -0.3 else "")
        rows.append(dict(ref=ref, value=value, fit="DNF" if dnf else "fit", description=desc, footprint=fp,
                         manufacturer=mfr, mpn=mpn, vcheck=chk, notes=note))
    for p in ("P1", "P2", "P3", "P4"):
        desc, mfr, mpn, rating, note = P["SOCK"]
        rows.append(dict(ref=p, value="socket", fit="fit", description=desc, footprint="4.1 mm hole, 5.6 mm pad",
                         manufacturer=mfr, mpn=mpn, vcheck="", notes=note))
    out = os.path.join(ROOT, DIRS[key], "bom")
    os.makedirs(out, exist_ok=True)
    fields = ["ref", "value", "fit", "description", "footprint", "manufacturer", "mpn", "vcheck", "notes"]
    with open(os.path.join(out, "na522_%s_bom_per_ref.csv" % key), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    # grouped
    groups = {}
    for r in rows:
        k = (r["fit"], r["value"], r["mpn"], r["description"])
        groups.setdefault(k, []).append(r["ref"])
    with open(os.path.join(out, "na522_%s_bom_grouped.csv" % key), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["qty_per_board", "qty_per_pair", "refs", "value", "fit", "description", "manufacturer", "mpn"])
        for (fit, value, mpn, desc), refs in sorted(groups.items(), key=lambda x: (x[0][0] != "fit", x[1][0])):
            mfr = next(r["manufacturer"] for r in rows if r["ref"] == refs[0])
            n = len(refs) if fit == "fit" else 0
            w.writerow([n, 2 * n, " ".join(refs), value, fit, desc, mfr, mpn])
    # markdown
    L = ["# Bill of materials - %s" % DESIGNS[key]["name"], "",
         "Quantities are per board; a stereo pair is one **T** and one **B** board (same BOM).",
         "Generated by `tools/make_bom.py` from `tools/circuit.py`; DC voltages are from the simulated operating point.", "",
         "| Ref | Value | Fit | Description | Manufacturer | MPN | DC check | Notes |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (r["ref"], r["value"], r["fit"], r["description"], r["manufacturer"],
                                                             r["mpn"], r["vcheck"], r["notes"]))
    alt = DESIGNS[key].get("alt_values", {})
    for name, av in alt.items():
        diffs = ["%s = %s" % (k, fmt(av[k]) if TOPOLOGY[k][0] == "R" else fmt(av[k], "F")) for k in av if av[k] != vals.get(k)]
        L += ["", "**Value option '%s'** (see simulation/RESULTS.md): change %s." % (name, ", ".join(diffs))]
    L += ["", "MPNs for passives are given as examples that meet the specification; check stock/ordering codes. "
          "Items marked *series* need the ordering code chosen for the stated value/voltage/pitch."]
    open(os.path.join(out, "BOM.md"), "w").write("\n".join(L) + "\n")
    print(key, len(rows), "lines")


if __name__ == "__main__":
    bom("tht")
    bom("smd")
