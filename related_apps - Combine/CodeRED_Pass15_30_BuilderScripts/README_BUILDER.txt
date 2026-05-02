Code RED Pass 15.30 Builder Package
===================================

This package is a builder-first cumulative pass.

Run:

    python -S builders/build_codered_pass15_30_from_pass12.py

It starts from the included Pass 12 base RPFs, then builds staged outputs:

- 15.00 Pass 12 base validation
- 15.10 empty-world merge
- 15.20 Blackwater chaos merge
- 15.30 lasso/sheriff tuning merge

The included ready-to-test RPFs are already in:

    final_stage_15_30/archives/content.rpf
    final_stage_15_30/archives/tune_d11generic.rpf

The builder re-creates the same style of cumulative output into:

    output/CodeRED_Pass15_30_rebuilt_from_builder.zip

Next pass queue:

- 15.40 all towns active
- 15.50 two nearby rival gangs near every town
- 15.60 store robbery / hogtying / civilian weapon distribution
- 15.70 guard dogs
- 15.80 gatling wagon / maxim truck assault lanes
- 15.90 radar/map active-area markers

Rule: preserve Pass 12 first, layer later edits second, validate markers after every stage.
