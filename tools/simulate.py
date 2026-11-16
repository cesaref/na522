#!/usr/bin/env python3
"""
Run the full ngspice characterisation for one design.

usage: python3 tools/simulate.py tht|smd [--mc N]

Outputs (in <design_dir>/simulation/):
  netlists/*.cir     every netlist actually simulated (re-runnable with `ngspice -b`)
  models.lib         transistor models used
  *.png              plots
  results.json       all numbers
  RESULTS.md         human-readable summary
"""
import json, math, os, re, shutil, subprocess, sys, random
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from circuit import TOPOLOGY, DESIGNS, QMODELS, fmt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRS = {"tht": "design1_tht", "smd": "design2_smd"}
RLOAD = 47e3          # assumed load presented by the NAC82 selector (unverified)
CART_R, CART_L = 1000.0, 0.5   # representative MM cartridge (e.g. 2M Red ~1.3k/700mH)


# ---------------------------------------------------------------- netlists
def build(key, vals, src="ac", rs=0.0, ls=0.0, v24="DC 24", src_spec="DC 0 AC 1",
          rload=RLOAD, extra="", title=None, temp=None, ic_out=False):
    qm = QMODELS[key]
    L = ["* %s" % (title or DESIGNS[key]["name"]),
         ".include models.lib",
         "V24 V24 0 %s" % v24]
    if src == "ac":
        if rs > 0 or ls > 0:
            L.append("VS SRC 0 %s" % src_spec)
            L.append("RS SRC SRCL %g" % max(rs, 1e-3))
            if ls > 0:
                L.append("LS SRCL IN %g" % ls)
            else:
                L.append("RSX SRCL IN 1e-3")
        else:
            L.append("VS IN 0 %s" % src_spec)
    elif src == "open":
        pass
    elif src == "short":
        L.append("VS IN 0 DC 0")
    for ref, (typ, pins) in TOPOLOGY.items():
        v = vals.get(ref)
        if v is None and typ in ("R", "C"):
            continue
        n = [("0" if p == "GND" else p) for p in pins]
        if typ == "R":
            L.append("%s %s %s %g" % (ref, n[0], n[1], max(v, 1e-3)))
        elif typ == "C":
            L.append("%s %s %s %g" % (ref, n[0], n[1], v))
        else:
            L.append("%s %s %s %s %s" % (ref, n[0], n[1], n[2], qm[typ]))
    if rload:
        L.append("RLOAD OUT 0 %g" % rload)
    if temp is not None:
        L.append(".temp %g" % temp)
    L.append(".options savecurrents reltol=1e-5 vntol=1e-8 abstol=1e-14")
    L.append(extra)
    L.append(".end")
    return "\n".join(L) + "\n"


def run(net, name, simdir):
    nd = os.path.join(simdir, "netlists")
    os.makedirs(nd, exist_ok=True)
    p = os.path.join(nd, name + ".cir")
    with open(p, "w") as f:
        f.write(net)
    r = subprocess.run(["ngspice", "-b", name + ".cir"], cwd=nd, capture_output=True, text=True, timeout=600)
    out = r.stdout + r.stderr
    if "error" in out.lower() and "no error" not in out.lower():
        errs = [l for l in out.splitlines() if "rror" in l]
        if errs:
            print("ngspice warnings/errors in", name, errs[:5])
    return out, nd


def readcols(path):
    d = np.loadtxt(path)
    return d


def models_text(bf_scale=1.0, bf_scales=None):
    """models.lib with BF scaled (hFE spread studies). bf_scales: dict model->scale"""
    txt = open(os.path.join(ROOT, "tools", "models.lib")).read()
    out = []
    cur = None
    for line in txt.splitlines():
        m = re.match(r"\.model\s+(\S+)", line, re.I)
        if m:
            cur = m.group(1)
        sc = (bf_scales or {}).get(cur, bf_scale)
        line = re.sub(r"\bBF=([0-9.eE+-]+)", lambda mm: "BF=%g" % (float(mm.group(1)) * sc), line)
        out.append(line)
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- analyses
NODES = ["V24", "VCC", "B1", "B1A", "E1", "N1", "E2", "N2", "O1", "Y1", "Z1", "B6", "E6",
         "N6", "E7", "N7", "O2", "Y2", "Z2", "F2", "OUT", "B3", "B8", "C3P", "C5P"]
QS = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8", "Q9", "Q10"]


def op_point(key, vals, simdir, temp=27, tag="op"):
    ctl = ".control\nop\n"
    for n in NODES:
        ctl += "echo NODE %s $&v(%s)\n" % (n, n)
    for q in QS:
        ctl += "echo QIC %s $&@%s[ic]\necho QIB %s $&@%s[ib]\n" % (q, q.lower(), q, q.lower())
    ctl += "echo ISUP $&i(v24)\n.endc\n"
    out, _ = run(build(key, vals, src="short", extra=ctl, temp=temp), "%s_%s" % (tag, key), simdir)
    res = {"nodes": {}, "q": {}}
    for l in out.splitlines():
        t = l.split()
        if len(t) == 3 and t[0] == "NODE":
            res["nodes"][t[1]] = float(t[2])
        elif len(t) == 3 and t[0] in ("QIC", "QIB"):
            res["q"].setdefault(t[1], {})[t[0][1:].lower()] = float(t[2])
        elif len(t) == 2 and t[0] == "ISUP":
            res["isupply"] = -float(t[1])
    V = dict(res["nodes"]); V["GND"] = 0.0
    for q in QS:
        typ, (c, b, e) = TOPOLOGY[q]
        vce = V[c] - V[e]
        ic = res["q"][q]["ic"]
        res["q"][q].update(vce=vce, vbe=V[b] - V[e], pd=abs(vce * ic))
    return res


def ac_resp(key, vals, simdir, tag="ac", fstart=1, fstop=200e3, ppd=50):
    ctl = (".control\nac dec %d %g %g\nlet mag=abs(v(out))\nlet ph=cph(v(out))\n"
           "let zin=abs(v(in)/(-i(vs)))\nlet zinph=cph(v(in)/(-i(vs)))\n"
           "wrdata %s.txt mag ph zin zinph\n.endc\n" % (ppd, fstart, fstop, tag))
    out, nd = run(build(key, vals, extra=ctl), "%s_%s" % (tag, key), simdir)
    d = readcols(os.path.join(nd, tag + ".txt"))
    return {"f": d[:, 0], "mag": d[:, 1], "ph": d[:, 3], "zin": d[:, 5], "zinph": d[:, 7]}


def riaa(f):
    s = 2j * np.pi * np.asarray(f)
    return (1 + s * 318e-6) / ((1 + s * 3180e-6) * (1 + s * 75e-6))


def riaa_dev(f, mag):
    g1k = np.interp(1000, f, mag)
    r = abs(riaa(f)) / abs(riaa([1000.0]))[0]
    return 20 * np.log10(mag / g1k) - 20 * np.log10(r), g1k


def zout(key, vals, simdir):
    ctl = (".control\nac dec 20 10 100k\nlet z=abs(v(out))\nwrdata zout.txt z\n.endc\n")
    net = build(key, vals, src="short", rload=None, extra="IT 0 OUT DC 0 AC 1\n" + ctl)
    out, nd = run(net, "zout_%s" % key, simdir)
    d = readcols(os.path.join(nd, "zout.txt"))
    return {"f": d[:, 0], "z": d[:, 1]}


def psrr(key, vals, simdir):
    ctl = ".control\nac dec 20 10 100k\nlet g=abs(v(out))\nwrdata psrr.txt g\n.endc\n"
    net = build(key, vals, src="short", v24="DC 24 AC 1", extra=ctl)
    out, nd = run(net, "psrr_%s" % key, simdir)
    d = readcols(os.path.join(nd, "psrr.txt"))
    return {"f": d[:, 0], "g": d[:, 1]}


def noise(key, vals, simdir, rs, ls, tag):
    ctl = (".control\nnoise v(out) vs dec 50 10 100k\nsetplot noise1\n"
           "wrdata %s.txt onoise_spectrum inoise_spectrum\n.endc\n" % tag)
    out, nd = run(build(key, vals, rs=rs, ls=ls, extra=ctl), "%s_%s" % (tag, key), simdir)
    d = readcols(os.path.join(nd, tag + ".txt"))
    return {"f": d[:, 0], "on": d[:, 1], "inn": d[:, 3]}


def a_weight(f):
    f = np.asarray(f)
    ra = (12194 ** 2 * f ** 4) / ((f ** 2 + 20.6 ** 2) * np.sqrt((f ** 2 + 107.7 ** 2) * (f ** 2 + 737.9 ** 2)) * (f ** 2 + 12194 ** 2))
    return ra / ((12194 ** 2 * 1000 ** 4) / ((1000 ** 2 + 20.6 ** 2) * np.sqrt((1000 ** 2 + 107.7 ** 2) * (1000 ** 2 + 737.9 ** 2)) * (1000 ** 2 + 12194 ** 2)))


def integ(f, psd2):
    m = (f >= 20) & (f <= 20000)
    return math.sqrt(np.trapezoid(psd2[m], f[m]))


def thd(key, vals, simdir, freq, amp_rms, tag):
    """THD+harmonics 2..10 by FFT over the last NP periods after removing the
    linear trend (slow LF settling of the coupling/feedback capacitors would
    otherwise pollute a short Fourier window)."""
    amp = amp_rms * math.sqrt(2)
    per = 1.0 / freq
    NP = 8
    tsettle = per * (40 if freq >= 500 else 12)
    tstop = tsettle + NP * per
    npts = 256 * NP
    step = NP * per / npts
    ctl = (".control\ntran %g %g %g %g\nlinearize v(out)\nwrdata %s.txt v(out)\n.endc\n" % (step, tstop, tsettle, step / 2, tag))
    # sine faded in over ~5 cycles: negligible DC injection into the LF time constants
    net = build(key, vals, src="short", extra=ctl).replace(
        "VS IN 0 DC 0", "BVS IN 0 V=%g*sin(6.283185307*%g*time)*(1-exp(-time/%g))" % (amp, freq, 5 * per))
    out, nd = run(net, tag, simdir)
    d = np.loadtxt(os.path.join(nd, tag + ".txt"))
    t, y = d[:, 0], d[:, 1]
    tt = np.linspace(tsettle, tstop, npts, endpoint=False)
    yy = np.interp(tt, t, y)
    yy = yy - np.polyval(np.polyfit(tt, yy, 1), tt)
    Y = np.abs(np.fft.rfft(yy * np.hanning(npts)))
    k = NP
    def bin_amp(h):
        i = h * k
        return math.sqrt(sum(Y[j] ** 2 for j in range(i - 2, i + 3) if 0 <= j < len(Y)))
    f1 = bin_amp(1)
    harm = math.sqrt(sum(bin_amp(h) ** 2 for h in range(2, 11) if h * k + 2 < len(Y)))
    fund = float(np.sqrt(np.mean(yy ** 2)))  # output rms (dominated by the fundamental)
    os.remove(os.path.join(nd, tag + ".txt"))
    return 100.0 * harm / f1, fund


def overload(key, vals, simdir, freq, lo, hi, lim=1.0):
    """bisection on input amplitude for THD = lim %"""
    for i in range(9):
        mid = math.sqrt(lo * hi)
        t, _ = thd(key, vals, simdir, freq, mid, "ovl_%s_%d" % (key, int(freq)))
        if t > lim:
            hi = mid
        else:
            lo = mid
    return math.sqrt(lo * hi)


def powerup(key, vals, simdir):
    ctl = ".control\ntran 1m 15 0 1m uic\nwrdata pwr.txt v(out) v(o2) v(o1)\n.endc\n"
    net = build(key, vals, src="short", v24="PWL(0 0 20m 24)", extra=ctl)
    out, nd = run(net, "powerup_%s" % key, simdir)
    d = readcols(os.path.join(nd, "pwr.txt"))
    return {"t": d[:, 0], "out": d[:, 1], "o2": d[:, 3], "o1": d[:, 5]}


TOL = {"tht": {"R": 0.01, "C": 0.05, "Ce": 0.20}, "smd": {"R": 0.001, "C": 0.02, "Ce": 0.20}}


def montecarlo(key, vals, simdir, n):
    random.seed(1)
    fs = None
    devs = []
    gains = []
    for i in range(n):
        v = {}
        for ref, val in vals.items():
            if val is None:
                v[ref] = None
                continue
            t = TOPOLOGY[ref][0]
            if t == "R":
                tol = TOL[key]["R"]
            elif ref in ("C1", "C3", "C5", "C7", "C8"):
                tol = TOL[key]["Ce"]
            else:
                tol = TOL[key]["C"]
            v[ref] = val * (1 + random.uniform(-tol, tol))
        ctl = ".control\nac dec 20 10 50k\nlet mag=abs(v(out))\nwrdata mc.txt mag\n.endc\n"
        bfs = {m: random.uniform(0.75, 1.4) for m in ("BC550C", "BC850C", "BC560C", "BC860C", "BCX56")}
        with open(os.path.join(simdir, "netlists", "models_mc.lib"), "w") as fm:
            fm.write(models_text(bf_scales=bfs))
        out, nd = run(build(key, v, extra=ctl).replace(".include models.lib", ".include models_mc.lib"), "mc_%s" % key, simdir)
        d = readcols(os.path.join(nd, "mc.txt"))
        fs = d[:, 0]
        dv, g = riaa_dev(fs, d[:, 1])
        devs.append(dv)
        gains.append(20 * math.log10(g))
    os.remove(os.path.join(simdir, "netlists", "mc_%s.cir" % key))
    os.remove(os.path.join(simdir, "netlists", "models_mc.lib"))
    return fs, np.array(devs), np.array(gains)


# ---------------------------------------------------------------- main
def main():
    key = sys.argv[1]
    nmc = int(sys.argv[sys.argv.index("--mc") + 1]) if "--mc" in sys.argv else 100
    D = DESIGNS[key]
    vals = D["values"]
    simdir = os.path.join(ROOT, DIRS[key], "simulation")
    os.makedirs(simdir, exist_ok=True)
    os.makedirs(os.path.join(simdir, "netlists"), exist_ok=True)
    shutil.copy(os.path.join(ROOT, "tools", "models.lib"), os.path.join(simdir, "netlists", "models.lib"))
    R = {"design": D["name"], "assumptions": {"load_ohm": RLOAD, "cartridge": "%g ohm + %g H" % (CART_R, CART_L),
                                              "supply": "24 V ideal at P1 (through on-card R25)"}}

    # operating point vs temperature
    R["op"] = op_point(key, vals, simdir)
    R["op_temp"] = {}
    for T in (0, 60):
        o = op_point(key, vals, simdir, temp=T, tag="op_t%d" % T)
        R["op_temp"][T] = {"O1": o["nodes"]["O1"], "O2": o["nodes"]["O2"], "isupply": o["isupply"]}

    # frequency response, primary and alternative value sets
    sets = {"primary": vals}
    sets.update(D.get("alt_values", {}))
    R["ac"] = {}
    acs = {}
    for name, vs in sets.items():
        a = ac_resp(key, vs, simdir, tag="ac_" + name)
        dv, g1k = riaa_dev(a["f"], a["mag"])
        acs[name] = (a, dv)
        m = (a["f"] >= 20) & (a["f"] <= 20000)
        pts = {}
        for fq in (10, 20, 50, 100, 1000, 10000, 20000, 50000):
            pts[str(fq)] = {"gain_db": float(20 * np.log10(np.interp(fq, a["f"], a["mag"]))),
                            "riaa_dev_db": float(np.interp(fq, a["f"], dv))}
        R["ac"][name] = {"gain_1k_db": float(20 * np.log10(g1k)), "gain_1k": float(g1k),
                         "riaa_dev_max_20_20k_db": float(np.max(np.abs(dv[m]))),
                         "riaa_dev_max_50_20k_db": float(np.max(np.abs(dv[(a["f"] >= 50) & (a["f"] <= 20000)]))),
                         "points": pts,
                         "zin_1k_ohm": float(np.interp(1000, a["f"], a["zin"])),
                         "zin_20k_ohm": float(np.interp(20000, a["f"], a["zin"]))}
    a, dv = acs["primary"]

    zo = zout(key, vals, simdir)
    R["zout_1k_ohm"] = float(np.interp(1000, zo["f"], zo["z"]))
    R["zout_20Hz_ohm"] = float(np.interp(20, zo["f"], zo["z"]))
    ps = psrr(key, vals, simdir)
    R["psrr_db"] = {str(fq): float(20 * np.log10(np.interp(fq, ps["f"], ps["g"]))) for fq in (100, 1000, 10000)}

    # noise
    g1k = R["ac"]["primary"]["gain_1k"]
    R["noise"] = {}
    nz = {}
    for tag, rs, ls in (("noise_short", 1e-3, 0), ("noise_cart", CART_R, CART_L)):
        n = noise(key, vals, simdir, rs, ls, tag)
        nz[tag] = n
        aw = a_weight(n["f"])
        vn = integ(n["f"], n["on"] ** 2)
        vna = integ(n["f"], (n["on"] * aw) ** 2)
        sig = 5e-3 * g1k
        R["noise"][tag] = {"out_uV_20_20k": vn * 1e6, "out_uV_A": vna * 1e6,
                           "snr_re5mV_unwtd_db": 20 * math.log10(sig / vn),
                           "snr_re5mV_A_db": 20 * math.log10(sig / vna),
                           "ein_1k_nV_rtHz": float(np.interp(1000, n["f"], n["inn"])) * 1e9}

    # distortion
    R["thd"] = {}
    levels = [2e-3, 5e-3, 10e-3, 20e-3, 50e-3]
    for lv in levels:
        t, fo = thd(key, vals, simdir, 1000, lv, "thd_%s" % key)
        R["thd"]["%gmV" % (lv * 1e3)] = {"thd_pct": t, "vout_rms": fo}
    t, fo = thd(key, vals, simdir, 20000, 20e-3, "thd20k_%s" % key)
    R["thd"]["20kHz_20mV"] = {"thd_pct": t, "vout_rms": fo}
    # overload (1 % THD)
    R["overload_mV_rms"] = {}
    for fq, lo, hi in ((1000, 20e-3, 1.0), (20000, 50e-3, 3.0), (20, 2e-3, 0.3)):
        ov = overload(key, vals, simdir, fq, lo, hi)
        R["overload_mV_rms"][str(fq)] = ov * 1e3
    R["overload_margin_db_re_5mV_1k"] = 20 * math.log10(R["overload_mV_rms"]["1000"] / 5.0)
    for f_ in os.listdir(os.path.join(simdir, "netlists")):
        if f_.startswith("ovl_"):
            os.remove(os.path.join(simdir, "netlists", f_))

    pu = powerup(key, vals, simdir)
    R["powerup"] = {"out_peak_V": float(np.max(np.abs(pu["out"]))),
                    "out_at_15s_mV": float(pu["out"][-1] * 1e3),
                    "o2_at_15s_V": float(pu["o2"][-1]),
                    "settle_time_s_out_within_50mV": float(pu["t"][np.where(np.abs(pu["out"]) > 0.05)[0][-1]]) if np.any(np.abs(pu["out"]) > 0.05) else 0.0}

    fs, devs, gains = montecarlo(key, vals, simdir, nmc)
    m = (fs >= 20) & (fs <= 20000)
    R["montecarlo"] = {"runs": nmc, "tolerances": TOL[key],
                       "riaa_dev_p95_abs_db": float(np.percentile(np.max(np.abs(devs[:, m]), axis=1), 95)),
                       "gain_1k_db_min": float(gains.min()), "gain_1k_db_max": float(gains.max())}

    with open(os.path.join(simdir, "results.json"), "w") as f:
        json.dump(R, f, indent=1, default=float)

    # ------------------------------------------------------------ plots
    fig, ax = plt.subplots(2, 1, figsize=(9, 8), sharex=True)
    for name, (aa, dd) in acs.items():
        ax[0].semilogx(aa["f"], 20 * np.log10(aa["mag"]), label=name)
        ax[1].semilogx(aa["f"], dd, label=name)
    ff = a["f"]
    ax[0].semilogx(ff, 20 * np.log10(abs(riaa(ff)) / abs(riaa([1000.0]))[0] * g1k), "k:", label="ideal RIAA (same 1 kHz gain)")
    ax[0].set_ylabel("Gain (dB)"); ax[0].grid(True, which="both", alpha=.3); ax[0].legend()
    ax[0].set_title(D["name"] + " - frequency response (load %gk)" % (RLOAD / 1e3))
    lo, hi = np.percentile(devs, 2.5, axis=0), np.percentile(devs, 97.5, axis=0)
    ax[1].fill_between(fs, lo, hi, color="C0", alpha=.2, label="Monte Carlo 95%% (%d runs)" % nmc)
    ax[1].set_ylabel("Deviation from RIAA (dB, re 1 kHz)"); ax[1].set_xlabel("Hz")
    ax[1].set_ylim(-3, 3.5); ax[1].grid(True, which="both", alpha=.3); ax[1].legend()
    ax[1].set_xlim(5, 100e3)
    fig.tight_layout(); fig.savefig(os.path.join(simdir, "frequency_response.png"), dpi=120); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    for tag, n in nz.items():
        ax.loglog(n["f"], n["inn"] * 1e9, label="input-referred, " + tag)
    ax.set_ylabel("nV/rtHz"); ax.set_xlabel("Hz"); ax.grid(True, which="both", alpha=.3); ax.legend()
    ax.set_title(D["name"] + " - input-referred noise density")
    fig.tight_layout(); fig.savefig(os.path.join(simdir, "noise.png"), dpi=120); plt.close(fig)

    fig, ax = plt.subplots(1, 3, figsize=(15, 4.5))
    ax[0].semilogx(a["f"], a["zin"] / 1e3); ax[0].set_title("Input impedance |Z| (kohm)"); ax[0].grid(True, which="both", alpha=.3)
    ax[1].loglog(zo["f"], zo["z"]); ax[1].set_title("Output impedance |Z| (ohm)"); ax[1].grid(True, which="both", alpha=.3)
    ax[2].semilogx(ps["f"], 20 * np.log10(ps["g"])); ax[2].set_title("Supply (P1) -> OUT gain (dB)"); ax[2].grid(True, which="both", alpha=.3)
    for x in ax: x.set_xlabel("Hz")
    fig.tight_layout(); fig.savefig(os.path.join(simdir, "impedances_psrr.png"), dpi=120); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(pu["t"], pu["out"], label="OUT (card pin P2)")
    ax.plot(pu["t"], pu["o2"], label="O2 (before C7)")
    ax.plot(pu["t"], pu["o1"], label="O1")
    ax.set_xlabel("s"); ax.set_ylabel("V"); ax.grid(True, alpha=.3); ax.legend()
    ax.set_title(D["name"] + " - power-up (24 V ramp in 20 ms, %gk load)" % (RLOAD / 1e3))
    fig.tight_layout(); fig.savefig(os.path.join(simdir, "powerup.png"), dpi=120); plt.close(fig)

    write_md(key, R, simdir)
    print(json.dumps({k: R[k] for k in ("ac", "noise", "thd", "overload_mV_rms", "montecarlo", "powerup")}, indent=1, default=float)[:4000])


def write_md(key, R, simdir):
    op = R["op"]
    L = ["# Simulation results - %s" % R["design"], "",
         "Generated by `tools/simulate.py %s` (ngspice). All netlists are in `netlists/` and can be re-run with "
         "`ngspice -b <file>.cir` from that directory." % key, "",
         "Assumptions: load %g kohm on OUT (NAC82 selector input impedance not yet measured), cartridge %s, "
         "ideal 24 V at P1. Transistor models are representative, see `netlists/models.lib`." %
         (R["assumptions"]["load_ohm"] / 1e3, R["assumptions"]["cartridge"]), "",
         "## Headline figures", "", "| Parameter | Value |", "|---|---|"]
    p = R["ac"]["primary"]
    L += ["| Gain @ 1 kHz | %.2f dB (x%.1f) |" % (p["gain_1k_db"], p["gain_1k"]),
          "| RIAA deviation 20 Hz-20 kHz (max abs) | %.2f dB |" % p["riaa_dev_max_20_20k_db"],
          "| RIAA deviation 50 Hz-20 kHz (max abs) | %.2f dB |" % p["riaa_dev_max_50_20k_db"],
          "| Input impedance @1 kHz / 20 kHz | %.1f k / %.1f k |" % (p["zin_1k_ohm"] / 1e3, p["zin_20k_ohm"] / 1e3),
          "| Output impedance @1 kHz | %.1f ohm |" % R["zout_1k_ohm"],
          "| Supply current | %.1f mA |" % (op["isupply"] * 1e3),
          "| SNR re 5 mV @1 kHz, A-wtd, 1k+500mH source | %.1f dB |" % R["noise"]["noise_cart"]["snr_re5mV_A_db"],
          "| SNR re 5 mV @1 kHz, A-wtd, shorted input | %.1f dB |" % R["noise"]["noise_short"]["snr_re5mV_A_db"],
          "| EIN @1 kHz, shorted input | %.2f nV/rtHz |" % R["noise"]["noise_short"]["ein_1k_nV_rtHz"],
          "| THD @1 kHz, 5 mV in | %.4f %% |" % R["thd"]["5mV"]["thd_pct"],
          "| THD @1 kHz, 50 mV in | %.4f %% |" % R["thd"]["50mV"]["thd_pct"],
          "| THD @20 kHz, 20 mV in | %.4f %% |" % R["thd"]["20kHz_20mV"]["thd_pct"],
          "| Overload (1 %% THD) @20 Hz / 1 kHz / 20 kHz | %.1f / %.0f / %.0f mV rms |" % (
              R["overload_mV_rms"]["20"], R["overload_mV_rms"]["1000"], R["overload_mV_rms"]["20000"]),
          "| Overload margin re 5 mV @1 kHz | %.1f dB |" % R["overload_margin_db_re_5mV_1k"],
          "| PSRR (P1 -> OUT) 100 Hz / 1 kHz / 10 kHz | %.1f / %.1f / %.1f dB |" % tuple(R["psrr_db"][k] for k in ("100", "1000", "10000")),
          "| Power-up: peak at OUT (47k load) / settles within 50 mV after | %.2f V / %.1f s |" % (R["powerup"]["out_peak_V"], R["powerup"]["settle_time_s_out_within_50mV"]),
          "| Monte Carlo (%d runs, R %.1f%%, C %.0f%%, electrolytic %.0f%%, hFE x0.75..1.4): 95th pct max RIAA error | %.2f dB |" % (
              R["montecarlo"]["runs"], R["montecarlo"]["tolerances"]["R"] * 100, R["montecarlo"]["tolerances"]["C"] * 100,
              R["montecarlo"]["tolerances"]["Ce"] * 100, R["montecarlo"]["riaa_dev_p95_abs_db"]),
          "| Monte Carlo gain spread @1 kHz | %.2f .. %.2f dB |" % (R["montecarlo"]["gain_1k_db_min"], R["montecarlo"]["gain_1k_db_max"]),
          ""]
    L += ["## Frequency response / RIAA deviation by value set", "",
          "| Value set | Gain@1k | 10 Hz | 20 Hz | 50 Hz | 100 Hz | 10 kHz | 20 kHz | 50 kHz |", "|---|---|---|---|---|---|---|---|---|"]
    for name, a in R["ac"].items():
        pts = a["points"]
        L.append("| %s | %.2f dB | %s |" % (name, a["gain_1k_db"], " | ".join("%+.2f" % pts[k]["riaa_dev_db"] for k in ("10", "20", "50", "100", "10000", "20000", "50000"))))
    L += ["", "(deviation from ideal RIAA in dB, normalised at 1 kHz)", "",
          "![response](frequency_response.png)", "", "## DC operating point (25 C)", "",
          "| Node | V |", "|---|---|"]
    for n, v in op["nodes"].items():
        L.append("| %s | %.3f |" % (n, v))
    L += ["", "| Transistor | Ic (mA) | Vce (V) | Vbe (V) | Pd (mW) |", "|---|---|---|---|---|"]
    for q, d in op["q"].items():
        L.append("| %s | %.3f | %.2f | %.3f | %.1f |" % (q, d["ic"] * 1e3, d["vce"], d["vbe"], d["pd"] * 1e3))
    L += ["", "Temperature drift: " + ", ".join("%d C: O1=%.2f V, O2=%.2f V, Isup=%.1f mA" % (int(T), d["O1"], d["O2"], d["isupply"] * 1e3) for T, d in R["op_temp"].items()), "",
          "## Distortion (1 kHz)", "", "| Input | Output (V rms) | THD (%) |", "|---|---|---|"]
    for k, d in R["thd"].items():
        L.append("| %s | %.3f | %.4f |" % (k, d["vout_rms"], d["thd_pct"]))
    L += ["", "## Noise", "", "| Source | Out noise 20-20k (uV) | A-wtd (uV) | SNR unwtd | SNR A-wtd |", "|---|---|---|---|---|"]
    for k, d in R["noise"].items():
        L.append("| %s | %.1f | %.1f | %.1f dB | %.1f dB |" % (k, d["out_uV_20_20k"], d["out_uV_A"], d["snr_re5mV_unwtd_db"], d["snr_re5mV_A_db"]))
    L += ["", "![noise](noise.png)", "", "![impedances](impedances_psrr.png)", "", "![powerup](powerup.png)", ""]
    with open(os.path.join(simdir, "RESULTS.md"), "w") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    main()
