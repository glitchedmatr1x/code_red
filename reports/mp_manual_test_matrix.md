# Code RED MP Manual Test Matrix

Run one copied `content.rpf` lane at a time. Do not compare runtime results until Magic RDR reopen/export verification passes for that lane.

| Lane | Name | Package | Import target | Purpose |
| --- | --- | --- | --- | --- |
| A | baseline_no_mp_restore | None | Clean backup / no MP restore | Baseline UI and error path |
| B | release64_csc_only | import_test_release64_csc | content/release64/multiplayer/ | PC-comparable path family |
| C | release_csc_only | import_test_release_csc | content/release/multiplayer/ | Legacy release path visibility |
| D | both_release_and_release64_csc | import_test_both_csc | both CSC path families | Path ambiguity isolation |
| E | xsc_review_only | import_test_xsc_review | Do not import without explicit approval | Wrapper review lane |

## Per-lane Worksheet

### Lane A: baseline_no_mp_restore

- Package: `None`
- Target: `Clean backup / no MP restore`
- Purpose: Baseline UI and error path

| Field | Result |
| --- | --- |
| content.rpf backup used |  |
| imported package |  |
| Magic RDR reopen/export verification result |  |
| byte compare result |  |
| launch result |  |
| menu change |  |
| new option visible |  |
| old option unlocked |  |
| different error message |  |
| loading screen change |  |
| crash/hang/return-to-menu behavior |  |
| log/crash/report evidence |  |
| screenshot/video note |  |
| next action |  |

### Lane B: release64_csc_only

- Package: `import_test_release64_csc`
- Target: `content/release64/multiplayer/`
- Purpose: PC-comparable path family

| Field | Result |
| --- | --- |
| content.rpf backup used |  |
| imported package |  |
| Magic RDR reopen/export verification result |  |
| byte compare result |  |
| launch result |  |
| menu change |  |
| new option visible |  |
| old option unlocked |  |
| different error message |  |
| loading screen change |  |
| crash/hang/return-to-menu behavior |  |
| log/crash/report evidence |  |
| screenshot/video note |  |
| next action |  |

### Lane C: release_csc_only

- Package: `import_test_release_csc`
- Target: `content/release/multiplayer/`
- Purpose: Legacy release path visibility

| Field | Result |
| --- | --- |
| content.rpf backup used |  |
| imported package |  |
| Magic RDR reopen/export verification result |  |
| byte compare result |  |
| launch result |  |
| menu change |  |
| new option visible |  |
| old option unlocked |  |
| different error message |  |
| loading screen change |  |
| crash/hang/return-to-menu behavior |  |
| log/crash/report evidence |  |
| screenshot/video note |  |
| next action |  |

### Lane D: both_release_and_release64_csc

- Package: `import_test_both_csc`
- Target: `both CSC path families`
- Purpose: Path ambiguity isolation

| Field | Result |
| --- | --- |
| content.rpf backup used |  |
| imported package |  |
| Magic RDR reopen/export verification result |  |
| byte compare result |  |
| launch result |  |
| menu change |  |
| new option visible |  |
| old option unlocked |  |
| different error message |  |
| loading screen change |  |
| crash/hang/return-to-menu behavior |  |
| log/crash/report evidence |  |
| screenshot/video note |  |
| next action |  |

### Lane E: xsc_review_only

- Package: `import_test_xsc_review`
- Target: `Do not import without explicit approval`
- Purpose: Wrapper review lane

| Field | Result |
| --- | --- |
| content.rpf backup used |  |
| imported package |  |
| Magic RDR reopen/export verification result |  |
| byte compare result |  |
| launch result |  |
| menu change |  |
| new option visible |  |
| old option unlocked |  |
| different error message |  |
| loading screen change |  |
| crash/hang/return-to-menu behavior |  |
| log/crash/report evidence |  |
| screenshot/video note |  |
| next action |  |

