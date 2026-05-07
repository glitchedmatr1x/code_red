# Code RED Archive / RPF Lane Validation Report

Generated UTC: `2026-05-07T05:17:24Z`
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
Resolved names: 1/1636
Sample reads: 4/4 ok; failed=0; text-like=4; resource=0

Top storage counts:
- compressed: 219
- plain: 215
- resource: 886

Top module counts:
- Unknown: 1320

Sample entries:
- [ok] root/0x753DB284/0xA57F233C | compressed |  | 20499 bytes text
- [ok] root/0x753DB284/0xC10D9746 | compressed |  | 6915 bytes text
- [ok] root/0x753DB284/0x06C35575/0x22398628/0x173D2464 | compressed |  | 8684 bytes text
- [ok] root/0x753DB284/0x06C35575/0x22398628/0x21572403 | compressed |  | 153 bytes text

### tune_d11generic.rpf

Path: `D:\Games\Red Dead Redemption\game\tune_d11generic.rpf`
Parsed: yes
Entries: 2017  Files: 1915  Dirs: 102
Resolved names: 1/2017
Sample reads: 4/4 ok; failed=0; text-like=2; resource=0

Top storage counts:
- compressed: 1769
- plain: 146

Top module counts:
- Unknown: 1915

Sample entries:
- [ok] root/0xA562A52D/0x8C3BA51D | compressed |  | 8399344 bytes
- [ok] root/0xA562A52D/0xADFDAAB3 | compressed |  | 8294972 bytes
- [ok] root/0xA562A52D/0x084275E1/0xE60ADCAC/0x6F128FD7 | compressed |  | 430 bytes text
- [ok] root/0xA562A52D/0x0ADC283D/0x04CE8507 | compressed |  | 128689 bytes text

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
Resolved names: 1/784
Sample reads: 4/4 ok; failed=0; text-like=4; resource=0

Top storage counts:
- compressed: 777
- plain: 1

Top module counts:
- Unknown: 778

Sample entries:
- [ok] root/0x25584DB6/0x0096DFE1 | compressed |  | 7152 bytes text
- [ok] root/0x25584DB6/0x045E8155 | compressed |  | 22330 bytes text
- [ok] root/0x25584DB6/0x1AE60DB7 | compressed |  | 62982 bytes text
- [ok] root/0x25584DB6/0x1CA9CF72 | compressed |  | 28765 bytes text

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
Resolved names: 1/986
Sample reads: 4/4 ok; failed=0; text-like=2; resource=3

Top storage counts:
- compressed: 6
- resource: 972

Top module counts:
- Unknown: 978

Sample entries:
- [ok] root/0x72686CAD/0x6C484837 | compressed |  | 2651 bytes text
- [ok] root/0x72686CAD/0x02EB4B02/0x01EA9618 | resource |  | 2345 bytes
- [ok] root/0x72686CAD/0x02EB4B02/0x0417C5F2 | resource |  | 61 bytes text
- [ok] root/0x72686CAD/0x02EB4B02/0x041FAE82 | resource |  | 326750 bytes

### strings_d11generic.rpf

Path: `D:\Games\Red Dead Redemption\game\strings_d11generic.rpf`
Parsed: yes
Entries: 8954  Files: 8939  Dirs: 15
Resolved names: 1/8954
Sample reads: 4/4 ok; failed=0; text-like=2; resource=4

Top storage counts:
- compressed: 4
- plain: 641
- resource: 8294

Top module counts:
- Unknown: 8939

Sample entries:
- [ok] root/0x560A49F7/0x001260CA | resource |  | 489 bytes
- [ok] root/0x560A49F7/0x001B491D | resource |  | 1654 bytes
- [ok] root/0x560A49F7/0x001D6711 | resource |  | 380 bytes text
- [ok] root/0x560A49F7/0x00216C5A | resource |  | 400 bytes text

## Safety

This validation is read-only. It inventories and sample-reads staged RPF6 archives, but does not modify source archives.
Patch/install operations must continue to use copied archives and proof reports.
