# Build, bring-up and validation procedure (both designs)

Expected values below come from the ngspice operating point and AC results:
`design1_tht/simulation/RESULTS.md` and `design2_smd/simulation/RESULTS.md`.
Allow ±10 % on DC currents and ±0.5 V on node voltages. These depend on hFE and Vbe spread.

## 0. Before ordering anything: verify the NAC82 slot (amplifier only, no cards)

The connector positions and pin functions are **estimates from photographs** (see `common/mechanical/`). Confirm them first.

1. **Pin positions.** Lay a 1:1 print of `common/mechanical/mechanical_T.pdf` and `mechanical_B.pdf` over the motherboard pins, or measure pin-to-pin distances with callipers. Record the corrections in `tools/placement.py` (`SOCKETS_T`, `PEG_T`) and regenerate the boards (`tools/build_pcb.py`). The B board is the X-mirror of T. Keep the ±1.5 mm uncertainty circles in mind.
2. **Pin functions.** With the amplifier unpowered:
   - P3 (wide trace to the input cable screen) reads **0 Ω** to the signal ground / input socket screen.
   - P4 shows continuity to the **centre pin** of the phono input socket for that channel.
   - P2 shows continuity through the motherboard series resistor to the selector.
3. **Supply.** Power the NAC82 with no cards fitted. P1 should read **+24 V** (±1 V) to P3, and P2/P4 should read ≈0 V.
4. If any function differs, change `CONNECTOR_NETS` in `tools/circuit.py` and regenerate. **Do not plug a card in until the pinout is confirmed.**
5. **Socket fit.** Fit a sample Mill-Max 0391 socket onto a motherboard pin. Check:
   - retention and wobble;
   - that the blade (0.8 × 1.7 mm, 1.88 mm diagonal) is within the 1.65–2.08 mm contact range;
   - that the pin length does not bottom out in the closed socket;
   - the height of the card above the motherboard, against the peg's snap-in height.
6. **Clearance.** Check the lid and component height clearance. The THT electrolytics are 11 mm tall and the SMD ones 10.2 mm. Allow ~6 mm more for the THT film capacitors.

## 1. Bare board checks

- [ ] Outline 83.5 × 50.5 mm, plus the small "ears" next to P1/P4 where the 5.6 mm socket pad needs extra edge distance (see `DESIGN.md` §6.3).
- [ ] Hole sizes: four 4.1 mm plated socket holes and one 3.2 mm non-plated peg hole.
- [ ] Continuity: P3 to the GND pour; no short between P1 and P3 (should be >1 MΩ before assembly).

## 2. Assembly

1. **SMD design:** reflow or hand-solder all SMD parts on the top side. Use the position files `pcb_*/*_pos.csv` and the BOM.
2. **THT design:** fit in height order: link R26, resistors, film caps, transistors, electrolytics. Watch the TO-92 orientation: BC550C/BC560C are C-B-E, footprint pad 1 = C (square pad).
3. **Polarised caps.** The `+` must go to the higher-voltage node:
   - C1: bias node
   - C7: O2
   - C3: Q1/R6 side
   - C5: R16 side
   - C8: VCC
4. **Sockets** P1–P4 go on the **underside**. Press them into the 4.1 mm holes from the bottom and solder from the top. Keep them perpendicular by soldering while the card is plugged onto a spare set of pins, or onto the NAC82 itself with power off.
5. **Build one T board and one B board.** They are mirror images. **Do not** mount a T board in the B position.
6. Wash off flux. The input node B1/B1A sits at 11 V with 165 kΩ source impedance, so leakage from flux residue causes offset and noise.

## 3. Power-up on the bench (card not in the amplifier)

Supply 24 V through a 100 Ω series resistor (current-limited) between P1 (+) and P3 (−). Short P4 to P3, and put 47 kΩ from P2 to P3.

| Check | Design 1 (THT) | Design 2 (SMD) |
|---|---|---|
| Supply current (no 100 Ω resistor) | 20.4 mA | 20.2 mA |
| VCC (C8 +) | 23.45 V | 22.63 V |
| B1 (R2 top / C1 +) | 11.7 V | 11.3 V |
| E1 (Q1 emitter) | 11.1 V | 10.7 V |
| O1 (Q3 emitter) | 11.0 V | 10.65 V |
| Z1, Z2 (R13 / R20 top) | 0.63 V (→ 9.3 mA sinks) | 0.63 V |
| E6 (Q6 emitter) | 10.4 V | 10.1 V |
| O2 (Q8 emitter / C7 +) | 10.0 V | 9.6 V |
| OUT (P2) after settling | 0 V ±20 mV | 0 V ±20 mV |
| Settling time of OUT to <50 mV | ~6 s | ~13 s |

- O2 is the most sensitive node: it depends on the balance between Q6's current and R15. Simulation shows 9.6–10.4 V over 0–60 °C.
- If O2 sits more than 2 V from the expected value, check Q6/Q7/R14/R15/R17/R21.

**Power-up thump.** At switch-on, OUT swings to about +20 V for a few hundred milliseconds into 47 kΩ. This is inherited from the original topology (simulated: `simulation/powerup.png`). Check that the NAC82 output muting, or your power-up order, protects the power amplifier and speakers. Do this before connecting speakers.

## 4. AC measurements

Instruments: an audio analyser or a sound-card setup (e.g. REW / ARTA) and an inverse-RIAA network (e.g. the Hagerman "iRIAA" or Lipshitz passive network). Drive through a 600 Ω / 1 kΩ source. Load OUT with 47 kΩ.

| Test | Method | Design 1 target | Design 2 target |
|---|---|---|---|
| Gain @1 kHz | 5 mV rms in | 32.2 dB (×40.6) ±0.5 dB | 32.2 dB (×40.9) ±0.3 dB |
| RIAA conformance 20 Hz–20 kHz | Through the inverse-RIAA network; sweep | +0.44 dB @20 Hz, +0.40 dB @50 Hz, +0.05 dB @20 kHz | ±0.05 dB nominal (95 % of builds ±0.16 dB) |
| L/R matching | Compare T and B cards | <0.3 dB | <0.1 dB |
| THD+N @1 kHz | 5 mV and 50 mV in | ≈0.007 % / 0.05 % (sim) | ≈0.007 % / 0.05 % (sim) |
| Overload @1 kHz (1 % THD) | Increase level | ≈180 mV in (≈7.3 V rms out) | ≈184 mV in |
| Overload @20 Hz / 20 kHz | Increase level | ≈12 mV / 1.7 V in | ≈13 mV / 1.7 V in |
| Noise, input shorted, A-wtd | Output noise | ≈14 µV (83 dB re 5 mV) | ≈13 µV (84 dB) |
| Noise with cartridge dummy (1 k + 0.5 H), A-wtd | Output noise | ≈26 µV (78 dB) | ≈25 µV (78 dB) |
| Input impedance | 1 kHz, series R method | 44.7 kΩ | 44.2 kΩ |
| Hum | 100 Hz component of output noise in the NAC82 | Compare with the original card | Expect ≥25 dB better PSRR than D1 |

- Overload @1 kHz: the 1 kHz figure is ~31 dB above 5 mV.
- Overload @20 Hz/20 kHz: the 20 Hz figure is limited by output swing at maximum bass gain.

## 5. In the NAC82

1. **First power-up.** Power off, fit the cards (T and B in their correct positions), and connect no source.
   - Re-measure the supply current: insert a meter in the P1 line using a socket adapter, or measure the voltage across R25.
     - Design 1: 0.55 V across 27 Ω.
     - Design 2: 1.37 V across 68 Ω.
2. **Listening test.** Use low volume first. Compare against a known-good original card if one is available.
3. **Hum check.** Check hum with the input shorted and the volume at maximum.
