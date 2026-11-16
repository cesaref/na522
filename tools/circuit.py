"""
Single source of truth for the NA522-compatible MM phono card designs.

Topology: Naim NA322/4 (traced by Matthias Stockert, 2019) -- see DESIGN.md.
Every downstream artefact (SPICE netlist, BOM, KiCad netlist/PCB) is generated
from the tables in this file, so a value change here propagates everywhere.

Net names
---------
V24   : +24 V from the NAC82 motherboard (connector pin P1)
VCC   : local rail after R25/C8
GND   : 0 V (connector pin P3)
IN    : phono input (connector pin P4)
OUT   : line-level output (connector pin P2)
B1    : bias node after C1        B1A : T1 base (after R4/C2 RF filter)
N1    : T1 collector / T2 base    E2  : T2 emitter
N2    : T2 collector              B3  : T3 base
O1    : stage-1 output            E1  : T1 emitter (stage-1 feedback node)
C3P   : R6/C3 junction            Y1/Z1 : T4/T5 current sink nodes
B6    : T6 base (after 75 us R12/C4 network)
N6    : T6 collector / T7 base    E7  : T7 emitter
N7    : T7 collector              B8  : T8 base
O2    : stage-2 output            E6  : T6 emitter (stage-2 feedback node)
C5P   : R16/C5 junction           F2  : R17/R21 junction
Y2/Z2 : T9/T10 current sink nodes
"""

# --------------------------------------------------------------------------
# Topology: ref -> (type, pins).  Pin order: R/C = (pin1, pin2) with pin1 = +
# for polarised caps;  Q = (C, B, E).
# --------------------------------------------------------------------------
TOPOLOGY = {
    # ---- input / bias ----
    "R1":  ("R", ("IN", "GND")),
    "C1":  ("C", ("B1", "IN")),          # + to bias node (DC +11.7 V)
    "R3":  ("R", ("VCC", "B1F")),
    "R26": ("R", ("B1F", "B1")),         # new: split bias resistor (0R link in faithful build)
    "C10": ("C", ("B1F", "GND")),        # new: bias-supply filter cap (DNF in faithful build)
    "R2":  ("R", ("B1", "GND")),
    "R4":  ("R", ("B1", "B1A")),
    "C2":  ("C", ("B1A", "GND")),
    # ---- stage 1: T1 (NPN) - T2 (PNP) - T3 (NPN follower), flat gain 1+R10/R6 ----
    "Q1":  ("NPN", ("N1", "B1A", "E1")),
    "R5":  ("R", ("VCC", "N1")),
    "Q2":  ("PNP", ("N2", "N1", "E2")),
    "R7":  ("R", ("VCC", "E2")),
    "R8":  ("R", ("N2", "GND")),
    "R9":  ("R", ("N2", "B3")),
    "Q3":  ("NPN_P", ("VCC", "B3", "O1")),
    "R10": ("R", ("O1", "E1")),
    "R6":  ("R", ("E1", "C3P")),
    "C3":  ("C", ("C3P", "GND")),
    # T4/T5 current sink loading O1 (~0.65 V / R13)
    "Q5":  ("NPN_P", ("O1", "Y1", "Z1")),
    "R11": ("R", ("VCC", "Y1")),
    "Q4":  ("NPN", ("Y1", "Z1", "GND")),
    "R13": ("R", ("Z1", "GND")),
    # ---- passive 75 us pole ----
    "R12": ("R", ("O1", "B6")),
    "C4":  ("C", ("B6", "GND")),
    # ---- stage 2: T6 - T7 - T8, RIAA 3180/318 us in feedback ----
    "Q6":  ("NPN", ("N6", "B6", "E6")),
    "R14": ("R", ("VCC", "N6")),
    "Q7":  ("PNP", ("N7", "N6", "E7")),
    "R18": ("R", ("VCC", "E7")),
    "R19": ("R", ("N7", "GND")),
    "R22": ("R", ("N7", "B8")),
    "Q8":  ("NPN_P", ("VCC", "B8", "O2")),
    "R15": ("R", ("E6", "GND")),
    "R16": ("R", ("E6", "C5P")),
    "C5":  ("C", ("C5P", "GND")),
    "R17": ("R", ("E6", "F2")),
    "R21": ("R", ("F2", "O2")),
    "C6":  ("C", ("F2", "O2")),
    "C6B": ("C", ("F2", "O2")),          # trim capacitor in parallel with C6 (may be DNF)
    # T9/T10 current sink loading O2
    "Q10": ("NPN_P", ("O2", "Y2", "Z2")),
    "R23": ("R", ("VCC", "Y2")),
    "Q9":  ("NPN", ("Y2", "Z2", "GND")),
    "R20": ("R", ("Z2", "GND")),         # labelled (duplicate) "R19 68R" on the NA322/4 drawing
    # ---- output ----
    "C7":  ("C", ("O2", "OUT")),         # + to O2 (DC ~ +14..17 V)
    "R24": ("R", ("OUT", "GND")),
    # ---- supply filter ----
    "R25": ("R", ("V24", "VCC")),
    "C8":  ("C", ("VCC", "GND")),
    "C9":  ("C", ("VCC", "GND")),        # HF bypass (new; DNF in the faithful build)
}

POLARISED = {"C1", "C3", "C5", "C7", "C8", "C10"}

# Card-edge connector (sockets on the underside).  Function assignment is
# inferred from photographs -- MUST be verified on the NAC82 before power-up.
CONNECTOR_NETS = {"P1": "V24", "P2": "OUT", "P3": "GND", "P4": "IN"}

# --------------------------------------------------------------------------
# Value sets
# --------------------------------------------------------------------------
# Values exactly as traced on the NA322/4 (Stockert 2019).
NAIM_TRACED = {
    "R1": 62e3, "C1": 10e-6, "R3": 330e3, "R26": 0.0, "C10": None, "R2": 330e3, "R4": 470, "C2": 470e-12,
    "R5": 22e3, "R7": 1e3, "R8": 22e3, "R9": 1e3, "R10": 2.2e3, "R6": 1e3, "C3": 47e-6,
    "R11": 62e3, "R13": 68,
    "R12": 3.4e3, "C4": 22e-9,
    "R14": 22e3, "R18": 1e3, "R19": 22e3, "R22": 1e3,
    "R15": 220e3, "R16": 390, "C5": 47e-6, "R17": 4.7e3, "R21": 82e3, "C6": 68e-9, "C6B": None,
    "R23": 62e3, "R20": 68,
    "C7": 10e-6, "R24": 100e3,
    "R25": 27, "C8": 47e-6, "C9": None,
}

# Design 1 option B: minimal change to the traced circuit for tighter RIAA
# (R21, R17 only) - found by SPICE-in-the-loop search (tools/optimise_riaa.py).
THT_RIAA = dict(NAIM_TRACED, R21=73.2e3, R17=4.75e3)

# Design 2: SMD "modern equivalent"
SMD = dict(NAIM_TRACED,
           R3=165e3, R26=165e3, C10=10e-6, R1=75e3,   # filtered bias: PSRR, Zin kept ~45k
           C1=1e-6,                    # C0G film-like dielectric, 0.96 Hz with 165k bias
           R6=499, R10=1.1e3, C3=220e-6,  # halve stage-1 feedback impedance (noise), gain 3.20
           R21=63.4e3, R17=4.7e3, C6B=None, C5=220e-6,   # RIAA +/-0.05 dB (SPICE-optimised), gain ~32.2 dB
           C7=47e-6,                   # larger -> negligible AC voltage across electrolytic
           R25=68, C8=470e-6, C9=100e-9)    # 5 Hz supply filter: ~+26 dB PSRR at 100 Hz

# --------------------------------------------------------------------------
# Transistor model selection per design (models in tools/models.lib)
# --------------------------------------------------------------------------
QMODELS = {
    "tht": {"NPN": "BC550C", "NPN_P": "BC550C", "PNP": "BC560C"},
    "smd": {"NPN": "BC850C", "NPN_P": "BCX56", "PNP": "BC860C"},
}

DESIGNS = {
    "tht": {"name": "Design 1 - through-hole (faithful NA322/4 topology)", "values": NAIM_TRACED,
            "alt_values": {"riaa": THT_RIAA}},
    "smd": {"name": "Design 2 - surface-mount (modern, RIAA-exact)", "values": SMD,
            "alt_values": {}},
}


def fmt(v, unit=""):
    """Engineering formatting: 4700 -> 4.7k"""
    if v is None:
        return "DNF"
    for p, s in ((1e-12, "p"), (1e-9, "n"), (1e-6, "u"), (1e-3, "m"), (1, ""), (1e3, "k"), (1e6, "M")):
        x = v / p
        if abs(x) < 999.5:
            t = ("%.3g" % x)
            return t + s + unit
    return "%g" % v
