# Code RED Archive / RPF Lane Validation Report

Generated UTC: `2026-05-03T08:34:23Z`
Root: `/mnt/data/codered_work`
Status: **PASS**

## Summary

- Archives discovered: 2
- Archives parsed: 2
- Total entries: 3653
- Total files: 3235
- Sample reads: 16/16 ok
- Sample failures: 0

## Archives

### content.rpf

Path: `/mnt/data/content.rpf`
Parsed: yes
Entries: 1636  Files: 1320  Dirs: 316
Resolved names: 1558/1636
Sample reads: 8/8 ok; failed=0; text-like=8; resource=0

Top storage counts:
- compressed: 219
- plain: 215
- resource: 886

Top module counts:
- Scripts: 1083
- Strings: 201
- Unknown: 36

Sample entries:
- [ok] root/content/rdr2_achievements.xml | compressed | .xml | 20499 bytes text
- [ok] root/content/rdr2_challenges.xml | compressed | .xml | 6915 bytes text
- [ok] root/content/ai/movementtuning.xml | compressed | .xml | 5432 bytes text
- [ok] root/content/ai/motives.xml | compressed | .xml | 955 bytes text
- [ok] root/content/ai/unalertedai/default_howlmoon.xml | compressed | .xml | 850 bytes text
- [ok] root/content/ai/unalertedai/pen_eat.xml | compressed | .xml | 925 bytes text
- [ok] root/content/ai/unalertedai/default_sleep.xml | compressed | .xml | 434 bytes text
- [ok] root/content/ai/unalertedai/default_drink.xml | compressed | .xml | 928 bytes text

### tune_d11generic.rpf

Path: `/mnt/data/tune_d11generic.rpf`
Parsed: yes
Entries: 2017  Files: 1915  Dirs: 102
Resolved names: 1719/2017
Sample reads: 8/8 ok; failed=0; text-like=8; resource=0

Top storage counts:
- compressed: 1769
- plain: 146

Top module counts:
- Unknown: 1499
- Strings: 327
- Textures: 88
- Audio: 1

Sample entries:
- [ok] root/tune/ai/motives.xml | compressed | .xml | 847 bytes text
- [ok] root/tune/asd/pig.xml | compressed | .xml | 12369 bytes text
- [ok] root/tune/asd/crow.xml | compressed | .xml | 12364 bytes text
- [ok] root/tune/asd/raccoon.xml | compressed | .xml | 12366 bytes text
- [ok] root/tune/asd/duck.xml | compressed | .xml | 12364 bytes text
- [ok] root/tune/asd/fox.xml | compressed | .xml | 12369 bytes text
- [ok] root/tune/asd/songbird.xml | compressed | .xml | 12365 bytes text
- [ok] root/tune/asd/oldm.xml | compressed | .xml | 12367 bytes text

## Safety

This validation is read-only. It inventories and sample-reads staged RPF6 archives, but does not modify source archives.
Patch/install operations must continue to use copied archives and proof reports.
