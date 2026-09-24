# Optional full-grid walkthrough extension

This optional interface supports the frontend’s full-solve replay. It supplements the
[agreed solver/UI contract](solver-ui-contract.md); it does not change any of
that contract's required function signatures or return types. Trace helpers are
separate from the core grid-only functions.

## Helpers

```python
solve_full_grid_fc_with_trace(n, box_h, box_w, givens)
solve_full_grid_bc_with_trace(n, box_h, box_w, givens)
```

Each returns a new dictionary:

```python
{
    'grid': {(row, column): value},  # Complete tuple-keyed grid, same as core API.
    'steps': [
        {'conclusion': 'Is1_1_1', 'premises': [], 'reason': 'given'},
        # Further facts, eliminations, and placements from this algorithm's run.
    ],
}
```

The entire result uses Python's tuple-keyed grid format; only `steps` are directly
JSON-compatible. Steps follow the existing trace schema and reason labels.

- The trace and grid come from the **same run of the selected algorithm**.
- Include the original facts and successful deductions supporting the returned
  grid. A trace may omit unrelated deductions. Each conclusion appears once and
  all premises appear earlier.
- Every cell in the returned grid has an `Is` step establishing it. No `Is` or
  `Not` step may contradict the returned grid.
- FC steps must come from the supplied FC algorithm's actual run.
- BC steps must come from the BC run. The trace lists successful deductions,
  not recursive calls, attempted goals, cache lookups, or failed branches.
- Errors, clue preservation, KB stability, and fresh returned objects follow the
  original contract. An incomplete solve raises `ValueError`; this initial
  extension does not expose a partial walkthrough through the exception.
- The existing `solve_full_grid_fc/bc` functions still return **only a grid**.
  Traced helpers should share their inference engine with those functions.

The course integration assumes valid supplied 9×9 puzzles. Both FC APIs run the
supplied FC routine once with an absent query to exhaust its agenda. The grid and
walkthrough come from that pass; candidate checks reuse the collected deductions.
The existing BC trace helper is retained. No extra input-validation layer
is required for this integration.

## Frontend behavior

The UI prefers the matching optional helper and times the whole call, including
trace recording. If the helper is absent or raises `NotImplementedError`, it
calls the corresponding grid-only function and reports that no solve walkthrough
is available. It never constructs an FC walkthrough by running BC afterward.

Replay starts at step 0 with the original clues. **Cell placements** visits each
new `Is` conclusion and includes intervening elimination steps in the replayed
prefix. **All deductions** visits each recorded step, including clue processing.
The displayed board is built from that trace prefix, never from the final grid.
Navigation is independent of the single-cell proof controls. Reset, puzzle
changes, and a new solve clear the walkthrough position.

## Multiple solutions

These Horn rules derive forced values without branching. On a satisfiable puzzle
with multiple completions, differing cells cannot be proved to have one fixed
value, so the full-grid call raises an incomplete-grid `ValueError`. That same
outcome can happen on a uniquely solvable puzzle requiring stronger deduction
rules. These APIs neither count solutions nor distinguish those two cases.
