Code RED Blackwater Faction War Pass 15
=========================================

This is the corrected full merge pass. It uses Pass 12 as the base so the faction-war, wilderness population, companion pulse, traffic, ambient manager, and PlayerAlly relationship work are preserved. It then layers the confirmed Pass 13 empty-world activity and Pass 14 Blackwater/law/duel/lasso updates on top.

Install
-------
1. Back up your current content.rpf and tune_d11generic.rpf.
2. Copy archives/content.rpf into the same location where you tested the previous content.rpf replacements.
3. Copy archives/tune_d11generic.rpf only if your current faction-war setup uses the modified tune archive. For the intended full Pass 15 test, replace both.
4. Test Blackwater main roads, town edges, roads into town, Thieves Landing, rail corridors, and empty wilderness for several in-game hours.

What this pass is meant to do
----------------------------
- Keep all Pass 12 faction-war and companion scaffolding.
- Keep the empty-world activity that already tested fine.
- Add Blackwater law/high-alert pressure and standoff/duel event eligibility.
- Add rowdy-gang and lone-lawman pressure.
- Keep Pass 14 lasso/sheriff/base_lasso tuning on top of Pass 12 tune.

Validation summary
------------------
Required checks passed: True
content.rpf SHA1: 79160225d430e654ed2c465a8c3ffc56a37906d3
tune_d11generic.rpf SHA1: b7b7cf5ee985fb9c75ba5fffa0d9418f956375ef

Notes
-----
strings_d11generic.rpf was researched for names/labels and leads, but it is not a spawn controller by itself, so no strings archive replacement is included in this pass. The findings were submitted to GitHub and included in research_notes/.
