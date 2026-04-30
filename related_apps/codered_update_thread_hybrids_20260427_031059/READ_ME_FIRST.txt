Code RED update-thread hybrid builds generated from your own content.rpf.

Test order I recommend:
1) content_sp_owner.rpf - least conflict; normal SP owns the long update state.
2) content_z_owner.rpf - zombie DLC owns the long update state.
3) content_dual_swap.rpf - recreates the stronger mixed-mode swap.
4) content_all_long_medium_short_dual.rpf - highest risk, all update pairs swapped.

Do not overwrite the original. Rename the chosen candidate to content.rpf only after backing up.
