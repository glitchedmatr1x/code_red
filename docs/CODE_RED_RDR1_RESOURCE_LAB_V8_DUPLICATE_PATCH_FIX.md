# Code RED RDR1 Resource Lab v8 duplicate patch fix

v8 fixes a false-failure case in `patch-archive`.

Older staging passes could leave both of these files in the same patch root:

- `patches/wgd_lasso_override/commongringos.wgd` from early staging
- `patches/wgd_lasso_override/root/gringores/commongringos.wgd` from exact internal-path staging

Both point at the same RPF entry, but only the nested exact-path file is the
right v7+ exact-size repacked resource. v8 resolves all candidates before
writing, chooses the best exact-path/exact-size candidate, and marks older
root-level duplicates as `superseded` instead of failing after the good patch is
already applied.

Manual cleanup is still safe:

```powershell
Remove-Item patches\wgd_lasso_override\commongringos.wgd
```

But it is no longer required for this case.
