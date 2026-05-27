# RPF Compare and Patch Workflow

The preferred Code RED workflow is patch-based and reversible.

## Workflow

1. Keep a clean original copy outside the repo.
2. Keep the modified copy outside the repo.
3. Compare clean vs modified files locally.
4. Generate a changed-path manifest.
5. Export only patch logic or minimum changed data needed by the tool.
6. Validate the patch can be reapplied.
7. Generate a report.
8. Share only public-safe tooling, manifests, and documentation.

## Public Repo Rule

Do not commit full `.rpf` files or extracted retail payloads. Release source tools and documentation. Put only vetted, public-safe build artifacts in GitHub Releases when needed.
