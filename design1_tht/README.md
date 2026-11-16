# Design 1: through-hole, faithful NA322/4 topology

A plug-in replacement for the Naim NA522 MM phono card in the NAC82.

- **Circuit:** the traced NA322/4 circuit with its original values.
- **Parts:** modern through-hole equivalents (see `bom/`).
- **Optional additions:** two positions for later improvements. Both are inactive in the default build:
  - R26/C10, a bias-supply filter. R26 is fitted as a 0 Ω link and C10 is not fitted.
  - C9, an HF bypass (not fitted).
- **Boards:** a stereo pair is one **T** and one **B** board. They are mirror images, as on the original cards.

Read `../DESIGN.md` first for the background, the reverse-engineering evidence and the open questions.

## Contents

| Path | What |
|---|---|
| `schematic/na522_tht_schematic.{pdf,svg,png}` | Schematic with values (drawn from `tools/circuit.py`) |
| `bom/BOM.md`, `bom/*.csv` | BOM per reference and grouped, with MPNs and capacitor DC-voltage/rating checks from the simulated operating point |
| `simulation/RESULTS.md` | Full ngspice characterisation: gain, RIAA error, Monte Carlo, noise, THD, overload, Zin/Zout, PSRR, power-up, DC operating point, temperature drift |
| `simulation/netlists/*.cir` | Every netlist simulated; re-run with `ngspice -b file.cir` inside that folder |
| `pcb_T/`, `pcb_B/` | KiCad 10 boards (`.kicad_pcb`), Gerbers (`gerbers/` + `_gerbers.zip`), Excellon drill + drill maps, pick-and-place `_pos.csv`, assembly PDF, renders, copper SVGs, DRC report |
| `../common/TEST_PROCEDURE.md` | Slot verification, assembly, bring-up voltages, AC acceptance tests |
| `../common/mechanical/` | Connector/peg coordinates, dimensioned drawings, annotated photographs |

## Fabrication notes (both T and B)

| Item | Value |
|---|---|
| Layers | 2, FR-4, 1.6 mm, 35 µm (1 oz) copper |
| Finish | ENIG preferred (gold to suit the gold socket contacts); HASL is acceptable |
| Outline | 83.5 × 50.5 mm, 0.5 mm corner chamfers, plus two small "ears" (≤1.4 mm) next to P1/P4. See `DESIGN.md` §6.3 |
| Tracks / clearance | All tracks 0.4 mm (supply current is 20 mA); clearance ≥0.3 mm; edge keep-out 1 mm |
| Vias | 0.8 mm pad, 0.4 mm drill |
| Holes | Sockets: 4.1 mm plated, 5.6 mm pad. Peg: 3.2 mm non-plated |
| Copper pours | GND on both layers |
| Solder mask / silk | Green / white; the bottom silk carries the "sockets on THIS side" note |
| DRC | 0 errors, 0 unconnected (KiCad 10.0.8). Warnings are silkscreen overlaps only, plus "library not found" because KiCad's global footprint table is not configured on the build machine |

Each `pcb_*/gerbers/` folder contains all of these:

- `*-F_Cu.gtl` and `*-B_Cu.gbl`
- `*-F_Mask.gts` and `*-B_Mask.gbs`
- `*-F_Silkscreen.gto` and `*-B_Silkscreen.gbo`
- `*-F_Paste.gtp` and `*-B_Paste.gbp`
- `*-Edge_Cuts.gm1`
- `*-PTH.drl` and `*-NPTH.drl`
- the drill map PDFs
- `*-job.gbrjob`

Upload `*_gerbers.zip` to the board house. **Order the T and B boards as two separate designs.**

## Key simulated figures (47 kΩ load, 24 V supply)

| | Value |
|---|---|
| Gain @1 kHz | 32.2 dB |
| RIAA deviation | +0.44 dB @20 Hz, +0.40 dB @50 Hz, ≤0.07 dB from 100 Hz to 20 kHz. MC 95th percentile: 0.73 dB |
| Input impedance | 44.7 kΩ (R1 62k ‖ R2/R3 165k), plus ~470 pF (C2 via R4) |
| SNR re 5 mV, A-wtd | 83 dB with the input shorted, 78 dB with a 1 k + 500 mH cartridge |
| THD @1 kHz | 0.0065 % at 5 mV in |
| Overload @1 kHz | 181 mV (31 dB margin) |
| PSRR @100 Hz | **−19.5 dB**. The original relies on a clean, regulated 24 V. Fit option R26/C10 + C9 to improve it (see `DESIGN.md` §5.4) |
| Supply current | 20.4 mA |

## Value options

- **'riaa'**: R21 = 73.2 k and R17 = 4.75 k (was 82 k / 4.7 k). The maximum RIAA error from 20 Hz to 20 kHz falls from 0.57 dB to 0.13 dB, a deliberate departure from the Naim voicing.
- **Bias filter**: R3 = 165 k, R26 = 165 k, C10 = 10 µF, and R1 = 75 k to keep Zin ≈ 45 k. This mirrors Design 2.

## Regenerating

From the repo root:

```
/opt/homebrew/bin/python3.14 tools/simulate.py tht          # simulation
work/venv/bin/python tools/draw_schematic.py                # schematic
/opt/homebrew/bin/python3.14 tools/make_bom.py              # BOM
$KPY tools/build_pcb.py tht T ; $KPY tools/build_pcb.py tht B   # place, autoroute, DRC, Gerbers
```

where `KPY=~/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3`.
