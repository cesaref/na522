#!/usr/bin/env python3
"""
SPICE-in-the-loop optimisation of the stage-2 RIAA network (R21, R17, C6 trim).

The stage-2 open-loop gain of the Naim topology is modest (loop gain of only a
few at 20 Hz), so the LF part of the RIAA curve depends on the real transistor
gain; an ideal-op-amp calculation is NOT adequate (it predicts +2.7 dB at 20 Hz
for the traced values whereas the transistor-level circuit gives ~+0.5 dB).

usage: python3 tools/optimise_riaa.py tht|smd
Writes the ranking to work/optimise_<key>.txt.
"""
import os, sys, itertools, subprocess, tempfile, shutil
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import simulate as S
from circuit import DESIGNS

E96 = [1.00, 1.02, 1.05, 1.07, 1.10, 1.13, 1.15, 1.18, 1.21, 1.24, 1.27, 1.30, 1.33, 1.37, 1.40, 1.43, 1.47, 1.50, 1.54,
       1.58, 1.62, 1.65, 1.69, 1.74, 1.78, 1.82, 1.87, 1.91, 1.96, 2.00, 2.05, 2.10, 2.15, 2.21, 2.26, 2.32, 2.37, 2.43,
       2.49, 2.55, 2.61, 2.67, 2.74, 2.80, 2.87, 2.94, 3.01, 3.09, 3.16, 3.24, 3.32, 3.40, 3.48, 3.57, 3.65, 3.74, 3.83,
       3.92, 4.02, 4.12, 4.22, 4.32, 4.42, 4.53, 4.64, 4.75, 4.87, 4.99, 5.11, 5.23, 5.36, 5.49, 5.62, 5.76, 5.90, 6.04,
       6.19, 6.34, 6.49, 6.65, 6.81, 6.98, 7.15, 7.32, 7.50, 7.68, 7.87, 8.06, 8.26, 8.45, 8.66, 8.87, 9.09, 9.31, 9.53, 9.76]


def evaluate(key, vals, tmp, bf_scale=1.0):
    net = S.build(key, vals, extra=".control\nac dec 25 20 20k\nlet mag=abs(v(out))\nwrdata o.txt mag\n.endc\n")
    net = net.replace(".include models.lib", ".include m.lib")
    with open(os.path.join(tmp, "m.lib"), "w") as f:
        f.write(S.models_text(bf_scale))
    with open(os.path.join(tmp, "o.cir"), "w") as f:
        f.write(net)
    subprocess.run(["ngspice", "-b", "o.cir"], cwd=tmp, capture_output=True)
    d = np.loadtxt(os.path.join(tmp, "o.txt"))
    dev, g = S.riaa_dev(d[:, 0], d[:, 1])
    return float(np.max(np.abs(dev))), dev, d[:, 0], 20 * np.log10(g)


def main():
    key = sys.argv[1]
    base = DESIGNS[key]["values"]
    tmp = tempfile.mkdtemp()
    res = []
    r21s = [x * 1e4 for x in E96 if 5.0 <= x <= 9.9]
    trims = [None, 1e-9, 2.2e-9, 3.3e-9, 4.7e-9]
    for r21, r17, trim in itertools.product(r21s, (4.7e3, 4.75e3), trims):
        v = dict(base, R21=r21, R17=r17, C6B=trim)
        m, dev, f, g = evaluate(key, v, tmp)
        res.append((m, r21, r17, trim, g))
    res.sort()
    lines = ["%.3f dB  R21=%g R17=%g C6B=%s  gain1k=%.2f dB" % (m, a, b, c, g) for m, a, b, c, g in res[:15]]
    best = res[0]
    v = dict(base, R21=best[1], R17=best[2], C6B=best[3])
    lines.append("\nhFE sensitivity of best (BF x0.7 / x1.0 / x1.4):")
    for s in (0.7, 1.0, 1.4):
        m, dev, f, g = evaluate(key, v, tmp, s)
        lines.append("  BF x%.1f: max dev %.3f dB, dev@20Hz %+.3f, gain1k %.2f dB" % (s, m, dev[0], g))
    lines.append("\nTraced values for comparison:")
    for s in (0.7, 1.0, 1.4):
        m, dev, f, g = evaluate(key, dict(base, R21=82e3, R17=4.7e3, C6B=None), tmp, s)
        lines.append("  BF x%.1f: max dev %.3f dB, dev@20Hz %+.3f, gain1k %.2f dB" % (s, m, dev[0], g))
    out = "\n".join(lines)
    print(out)
    os.makedirs(os.path.join(S.ROOT, "work"), exist_ok=True)
    open(os.path.join(S.ROOT, "work", "optimise_%s.txt" % key), "w").write(out)
    shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
