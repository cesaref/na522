# Design 2: surface-mount "modern equivalent"

A plug-in replacement for the NA522 MM card in the NAC82.

- **Topology:** the same Naim discrete topology, so the gain, input loading and output behaviour match the original.
- **Parts:** precision components throughout.
- **Changes from the original** are all simulated; see `simulation/RESULTS.md`.
- **Boards:** a stereo pair is one **T** and one **B** board (mirror images).

## What changed from the original, and why

| Change | Original | Design 2 | Reason / effect (simulated) |
|---|---|---|---|
| RIAA network | R17 4K7, R21 82K, C5 47 µF | R17 4K7, **R21 63.4 k**, **C5 220 µF** | RIAA error 0.57 dB → **0.04 dB** (20 Hz–20 kHz). Values found by SPICE-in-the-loop search (`tools/optimise_riaa.py`); insensitive to hFE (0.75–1.4×) |
| Resistors | 1 % metal film (R12 1 %/50 ppm) | **0.1 %, 25 ppm thin film** (Vishay TNPW0805) | Monte Carlo RIAA spread (95th pct) 0.73 → 0.16 dB; channel match |
| RIAA capacitors | Polyester/film | **C0G/NP0 MLCC** (alt. PPS film) | Negligible voltage coefficient and dielectric absorption |
| Stage-1 feedback | R6 1K, R10 2K2, C3 47 µF | **R6 499 Ω, R10 1.1 k, C3 220 µF** | Same gain (×3.2); about half the feedback-network thermal noise. EIN 5.9 → 5.3 nV/√Hz |
| Input coupling C1 | 10 µF tantalum | **1 µF C0G** | No tantalum in the signal path. 0.96 Hz corner with the 165 k bias network |
| Bias divider | R3 330k direct from VCC | **R3 165k + R26 165k + C10 10 µF** (R1 62k → 75k keeps Zin 44 k) | Removes supply ripple from the input transistor base |
| Supply filter | R25 27 Ω, C8 47 µF | **R25 68 Ω, C8 470 µF**, plus C9 100 nF | 5 Hz corner. PSRR @100 Hz improves from −19.5 dB to **−46 dB** |
| Output coupling C7 | 10 µF tantalum | **47 µF electrolytic** | Less AC voltage across the electrolytic; no tantalum |
| Followers / sinks (Q3, Q5, Q8, Q10) | ZTX (E-line) | **BCX56-16, SOT-89** | ~0.1 W each: needs a SOT-89 package, not SOT-23 |
| Small-signal transistors | ZTX384C / ZTX214C | **BC850C / BC860C** (SOT-23) | Low-noise C-group parts |

Gain, input impedance (44 kΩ, 470 pF), output DC conditions, supply current (20 mA) and overload margin are essentially unchanged.

## Contents

Same structure as Design 1: `schematic/`, `bom/`, `simulation/`, `pcb_T/`, `pcb_B/`. See `../design1_tht/README.md` for the file-by-file table and the regeneration commands (replace `tht` with `smd`).

## Fabrication and assembly notes

- **Board:** 2 layers, FR-4 1.6 mm, 1 oz, **ENIG**. Same outline, holes, rules and DRC status as Design 1, with clearance ≥0.25 mm.
- **Components:** all SMD parts are on the **top** side, and pick-and-place files are provided (`pcb_*/*_pos.csv`). The four sockets are through-hole and fitted from the bottom; hand-solder them after reflow.
- **Stencil:** the paste layer is included (`*-F_Paste.gtp`).
- **Smallest parts:** 0805 passives and SOT-23, so it can be hand-assembled.
- **C8 voltage margin:** C8 runs at 65 % of its 35 V rating. Use the 50 V version if one is available in a 10 × 10 mm can.

## Key simulated figures

| | Value |
|---|---|
| Gain @1 kHz | 32.2 dB |
| RIAA deviation | ±0.04 dB from 20 Hz to 20 kHz (−0.2 dB @10 Hz). MC 95th percentile: 0.16 dB |
| Input impedance | 44.2 kΩ (+470 pF) |
| SNR re 5 mV, A-wtd | 84 dB with the input shorted, 78 dB with a cartridge |
| THD @1 kHz | 0.0065 % at 5 mV, 0.053 % at 50 mV |
| Overload @1 kHz | 184 mV |
| PSRR @100 Hz | −46 dB |
| Supply current | 20.2 mA |
| Power-up | +21 V transient at OUT (as the original); settles in ~13 s |
