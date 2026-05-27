# Code RED Archive / RPF Lane Validation Report

Generated UTC: `2026-05-07T05:37:34Z`
Root: `D:\Games\Red Dead Redemption\Code_RED`
Status: **PASS**

## Summary

- Archives discovered: 7
- Archives parsed: 7
- Total entries: 19799
- Total files: 19347
- Sample reads: 28/28 ok
- Sample failures: 0

## Archives

### content.rpf

Path: `D:\Games\Red Dead Redemption\game\content.rpf`
Parsed: yes
Entries: 1636  Files: 1320  Dirs: 316
Resolved names: 1636/1636
Sample reads: 4/4 ok; failed=0; text-like=4; resource=0

Top storage counts:
- compressed: 219
- plain: 215
- resource: 886

Top module counts:
- Scripts: 1083
- Strings: 212
- Unknown: 25

Sample entries:
- [ok] root/content/rdr2_achievements.xml | compressed | .xml | 20499 bytes text
- [ok] root/content/rdr2_challenges.xml | compressed | .xml | 6915 bytes text
- [ok] root/content/dlc/zombiepack/description.txt | compressed | .txt | 153 bytes text
- [ok] root/content/dlc/zombiepack/dlctuerrormsg.strtbl | plain | .strtbl | 2422 bytes text

### tune_d11generic.rpf

Path: `D:\Games\Red Dead Redemption\game\tune_d11generic.rpf`
Parsed: yes
Entries: 2017  Files: 1915  Dirs: 102
Resolved names: 2017/2017
Sample reads: 4/4 ok; failed=0; text-like=4; resource=0

Top storage counts:
- compressed: 1769
- plain: 146

Top module counts:
- Unknown: 1489
- Strings: 337
- Textures: 88
- Audio: 1

Sample entries:
- [ok] root/tune/types/fragments/fragment.xml | compressed | .xml | 430 bytes text
- [ok] root/tune/ai/motives.xml | compressed | .xml | 847 bytes text
- [ok] root/tune/physics/liquid.xml | compressed | .xml | 870 bytes text
- [ok] root/tune/physics/physics.xml | compressed | .xml | 919 bytes text

### terrainboundres.rpf

Path: `D:\Games\Red Dead Redemption\game\terrainboundres.rpf`
Parsed: yes
Entries: 5381  Files: 5378  Dirs: 3
Resolved names: 5381/5381
Sample reads: 4/4 ok; failed=0; text-like=2; resource=2

Top storage counts:
- compressed: 2
- resource: 5376

Top module counts:
- Meshes: 5376
- Strings: 2

Sample entries:
- [ok] root/terrainboundres/territory_swall_noid/validinstance_monkeypostexport.txt | compressed | .txt | 59194 bytes text
- [ok] root/terrainboundres/territory_swall_noid/validinstance_rdr2.txt | compressed | .txt | 59194 bytes text
- [ok] root/terrainboundres/territory_swall_noid/08c022c0_bnd.wtb | resource | .wtb | 28177 bytes
- [ok] root/terrainboundres/territory_swall_noid/108029c0_bnd.wtb | resource | .wtb | 49821 bytes

### camera.rpf

Path: `D:\Games\Red Dead Redemption\game\camera.rpf`
Parsed: yes
Entries: 784  Files: 778  Dirs: 6
Resolved names: 784/784
Sample reads: 4/4 ok; failed=0; text-like=4; resource=0

Top storage counts:
- compressed: 777
- plain: 1

Top module counts:
- Strings: 768
- Unknown: 10

Sample entries:
- [ok] root/camera/gamecameraarcmachine.txt | compressed | .txt | 28765 bytes text
- [ok] root/camera/tune.xml | compressed | .xml | 9540 bytes text
- [ok] root/camera/default_timestamp.txt | plain | .txt | 10 bytes text
- [ok] root/camera/cameralenspresets.txt | compressed | .txt | 4419 bytes text

### gringores.rpf

Path: `D:\Games\Red Dead Redemption\game\gringores.rpf`
Parsed: yes
Entries: 41  Files: 39  Dirs: 2
Resolved names: 41/41
Sample reads: 4/4 ok; failed=0; text-like=1; resource=4

Top storage counts:
- resource: 39

Top module counts:
- World: 39

Sample entries:
- [ok] root/gringores/agaveviejo.wgd | resource | .wgd | 3468 bytes
- [ok] root/gringores/lashermanas.wgd | resource | .wgd | 5105 bytes text
- [ok] root/gringores/elpresidio_z.wgd | resource | .wgd | 821 bytes
- [ok] root/gringores/plainview.wgd | resource | .wgd | 1912 bytes

### navres.rpf

Path: `D:\Games\Red Dead Redemption\game\navres.rpf`
Parsed: yes
Entries: 986  Files: 978  Dirs: 8
Resolved names: 986/986
Sample reads: 4/4 ok; failed=0; text-like=4; resource=0

Top storage counts:
- compressed: 6
- resource: 972

Top module counts:
- World: 934
- Unknown: 38
- Strings: 6

Sample entries:
- [ok] root/navres/battlesets.txt | compressed | .txt | 2651 bytes text
- [ok] root/navres/territory_zombiepack/minheightgrid.xml | compressed | .xml | 21549 bytes text
- [ok] root/navres/territory_zombiepack/heightgrid.xml | compressed | .xml | 85045 bytes text
- [ok] root/navres/territory/minheightgrid.xml | compressed | .xml | 21549 bytes text

### strings_d11generic.rpf

Path: `D:\Games\Red Dead Redemption\game\strings_d11generic.rpf`
Parsed: yes
Entries: 8954  Files: 8939  Dirs: 15
Resolved names: 8954/8954
Sample reads: 4/4 ok; failed=0; text-like=2; resource=0

Top storage counts:
- compressed: 4
- plain: 641
- resource: 8294

Top module counts:
- Strings: 8932
- Unknown: 7

Sample entries:
- [ok] root/strings/subtitle_grave03_cs03_win32.strtbl | plain | .strtbl | 20833 bytes
- [ok] root/strings/subtitle_r4_end_win32.strtbl | plain | .strtbl | 26389 bytes text
- [ok] root/strings/subtitle_rcm_12_cs01_jack_win32.strtbl | plain | .strtbl | 28360 bytes
- [ok] root/strings/subtitle_rcm_11_cs02_jack_win32.strtbl | plain | .strtbl | 25286 bytes text

## Safety

This validation is read-only. It inventories and sample-reads staged RPF6 archives, but does not modify source archives.
Patch/install operations must continue to use copied archives and proof reports.
