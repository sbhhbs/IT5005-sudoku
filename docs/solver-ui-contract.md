# Group 23: solver-to-UI interface contract

**Status:** Core interface reviewed and accepted before implementation. The optional full-grid walkthrough helpers were added as a later proposal; see [the separate extension](full-grid-trace-extension.md). Their implementation in the local integration backend does not imply Member 2 has accepted that extension.

**Scope:** Member 2 implements the definite knowledge base, inference, full-grid solvers, and trace production in `sudoku_solver.py`. Member 3 implements the Streamlit interface and renders the returned data. The general knowledge base belongs to Member 1 and keeps its existing interface.

The starter function signatures and assignment restrictions remain authoritative. The additional trace helper and the detailed error/mutation behavior below are group integration decisions, not extra requirements quoted from the assignment.

## 1. Initial handoff baseline

This table records the state when the contract was proposed, not current implementation progress. The frontend and general KB have since been implemented; the local Member 2 integration backend is described in section 13.

| Component | State at initial handoff | Integration responsibility |
| --- | --- | --- |
| `puzzles.json` | Provided; five 9×9 puzzles with 3×3 boxes | UI selects a puzzle and converts its givens to Python keys |
| Notebook `load_pool` | Provided | Keep the assignment's loader unchanged |
| `atom`, `Expr`, `PropKB`, `PropDefiniteKB` | Provided | Reuse these representations |
| `pl_fc_entails` | Provided in `logic_.py` | Member 2 calls it; do not edit the library |
| `build_general_kb` | Stub | Member 1; separate from the app's primary solver path |
| `build_definite_kb` | Stub | Member 2 |
| `pl_bc_entails` | Stub | Member 2 |
| `solve_full_grid_fc`, `solve_full_grid_bc` | Stubs | Member 2 |
| `pl_bc_entails_with_trace` | Proposed new helper; not present yet | Member 2, in coordination with Member 3 |
| Streamlit interface | Title, imports, and TODOs | Member 3 |
| GitHub and Streamlit deployment | Set up; updates on `main` have been verified | Member 3 integrates and checks the live app |

Live app: [Group 23 - Sudoku Solver](https://it5005-group23-sudoku.streamlit.app)

## 2. Assignment constraints to preserve

- Implement core solver functions in `sudoku_solver.py`, and import them into the app and notebook. Do not duplicate those functions in the app.
- In `sudoku_solver.py`, import only from the provided `utils.py` and `logic_.py`. Use ordinary built-in dictionaries/lists for this contract; no additional serialization or typing dependency is needed.
- Do not change `utils.py`, `logic_.py`, or `atom`.
- `build_general_kb` returns a `PropKB`; `build_definite_kb` returns a `PropDefiniteKB`. A compatible subclass may be used for indexing or private trace metadata.
- Use only the puzzle's givens for solving and entailment. The reference solution is test data, not an inference input.
- Keep the existing required functions' parameters and return types. Add trace support through the separate helper below.
- Support dimensions supplied to the functions rather than hard-coding 9, 3, or 81 in the interfaces.

## 3. Puzzle data at each boundary

### 3.1 JSON file format

The file has these fields:

```text
{
  "n": integer,
  "box_h": integer,
  "box_w": integer,
  "puzzles": [
    {
      "givens": {"row_column": value, ...},
      "given_count": integer,
      "solution": {"row_column": value, ...}
    },
    ...
  ]
}
```

The example above describes a schema, not literal JSON to parse. For example, the key `"2_7"` means row 2, column 7. The UI can identify a puzzle by its list index; no puzzle ID needs to be passed to a solver.

`given_count` is display metadata. It is not a difficulty rating and is not enough to determine whether the chosen deduction rules can solve a puzzle.

### 3.2 Python solver input

```python
n = 9
box_h = 3
box_w = 3
givens = {(2, 1): 2, (2, 7): 8, (2, 8): 6}
```

This is an illustrative subset of clues, not a complete puzzle specification from the bank.

| Field | Type and meaning |
| --- | --- |
| `n` | Positive Python integer; grid has `n` rows, `n` columns, and values `1..n` |
| `box_h`, `box_w` | Positive Python integers; `box_h * box_w == n` |
| `givens` | Dictionary mapping `(row, column)` tuples to integer values |
| Row and column | Integers in `1..n`; never zero-indexed |
| Cell value | Integer in `1..n` |
| Empty cell | Absent from `givens`; do not encode as `0`, `None`, `""`, or `"."` |

Reject booleans where integers are expected; Python treats `bool` as an integer subclass, but `True` is not a meaningful Sudoku coordinate or value.

Member 3 converts JSON keys once when loading a puzzle:

```python
givens = {
    tuple(int(part) for part in key.split('_')): value
    for key, value in selected_puzzle['givens'].items()
}
```

This is app-side data preparation. Do not pass the whole puzzle object, its `solution`, or `given_count` into the solver.

### 3.3 Solved-grid output

A successful full-grid call returns a new dictionary with the same tuple-key format:

```python
# Complete illustrative 4×4 result, with 2×2 boxes.
{
    (1, 1): 1, (1, 2): 2, (1, 3): 3, (1, 4): 4,
    (2, 1): 3, (2, 2): 4, (2, 3): 1, (2, 4): 2,
    (3, 1): 2, (3, 2): 1, (3, 3): 4, (3, 4): 3,
    (4, 1): 4, (4, 2): 3, (4, 3): 2, (4, 4): 1,
}
```

Required properties:

- Exactly `n * n` cells, including all original givens.
- Exactly the coordinate set `{(r, c): 1 <= r <= n, 1 <= c <= n}`.
- Values in `1..n`; rows, columns, and boxes satisfy Sudoku uniqueness.
- Every original given retains its value.
- Dictionary order is not significant. The UI renders explicitly in row/column order.
- No timing, trace, or status fields mixed into this dictionary.

## 4. Required function interfaces

```python
build_general_kb(n, box_h, box_w, givens) -> PropKB
build_definite_kb(n, box_h, box_w, givens) -> PropDefiniteKB
solve_full_grid_fc(n, box_h, box_w, givens) -> dict
pl_bc_entails(kb, query) -> bool
solve_full_grid_bc(n, box_h, box_w, givens) -> dict
```

These arrows describe return types; they do not prescribe extra imports or annotations in the implementation.

### 4.1 Full-grid calls

```python
solved = solve_full_grid_fc(n, box_h, box_w, givens)
# Or, depending on the user's selection:
solved = solve_full_grid_bc(n, box_h, box_w, givens)
```

Each full-grid function builds its own definite KB from the supplied inputs. The UI does not provide a prebuilt KB to these functions.

Use the supplied `pl_fc_entails` for the forward solver and the group's `pl_bc_entails` for the backward solver. Any internal reuse of inference work must preserve their semantics. No guessing or reading a known solution to fill missing cells.

### 4.2 Targeted entailment call

```python
kb = build_definite_kb(n, box_h, box_w, givens)
query = atom('Is', r, c, v)
entailed = pl_bc_entails(kb, query)
```

- `query` is an atomic `Expr`, not a string, tuple, or arbitrary formula.
- Return the built-in `True` or `False`, not a dictionary, string, or proof object.
- `True` means the definite KB entails the query.
- `False` means the definite KB does not entail the query. It is not an error.
- The core BC function should work on ordinary propositional definite KBs as well, including small examples using atoms such as `A`, `B`, and `C`. Do not rely on Sudoku atom names for the correctness of the inference engine.
- The UI validates Sudoku row/column/value ranges before constructing a query.

## 5. Unsolved grids and error behavior

### 5.1 Full-grid solver cannot establish every cell

**Raise `ValueError` with an explanatory message. Do not return a partial grid as a successful result.**

Example message:

```text
The current Horn rules determined 45 of 81 cells. A complete grid could not be established without stronger reasoning.
```

The wording and exact count are not an API for the UI to parse. Member 3 catches `ValueError` and displays its message.

- Do not fill unresolved cells from the reference solution.
- Do not select an arbitrary candidate when no value is entailed.
- Do not return `None`, `False`, `{}`, or a grid with zeroes as an alternative failure signal.
- If no cells are determined, raise the same kind of exception with an appropriate message.
- An inability to solve using these rules does **not** establish that the Sudoku has no solution. Say that the rules did not establish a complete grid.
- Returning partial progress through a structured exception is outside this initial contract. If needed later, agree on a separate extension.

### 5.2 Invalid input and detected contradictions

Raise `ValueError` for these user/data errors:

| Condition | Expected handling |
| --- | --- |
| Nonpositive/noninteger dimensions or `box_h * box_w != n` | Reject before building rules |
| `givens` is not the expected mapping, or has malformed keys/values | Reject with a useful message |
| Coordinates or values outside `1..n` | Reject |
| Two givens repeat a value in a row, column, or box | Reject |
| Inference encounters contradictory conclusions for a cell | Report a contradiction; do not silently pick the first value |
| A returned full grid would violate Sudoku rules or change a given | Do not return it as a successful result |

Do not add an exhaustive consistency solver merely to validate input. Some inconsistent puzzles have no directly conflicting givens and may remain undetected by these rules. The requirement is to reject directly detectable input conflicts and contradictions actually encountered during inference.

For the generic BC interface, reject malformed non-atomic queries or a KB that is not a valid propositional definite KB with `ValueError`. An ordinary atomic query with no supporting rules/facts returns `False`.

A valid targeted query can still return `True` or `False` even if the entire puzzle cannot be solved. It should not call a full-grid solver first.

`NotImplementedError` is only a temporary starter condition. Member 3 may handle it while developing, but completed solver paths must not raise it.

### 5.3 Caller behavior

```python
try:
    solved = solve_full_grid_bc(n, box_h, box_w, givens)
except NotImplementedError:
    # Temporary development state only.
    show_not_implemented_message()
except ValueError as error:
    show_solver_message(str(error))
else:
    show_solved_board(solved)
```

The `show_*` names are illustrative UI actions, not functions Member 2 needs to supply. Do not turn unexpected programming exceptions into successful results or `False` entailment verdicts.

## 6. Input mutation, KB state, and repeat calls

### 6.1 Treat `givens` as read-only

All KB builders and full-grid solvers must leave the caller's `givens` unchanged, on both success and failure.

- Do not add deductions to the supplied dictionary.
- Do not remove clues or replace their values.
- Do not retain a mutable alias to it that could be changed by later inference. Copy clues if storing them internally.
- Return a fresh solved-grid dictionary. It must not be the same object as `givens`, even if the puzzle was already complete.
- Mutating a returned grid must not affect the original clues, another result, or subsequent solver calls.

This lets the UI reliably style original clues differently from deduced values and reset the board to its initial state.

### 6.2 Keep the logical KB stable during entailment

`pl_bc_entails` and `pl_bc_entails_with_trace` must not change the logical facts/rules in `kb.clauses` as a side effect of answering a query. In particular, do not append proven conclusions to the clauses and then label them as original givens in later traces.

Private indexes and proof caches are allowed, provided that:

- They do not change the Boolean result, including when calls occur in a different order.
- They retain enough provenance to explain cached deductions.
- They do not mix results from different puzzles or KB instances.
- They are invalidated if the KB's clauses change. Per-call caches are a simpler alternative if persistent invalidation is difficult.
- Returned trace dictionaries and lists are fresh snapshots; callers cannot corrupt cached proofs by modifying a previous result.

Member 3 can build a fresh KB for each submitted cell query initially. The UI will not depend on any private attributes added to the KB.

### 6.3 Cycle handling

Both the plain and traced BC calls must terminate on cyclic rule dependencies. A goal appearing on the active proof path is not evidence that it is true.

Do not permanently cache a branch-local cycle failure as a globally disproved proposition: another rule may establish the same goal from facts. Ensure that repeated calls and alternative rule orderings preserve correctness.

## 7. New trace helper

Add this helper to `sudoku_solver.py`:

```python
pl_bc_entails_with_trace(kb, query) -> dict
```

For the app, `kb` comes from `build_definite_kb`, and `query` comes from `atom`. The required `pl_bc_entails(kb, query) -> bool` interface remains unchanged.

Both public functions should share the same internal backward-chaining engine. A plain call returns the Boolean result; a traced call also returns the recorded supporting steps. This is not a request to implement a second independent inference algorithm.

Required result shape:

```text
{
  "query": string,
  "entailed": boolean,
  "steps": list of step objects
}
```

| Field | Required behavior |
| --- | --- |
| `query` | The queried atom's canonical name, e.g. `"Is1_4_4"` |
| `entailed` | Built-in Boolean, equal to `pl_bc_entails(kb, query)` on the same logical KB |
| `steps` | Ordered, self-contained supporting proof, following the rules below |

Use JSON-compatible Python values: strings, booleans, lists, and dictionaries. Do not return `Expr`, `set`, tuple-keyed maps, HTML, Streamlit objects, or exception instances inside the trace.

No file serialization is required in Member 2's code. The format is JSON-compatible so that it is simple to inspect, test, and render.

### 7.1 Step object

```json
{
  "conclusion": "Not1_2_3",
  "premises": ["Is1_1_3"],
  "reason": "row_elimination"
}
```

This is an illustrative implication: row 1 already contains 3 at column 1, so column 2 cannot contain 3. It is not a claimed result for a supplied puzzle.

| Field | Type | Meaning |
| --- | --- | --- |
| `conclusion` | String | Canonical name of the established atom |
| `premises` | List of strings | Exact atoms supporting the inference, or an empty list for a fact |
| `reason` | String | One of the values in the next table |

For a non-fact step, the logical rule is fully represented by `premises ==> conclusion`. A separate human-readable sentence, rule string, or source-code location is not required. Member 3 writes the UI wording.

### 7.2 Reason values

| `reason` | Meaning and required evidence |
| --- | --- |
| `given` | An original input clue; `premises` is empty and conclusion is the corresponding `Is` atom |
| `cell_elimination` | A known `Is(r,c,u)` rules out a different value `v` in that same cell |
| `row_elimination` | A known `Is(r,c,v)` rules out `v` in another cell of the same row |
| `column_elimination` | A known `Is(r,c,v)` rules out `v` in another cell of the same column |
| `box_elimination` | A known value rules out that value in another cell of its box |
| `last_candidate` | All other `n-1` values have explicit `Not(r,c,u)` premises, establishing `Is(r,c,v)` |
| `rule_application` | Generic fallback for an additional valid definite rule not covered above |

If a peer shares both a row/column and a box, choose one valid explanation. The implementation may record which rule was used or apply a consistent classification order. The UI must not depend on a particular choice among equally valid reasons.

Private KB metadata may retain dimensions, original givens, and rule labels for trace production. This stays internal to Member 2's implementation; Member 3 consumes only this documented result.

Do not infer `box_elimination` using a hard-coded 3×3 box size. Use the dimensions supplied when building the KB.

The `rule_application` fallback supports future extensions or generic KB facts. A zero-premise fact that was not an original Sudoku clue must not be labelled `given`. In a 1×1 puzzle, `last_candidate` may legitimately have zero elimination premises.

### 7.3 Symbol naming

Use the exact names produced by `atom`:

```python
atom('Is', 3, 2, 4)   # Is3_2_4
atom('Not', 3, 2, 4)  # Not3_2_4
```

The prefix is followed immediately by the row, then underscore-separated column and value. Do not add an underscore after `Is`/`Not`, spaces, or zero-based coordinates.

`Not3_2_4` is an ordinary positive atom meaning “this value has been ruled out.” It is distinct from the logical negation expression `~Is3_2_4`.

The UI can parse names by removing the `Is` or `Not` prefix and splitting the remainder on underscores. This supports multi-digit coordinates too; do not use fixed character offsets for each number.

## 8. Trace ordering and truthfulness

The returned list is a supporting proof of the query, not necessarily a transcript of every attempted search branch.

Required invariants:

1. Every step comes from an original fact or a rule actually justified during inference. Record provenance while proving atoms; do not manufacture a plausible explanation after consulting the reference solution.
2. Every premise appears as the conclusion of an earlier step in this list. Include required original givens explicitly.
3. List each conclusion once. Shared supporting deductions can be referenced by multiple later steps.
4. For `entailed=True`, the final step establishes the exact queried atom.
5. A query that is itself a given has a one-step proof.
6. Do not include unsupported guesses, failed branches as successful steps, self-supporting cycles, or unrelated deductions.
7. A cached proof is acceptable if its original supporting facts and rules remain valid and are included in the returned list.
8. Different valid rule orderings may produce different proofs. Tests should validate the proof's meaning, not require one exact list unless deliberately using a fixed fixture.

Member 3 will present this as “Steps supporting the answer.” The UI should not claim it is the complete chronological execution log. A future search/debug event stream would need a separate format for goals attempted, branches rejected, and cycle encounters.

## 9. Complete trace examples

### 9.1 Successful last-candidate query

For this illustrative 4×4 puzzle fragment:

```python
givens = {(1, 1): 1, (1, 2): 2, (1, 3): 3}
kb = build_definite_kb(4, 2, 2, givens)
query = atom('Is', 1, 4, 4)
result = pl_bc_entails_with_trace(kb, query)
```

One valid result is:

```json
{
  "query": "Is1_4_4",
  "entailed": true,
  "steps": [
    {"conclusion": "Is1_1_1", "premises": [], "reason": "given"},
    {"conclusion": "Not1_4_1", "premises": ["Is1_1_1"], "reason": "row_elimination"},
    {"conclusion": "Is1_2_2", "premises": [], "reason": "given"},
    {"conclusion": "Not1_4_2", "premises": ["Is1_2_2"], "reason": "row_elimination"},
    {"conclusion": "Is1_3_3", "premises": [], "reason": "given"},
    {"conclusion": "Not1_4_3", "premises": ["Is1_3_3"], "reason": "row_elimination"},
    {
      "conclusion": "Is1_4_4",
      "premises": ["Not1_4_1", "Not1_4_2", "Not1_4_3"],
      "reason": "last_candidate"
    }
  ]
}
```

This fragment is sufficient for the targeted query. It does not need to determine the entire 4×4 grid.

### 9.2 Query is already given

```json
{
  "query": "Is1_1_1",
  "entailed": true,
  "steps": [
    {"conclusion": "Is1_1_1", "premises": [], "reason": "given"}
  ]
}
```

### 9.3 Query is not entailed

Using the same fragment, querying `Is1_4_1` returns:

```json
{
  "query": "Is1_4_1",
  "entailed": false,
  "steps": []
}
```

For this initial contract, all non-entailed queries return an empty supporting-proof list. The UI displays “The current rules do not establish this value.” It must not present this empty list as a proof of impossibility.

### 9.4 Optional explanation that a value is ruled out

After an `Is` query returns `False`, the UI may make a separate call:

```python
exclusion = pl_bc_entails_with_trace(kb, atom('Not', 1, 4, 1))
```

For this fragment, a valid result is:

```json
{
  "query": "Not1_4_1",
  "entailed": true,
  "steps": [
    {"conclusion": "Is1_1_1", "premises": [], "reason": "given"},
    {"conclusion": "Not1_4_1", "premises": ["Is1_1_1"], "reason": "row_elimination"}
  ]
}
```

Now the UI can say “This value is ruled out” and display that separate proof. Keep the original `Is` verdict and the `Not` proof distinct. If neither is entailed, the status is undetermined by these rules. The helper itself does not silently change the query or combine the two calls.

## 10. App integration and timing

### 10.1 Whole-grid solve

```python
# App code; time is imported in sudoku_app.py, not added to the solver imports.
start = time.perf_counter()
solved = solve_full_grid_fc(n, box_h, box_w, givens)
elapsed_seconds = time.perf_counter() - start
```

Time the full call, including KB construction, for both algorithms. Do not include board rendering. The app owns the displayed timing; Member 2 does not add a timing field to solver results.

Avoid reporting a cached whole-grid UI result's lookup time as solver runtime. Benchmarks should clearly state whether KB construction or reusable proof caches are included.

### 10.2 Targeted query and tutor

```python
kb = build_definite_kb(n, box_h, box_w, givens)
query = atom('Is', r, c, v)
result = pl_bc_entails_with_trace(kb, query)
# result['entailed'] supplies the verdict.
# result['steps'] supplies tutor cards and board highlights.
```

The traced helper must use the same core BC implementation as the required plain function. If the app calls the plain function separately to meet an explicit verification/check path, its verdict must agree. There should be no independent UI-side entailment algorithm.

The UI keeps its original givens separate from any solved board. Query reasoning uses the original givens, not a previously displayed solution inserted as extra clues.

Member 3 maps reason codes and symbol coordinates into sentences, highlights, and expandable cards. Member 2 returns data, not presentation markup. Do not use `eval` to decode returned symbol strings.

## 11. Development fixtures while Member 2 is implementing

Member 3 can build the UI now using the real puzzle inputs and separate test fixtures for results/proofs.

- Keep fixtures in tests or an explicitly labelled development preview. They are not alternate implementations of the required solver functions.
- The provided `solution` may be used as a test expectation or a clearly labelled reference-board preview. It must not satisfy a production solve or entailment request.
- Use the complete 4×4 proof above as an illustrative tutor fixture, clearly distinct from an actual live solver result.
- Handle `NotImplementedError` visibly during development; do not silently substitute a reference solution and show “solved.”
- Full-grid solving and positive/negative verdict rendering can be developed without waiting for trace support.
- Agree on this trace schema before connecting tutor mode. If the schema changes, update this document and both producer/consumer code together.

## 12. Acceptance checklist for Member 2 and integration

### Data and full-grid behavior

- [ ] The existing signatures and return types are preserved.
- [ ] Valid 4×4/2×2 and 9×9/3×3 inputs use the same interface; no hard-coded dimensions.
- [ ] Returned successful grids contain every cell, preserve givens, and satisfy Sudoku constraints.
- [ ] All five supplied puzzles are checked against the reference solutions using both full-grid solvers.
- [ ] A puzzle unresolved by the current rules raises `ValueError` rather than returning a partial or guessed grid.
- [ ] Invalid dimensions, out-of-range data, and directly conflicting givens are rejected.
- [ ] `givens` is unchanged after successful, unsuccessful, and invalid-input calls.
- [ ] Returned grids are separate objects; mutating one does not corrupt clues or subsequent results.

### Inference behavior

- [ ] BC returns `True` for every correct cell/value and `False` for every incorrect candidate in the supplied solvable puzzles.
- [ ] BC and supplied FC entailment agree on the same definite KB, including negative queries.
- [ ] A valid unprovable atom returns `False`, without requiring a solved full grid.
- [ ] Unsupported cycles terminate with `False`; cycles with an independent factual proof can still succeed.
- [ ] Query order and repeated calls do not change logical answers.
- [ ] Plain and traced queries leave the KB's logical clauses unchanged.

### Trace behavior

- [ ] The trace verdict equals the plain BC verdict.
- [ ] Top-level and step fields follow this document and contain JSON-compatible values.
- [ ] A given query returns its one-step proof; an unproved query returns `False` and `[]`.
- [ ] Every premise is established earlier in the trace, and a successful query is the final conclusion.
- [ ] Each non-fact step is justified by an actual rule in the KB.
- [ ] Reason labels match their premises, conclusion, and puzzle geometry.
- [ ] Facts and cached deductions are distinguished correctly.
- [ ] Mutating a returned trace does not corrupt later traces or cached proof state.
- [ ] Any explanation of an excluded value is a separate proven `Not` query, not an assumption based on `Is=False`.

### Handoff

- [ ] Member 2 and Member 3 agree on the function name and schema before tutor integration.
- [ ] Member 2 supplies at least one real successful proof, one direct-given proof, and one non-entailed result for integration checks.
- [ ] Member 3 verifies the UI against both live results and expected error behavior.

The solver implementation can choose its indexes, search order, memoization, and private metadata. Those choices stay internal as long as the interfaces, logical meaning, and behavior above hold.


## 13. Local integration implementation and later additions

The local backend written for frontend integration testing follows the core interfaces above. That backend and its tests are currently uncommitted and are not included in this branch's published code. It remains separate from Member 2's reviewed handoff; this section records implementation choices, not additional obligations for Member 2.

### Additional public APIs

Only these two public helpers extend this agreement:

```python
solve_full_grid_fc_with_trace(n, box_h, box_w, givens)
solve_full_grid_bc_with_trace(n, box_h, box_w, givens)
# Each returns {'grid': complete_tuple_keyed_grid, 'steps': ordered_steps}.
```

They support **Follow the solve** and are specified in [the optional full-grid extension](full-grid-trace-extension.md). The frontend falls back to the existing grid-only solver if the matching helper is absent or raises `NotImplementedError`. The single-cell `pl_bc_entails_with_trace` helper was already part of the accepted core agreement in section 7.

Single-cell traces contain only the supporting proof and end with the query. Full-grid traces contain the selected algorithm's successful deductions for the whole run and have no single final-query requirement. Both use the same step fields and reason labels. Neither is a search-event log. Incomplete full-grid calls still raise `ValueError`; they do not return partial grids or partial walkthroughs. No uniqueness checking or solution enumeration has been added.

### Private implementation choices

- A compatible `PropDefiniteKB` subclass stores rule labels, premise indexes, and proof metadata. The frontend does not access those private fields.
- FC calls the unchanged supplied `pl_fc_entails` once with an absent probe atom to exhaust its agenda. The KB's premise lookup observes processed atoms and records provenance; it does not insert deductions into `kb.clauses`.
- BC expands dependencies backward from each goal, then propagates proven premises through suspended rules until that dependency set reaches a fixed point. This tabled implementation handles cycles and shares proven subgoals across queries; it is not a simple recursive DFS. Clause changes invalidate the cache. A query in a connected Sudoku KB can reach most of its rules.
- Full-grid BC queries every cell/value, so it does not hide conflicting conclusions by accepting the first successful value.

Member 2 can use different private indexes or proof-search strategies while preserving the public behavior. Notebook performance comparisons should explain that this FC implementation exhausts its agenda once, while BC reuses proof tables within a full-grid solve. UI timings include KB construction and, when the optional helper is used, trace recording; they are not inference-only benchmarks.

### Verification scope

The local `tests/test_definite_solver.py` checks both solvers against all five supplied solutions, positive and negative BC candidates, proof validity, generic Horn cycles, cache invalidation, fresh return objects, input preservation, invalid/incomplete inputs, rectangular boxes, and real frontend integration. It also checks the optional full-grid traces separately. Passing these checks is integration evidence, not a substitute for Member 2's review or the notebook's assignment answers. The checklist above remains available for the final handoff review.
