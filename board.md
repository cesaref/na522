I use a NAIM NAC82 preamplifier, which has support for internal phono cards for MM cartridges - the NA522 cards.

These cards are no longer available, so i'm interested in reverse engineering the cards, and producing a compatible phono card design which I can use for this amplifier.

I can't find a schematic for the NA522, but i believe the NA322 board is the same circuit, but with a different form factor for a different Naim amplifier - i've included a pdf in this directory which includes details about the NA322-4 variant, the components and the circuit. I've included some photos of the internals of the NAC82 amplifier with the boards in situ, and then with the boards removed, and close ups of the boards.

The overall dimension of the boards are 83.5mm by 50.5mm. The connectors on the board are 0.8mm by 1.7mm metal pins, and these insert into the four gold plated connectors on the board, with the whole in the board which a plastic peg pushes through to secure the board. Can you estimate the positions of the connectors and peg from the photos - and this information will be reviewed and corrected once a design has been proposed.

Can you help me build boards for this preamp. All designs need to be electrically and physically compatible with the NAC82 preamp, such that they will plug into the header in the preamp to receive power and input/output signals. I would like two designs:

1) A board which uses through hole components, similar to the original design.
2) A board which uses surface mount components. This board should be the modern equivalent of the original board and use high quality components to achieve the best sound quality.

Please generate output which will feed into a review process by an electronic engineer - provide all of the information that they will require to critique the proposed design, and to validate that it is accurate.

Provide a design document that overviews what you have found, with links to the original sources of the information written as a .md file. In addition, for each design create an output directory containing all that would be required to manufacture, build and validate each design. For example, i'd expect to see gerber files for the boards, a list of components, and maybe a spice model with estimated frequency response and gain, and any other circuit characterisation parameters which would be important for the reviewing electronics engineer to complete their assesment.
