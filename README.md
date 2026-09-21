# IT5005 Sudoku — Group 23

Live app: [Group 23 - Sudoku Solver](https://it5005-group23-sudoku.streamlit.app)

A shared project for Group 23. The Streamlit frontend supports puzzle selection, full-grid solver controls, targeted queries, and a proof viewer. The backend solver functions are still starter stubs; the conceptual answers remain to be completed.

## Run locally

Use Python 3.12 or newer. Run these commands from this repository's root:

```sh
python3 -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run sudoku_app.py
```

The app loads all five puzzles and shows their original clues. Solve and query actions display a clear unavailable message while the corresponding backend function raises `NotImplementedError`. They connect to the real solver as its implementation arrives; reference solutions are never used as a fallback.

The optional `pl_bc_entails_with_trace` helper enables the tutor view. If only plain backward chaining is ready, the app can display its verdict without a trace. A failed query is described as unproved unless a separate `Not` query establishes that the value is ruled out. See [the solver/UI contract](docs/solver-ui-contract.md) for the agreed formats.

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

Tests use Streamlit's `AppTest` with explicit backend fixtures to exercise solved grids, failed and excluded queries, proof navigation, puzzle resets, and unavailable or malformed backend responses. Fixtures stay under `tests/`; the production app does not import them or read reference solutions for inference. End-to-end integration with real deductions still needs the backend implementation.

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
