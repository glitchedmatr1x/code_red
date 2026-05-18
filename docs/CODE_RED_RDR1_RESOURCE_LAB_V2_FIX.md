# Code RED RDR1 Resource Lab v2 launcher fix

This build fixes the first drop-in launcher behavior where double-clicking the BAT with no command could appear to do nothing because the command window closed immediately.

Changes:

- `Run_CodeRED_RDR1_Resource_Lab.bat` now runs `status` when double-clicked with no arguments.
- The launcher pauses when double-clicked or when an error occurs.
- The launcher checks `py -3`, then `python`, then `python3`.
- A `Double_Click_CodeRED_RDR1_Resource_Lab.bat` convenience launcher is included.

Extract the ZIP into the Code RED root before running it.
