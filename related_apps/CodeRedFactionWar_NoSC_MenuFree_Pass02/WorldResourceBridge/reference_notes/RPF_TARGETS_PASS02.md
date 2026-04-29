# Pass02 RPF Targets

## First target: tune AI

Archive:

```text
tune_d11generic.rpf
```

Target:

```text
root/tune/ai/game_main.tr
```

Add loose resource candidate:

```text
root/tune/ai/code_red_factionwar_world.tr
```

Reason: the tune-side `game_main.tr` patch is very small and clean.

## Second target: content AI

Archive:

```text
content.rpf
```

Target:

```text
root/content/ai/game_main.tr
```

Add loose resource candidate:

```text
root/content/ai/code_red_factionwar_world.tr
```

Reason: content-side AI has a larger `program Main` route, but it exposes more active human behavior systems.

## Later targets

Population:

```text
tune_d11generic.rpf::root/tune/level/territory/level.pop
```

Traffic:

```text
tune_d11generic.rpf::root/tune/settings/default.traffic
```

These should be merged only after Code RED has a stable DSL merge editor.
