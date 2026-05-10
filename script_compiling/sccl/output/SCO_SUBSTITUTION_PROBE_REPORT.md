# Code RED SCO Substitution Probe Report

Project: vehicle_menu_probe
Output: test_sco
RDR_SCO compile exit code: 0

## Generated artifacts
### script_compiling\sccl\output\vehicle_menu_probe\test_ps3.csc
- extension: .csc
- length: 1426
- sha1: 7F547D195D5589EC4AC9CD4F5CF040AF315403BF
- first 32 bytes: 86 43 53 52 00 00 00 02 80 00 00 00 80 00 00 01 63 8E 7D 42 C4 C5 F4 47 76 57 2A 8B 6D 61 FA 39

### script_compiling\sccl\output\vehicle_menu_probe\test_sco.sco
- extension: .sco
- length: 1402
- sha1: 627F6E338ED0DDB1F52EA998FAA1F999EBE4F8D8
- first 32 bytes: 53 43 52 02 34 9D 01 8A 00 00 05 4A FF FF FF FD 00 00 0B 4B 00 00 00 0E 00 00 00 00 00 00 00 00

### script_compiling\sccl\output\vehicle_menu_probe\test_x360.xsc
- extension: .xsc
- length: 1462
- sha1: F6BDB733B54EAAAE757984008A7804F489471A5D
- first 32 bytes: 85 43 53 52 00 00 00 02 80 00 00 00 80 00 00 01 D4 B0 6C 63 C6 C8 A0 82 B3 4C D9 AD 61 C7 7E BD

## Verdict
A successful .sco compile only proves SC-CL can emit RDR_SCO. It does not prove that active WSC/RSC85 script requests will accept .sco in place of .wsc.

Safe next test: use a tiny noncritical script probe/alias before attempting anything near multiplayer_update_thread.
