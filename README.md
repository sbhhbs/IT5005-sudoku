# IT5005 Sudoku — Group 23

Live app: [Group 23 - Sudoku Solver](https://it5005-group23-sudoku.streamlit.app)

A shared project for Group 23. The Streamlit frontend supports puzzle selection, full-grid solver controls, targeted queries, a proof viewer, and a knowledge-base inspector. The general and definite knowledge bases, FC/BC solvers, cell proofs, and both solve walkthroughs are implemented. This course app assumes valid supplied 9×9 puzzle inputs. The conceptual answers remain to be completed.

## Run locally

Use Python 3.12 or newer. Run these commands from this repository's root:

```sh
python3 -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run sudoku_app.py
```

The app loads all five puzzles and shows their original clues on a full-width board above three tabs: **Solve the grid** (solver and walkthrough), **Ask about cell** (query and proof), and **Knowledge base explore** (clauses and filters). Puzzle selection and Reset stay above the tabs. Click any board cell to highlight it and set the row/column in **Ask about one cell**; clicking a filled cell also copies its value. Editing the query coordinates updates the same selection. Selecting a different cell clears the previous query result without running inference. **Reset** or changing puzzles clears the selection and highlight; KB cell focus stays disabled until a cell is selected again. Solve and query actions display a clear unavailable message while the corresponding backend function raises `NotImplementedError`. They connect to the real solver as its implementation arrives; reference solutions are never used as a fallback.

After **Solve puzzle**, **Follow the solve** replays the selected algorithm's actual successful deductions. Start at the original clues, use Previous/Next or the slider, and switch between **Cell placements** and **All deductions**. The replay board is reconstructed from the trace prefix, not copied from the final solution. Full-grid traces use [optional extension helpers](docs/full-grid-trace-extension.md), preserving the original grid-only APIs. Without those helpers, solving still works and the app reports that no walkthrough is available.

These solvers never choose arbitrarily between multiple solutions. They report an incomplete grid if the Horn rules cannot finish; that alone does not distinguish ambiguity from a unique puzzle needing stronger rules.

The optional `pl_bc_entails_with_trace` helper enables the single-cell tutor view. If only plain backward chaining is ready, the app can display its verdict without a trace. A failed query is described as unproved unless a separate `Not` query establishes that the value is ruled out. See [the solver/UI contract](docs/solver-ui-contract.md) for the agreed formats.

The general builder was adapted from `Serim_sudoku.zip`, with corrected box traversal for rectangular grids. The supplied `logic_.py` and `utils.py` are unchanged. The archive's definite-KB/FC/BC implementation and notebook answers/outputs were not imported; those remain separate work, and its experiment outputs used different support libraries.

### Inspect the knowledge base

Under **Explore the knowledge base**, choose **General / CNF** or **Definite / Horn**, then generate the selected puzzle's KB. The inspector shows actual stored clauses, symbol/fact counts, a case-insensitive search, 50 clauses per page, and a download of all clauses. Filter by **Fact**, cell-value constraints, row/column/box uniqueness, or Horn last-candidate rules. **Focus on current selected cell** restricts the view to clauses that explicitly mention the highlighted board cell; changing selection does not rebuild the KB. Multiple types are combined with OR, then intersected with the cell focus and text search. A constraint can carry both a row/column and a box tag because it applies to both; stored duplicates remain visible. Expand **Explain a displayed clause** for its plain-language meaning. Downloads always include the complete KB regardless of filters. Definite rules can be viewed as implications or converted to equivalent CNF with the provided logic library. The original formulas before `PropKB.tell` converts them are not retained, so the app does not reconstruct them.

General and definite are knowledge representations. Resolution and truth-table checking operate on the general KB; the full-grid app uses FC/BC with the definite KB. The inspector builds and displays rules without invoking inference. Run the assignment's bounded resolution/model-checking experiments in the notebook, since the supplied algorithms are impractical on the full 9×9 grid. An unfinished builder shows an unavailable message, not sample clauses.

For the notebook:

```sh
pip install -r requirements-dev.txt
jupyter lab Sudoku_Assignment.ipynb
```

## Frontend verification

After installing `requirements-dev.txt`, run:

```sh
python -m pytest -q
```

General-KB tests check the supplied solutions against all generated clauses, rectangular boxes, inference on a small grid, input preservation, and the app's real CNF generation.

Frontend tests use Streamlit's `AppTest` with explicit backend fixtures to exercise solved grids, failed and excluded queries, single-cell proof navigation, full-solve replay with optional trace fixtures, puzzle resets, and unavailable or malformed backend responses. Fixtures stay under `tests/`; the production app does not import them or read reference solutions for inference. Focused integration tests check the FC walkthrough against all five supplied solutions and verify that the frontend can replay it.

The app resolves `puzzles.json` relative to its own file, so it also runs when launched from another working directory. For the repository's theme settings, launch from the repository root as shown above.

## Deploy on Streamlit Community Cloud

| Field | Value |
| --- | --- |
| Repository | `sbhhbs/IT5005-sudoku` |
| Branch | `main` |
| Main file path | `sudoku_app.py` |
| App URL | [https://it5005-group23-sudoku.streamlit.app](https://it5005-group23-sudoku.streamlit.app) |
| Advanced settings: Python | `3.12` |

Alternatively, paste this file URL into the deployment form:

https://github.com/sbhhbs/IT5005-sudoku/blob/main/sudoku_app.py

The starter is deployed at the URL above, which is also recorded in the notebook. Streamlit tracks `main`; pushes and merged pull requests to that branch should update the app automatically.

## Git collaboration

The owner can invite teammates as collaborators for push access. Public visibility alone gives read/fork access, not push access.

Use a separate branch per task and open pull requests into `main`. Coordinate edits to shared files, and agree on responsibilities as a group before starting implementation.

## Assignment rules and final submission

Read `Sudoku_Assignment.pdf` for full requirements and `StreamlitDeploymentGuide.pdf` for the supplied deployment guide.

- Use the provided `logic_.py` and `utils.py`; do not edit either.
- Import only from these two modules in `sudoku_solver.py`.
- Keep core solver functions in `sudoku_solver.py`; import them in the notebook and app, without duplication.
- Use puzzle `givens` for inference. The supplied `solution` is for verification only.
- Document the code and ensure the completed notebook/app execute without errors.
- Fill in the **group number, student names, student IDs, and actual contributions** in the notebook before submission. Because this repository is public, the roster is blank; fill student IDs in the final local submission copy unless the group intends to publish them.
- Run required notebook cells, retain outputs, answer all five conceptual questions, and insert the actual deployed app URL.
- Submit only `Sudoku_Assignment.ipynb`, `sudoku_solver.py`, and `sudoku_app.py`, zipped inside a folder named for your group. The support files, PDFs, and repository setup files are needed for development but are not submission deliverables.
