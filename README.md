# IT5005 Sudoku — group assignment starter

A shared starting point for four group members. **The assignment is not implemented yet.** The original solver stubs, Streamlit TODOs, and conceptual-answer placeholders are intentionally preserved.

## Run locally

Use Python 3.12 or newer. Run these commands from this repository's root:

```sh
python3 -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run sudoku_app.py
```

The starter currently displays only **Sudoku Solver**. This is expected: solving, puzzle selection, queries, and tutor mode are group implementation tasks. Calling an unimplemented solver function raises `NotImplementedError`.

For the notebook:

```sh
pip install -r requirements-dev.txt
jupyter lab Sudoku_Assignment.ipynb
```

## Deploy on Streamlit Community Cloud

| Field | Value |
| --- | --- |
| Repository | `sbhhbs/IT5005-sudoku` |
| Branch | `main` |
| Main file path | `sudoku_app.py` |
| App URL | Leave blank, or choose an available name such as `it5005-sudoku-sbhhbs` |
| Advanced settings: Python | `3.12` |

Alternatively, paste this file URL into the deployment form:

https://github.com/sbhhbs/IT5005-sudoku/blob/main/sudoku_app.py

Deploy the starter now to verify hosting. Future merges to `main` will update the deployed app. After deployment, record the actual app URL in the notebook's designated section. The sample subdomain above is a suggestion, not a deployed URL.

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
