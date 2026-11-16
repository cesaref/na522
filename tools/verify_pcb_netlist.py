#!/usr/bin/env python3
"""
Independent check that every pad on every generated board is on the net that
tools/circuit.py specifies (catches footprint pin-mapping mistakes, e.g. SOT-23
B/E/C order), and that transistor pads map to the intended C/B/E.
Run with KiCad's python:  $KPY tools/verify_pcb_netlist.py
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pcbnew
from circuit import TOPOLOGY, CONNECTOR_NETS
from build_pcb import FP

ok_all = True
lines = []
for key, dd in (("tht", "design1_tht"), ("smd", "design2_smd")):
    for hand in ("T", "B"):
        path = os.path.join(ROOT, dd, "pcb_%s" % hand, "na522_%s_%s.kicad_pcb" % (key, hand))
        b = pcbnew.LoadBoard(path)
        errs = []
        fps = {f.GetReference(): f for f in b.GetFootprints()}
        for ref, (typ, pins) in TOPOLOGY.items():
            f = fps.get(ref)
            if f is None:
                errs.append("%s missing" % ref)
                continue
            if typ in ("NPN", "PNP", "NPN_P"):
                padnums = FP[key]["QPINS"][typ]
                names = ("C", "B", "E")
            else:
                padnums = ("1", "2")
                names = ("1", "2")
            for pn, net, nm in zip(padnums, pins, names):
                pads = [p for p in f.Pads() if p.GetNumber() == pn]
                got = {p.GetNetname() for p in pads}
                if got != {net}:
                    errs.append("%s pad %s (%s): expected %s got %s" % (ref, pn, nm, net, got))
        for pname, net in CONNECTOR_NETS.items():
            got = {p.GetNetname() for p in fps[pname].Pads()}
            if got != {net}:
                errs.append("%s expected %s got %s" % (pname, net, got))
        # track/zone connectivity
        b.BuildConnectivity()
        unrouted = b.GetConnectivity().GetUnconnectedCount(True)
        lines.append("%s %s: %d footprints checked, %d pad/net errors, %d unrouted" % (key, hand, len(fps), len(errs), unrouted))
        lines += ["   " + e for e in errs]
        ok_all &= (not errs and unrouted == 0)
lines.append("ALL OK" if ok_all else "ERRORS FOUND")
print("\n".join(lines))
open(os.path.join(ROOT, "common", "pcb_netlist_verification.txt"), "w").write("\n".join(lines) + "\n")
