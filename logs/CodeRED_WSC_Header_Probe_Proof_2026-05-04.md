# Code RED WSC Header Probe Proof — 2026-05-04

## Command

```powershell
py -3 tools\codered_probe_wsc_headers.py --root "C:\Users\glitc\OneDrive\Desktop\CodeRED_RPF_Extracts"
```

## Result

The targeted WSC probe found 11 important camp/vehicle gringo WSC files.

## Key WSC header evidence

All targeted WSC leads began with the same header family:

```text
52 53 43 85 ...
ASCII: RSC.
```

Examples:

```text
content/release64/scripting/gringo/commonscripts/playercamp01_gringo.wsc
head: 52 53 43 85 02 00 00 00 00 00 00 80 06 00 00 90
sha1: 877A581D5FDB9AC163E621ECC1C4277C738A6E3D

content/release64/scripting/gringo/commonscripts/vehicle_generator.wsc
head: 52 53 43 85 02 00 00 00 00 00 00 80 01 00 00 80
sha1: B754BD583399726F568F2E406F3DCDB9D472A11C

content/release64/scripting/gringo/commonscripts/car_gringo.wsc
head: 52 53 43 85 02 00 00 00 00 00 00 80 03 00 00 80
sha1: 1751BD2B912039048FD480B43DA6EA2B9386FFA9

content/release64/scripting/gringo/commonscripts/playercar.wsc
head: 52 53 43 85 02 00 00 00 00 00 00 80 06 00 00 90
sha1: 1B0A2469309D9A761CCFCC9370D9C22FE458894D
```

## Compared formats

Previously proven extracted/compiled SCO files begin with:

```text
53 43 52 02 ...
ASCII: SCR.
```

Previously proven compiled XSC files begin with:

```text
85 43 53 52 ...
ASCII: .CSR
```

Targeted WSC files begin with:

```text
52 53 43 85 ...
ASCII: RSC.
```

## Interpretation

WSC is not in the SCO header family.

WSC appears closer to the XSC header family than to SCO, because the byte set is related to XSC (`85 43 53 52` vs `52 53 43 85`), but the order/layout differs.

Do not rename `.xsc` or `.sco` to `.wsc` yet.

## Current safe conclusion

```text
.sco: proven SC-CL RDR_SCO output and same broad SCR header family as extracted .sco
.xsc: proven SC-CL RDR_#SC output and .CSR header family
.wsc: extracted gringo script format with RSC. header family, not yet reproducible by SC-CL in this lane
```

## Next safe step

Add a WSC/XSC conversion research lane, not an install lane:

1. Check whether SC-CL has a target/flag that emits `RSC.` / `.wsc` style output.
2. Compare XSC and WSC header fields to see whether this is endian/platform wrapping.
3. Do not patch `playercamp01_gringo.wsc` until WSC output/packing is proven.
4. For runtime proof, prefer the compiled `.sco` lane if an `.sco` slot can be tested in a copied archive.
