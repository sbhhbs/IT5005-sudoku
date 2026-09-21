"""Group 23 Streamlit UI. Inference remains in sudoku_solver.py.

Run from any working directory with: streamlit run /path/to/sudoku_app.py
Test fixtures live under tests/ and are never substituted for solver results.
"""

import html
import json
from pathlib import Path
import re
import time

import streamlit as st
import sudoku_solver
from logic_ import PropKB, PropDefiniteKB, Expr, prop_symbols, to_cnf, conjuncts, disjuncts
from sudoku_solver import (
    atom, build_definite_kb, build_general_kb, solve_full_grid_fc,
    solve_full_grid_bc, pl_bc_entails,
)


STYLE = """
<style>
.stApp {background:#faf9f6; color:#243d33;}
.block-container {max-width:1120px; padding-top:2.7rem; padding-bottom:2rem;}
h1,h2,h3 {color:#243d33; letter-spacing:-.035em;}
.eyebrow {color:#537165; font:600 12px/1.5 sans-serif; letter-spacing:.16em; margin-bottom:10px;}
.board-wrap {width:100%; max-width:540px; margin:12px auto;}
.sudoku {width:100%; table-layout:fixed; border-collapse:collapse;}
.sudoku th {background:#faf9f6; color:#698173; font:500 12px/1.5 sans-serif; text-align:center; height:26px;}
.sudoku td {border:1px solid #d6dfd6; text-align:center; height:clamp(30px, 4vw, 49px); font:550 22px/1.15 sans-serif; color:#197352;}
.sudoku td {background:white;}
.sudoku td:first-of-type {border-left:2px solid #416152;}
.sudoku tbody tr:first-child td {border-top:2px solid #416152;}
.sudoku td.given {background:#eef2e9; color:#243d33; font-weight:750;}
.sudoku td.target {background:#ffe9ae; box-shadow:inset 0 0 0 2px #b88b24; color:#594409;}
.sudoku td.support {background:#dceee7; box-shadow:inset 0 0 0 1px #7bad98;}
.board-legend {color:#597165; text-align:center; font-size:13px; line-height:1.8; margin:12px 0 18px;}
.board-legend b {font-weight:700;}
.st-key-board_grid {max-width:540px; margin:12px auto; gap:0;}
.st-key-board_grid [data-testid="stVerticalBlock"] {gap:0;}
.st-key-board_grid [data-testid="stHorizontalBlock"] {gap:0; flex-wrap:nowrap;}
.st-key-board_grid [data-testid="stColumn"] {min-width:0 !important;}
.st-key-board_grid button {width:100%; min-height:0; height:clamp(30px,4vw,49px); padding:0;
 border:1px solid #d6dfd6; border-radius:0; background:white; color:#197352;}
.st-key-board_grid button p {font-size:21px; font-weight:600;}
.st-key-board_grid button:hover {background:#e4eee7; border-color:#416152;}
.st-key-board_grid button:focus-visible {outline:3px solid #197352; outline-offset:-4px;}
.grid-index {text-align:center; color:#698173; font:500 12px/1.5 sans-serif; padding:6px 0;}
@media(max-width:600px) {
 .block-container {padding-top:1.3rem;}
 .sudoku td {height:33px; font-size:18px;}
}
</style>
"""

REASON_TITLES = {
    'given': 'Start with a clue',
    'cell_elimination': 'One value per cell',
    'row_elimination': 'Check the row',
    'column_elimination': 'Check the column',
    'box_elimination': 'Check the box',
    'last_candidate': 'One candidate remains',
    'rule_application': 'Apply a logical rule',
}


@st.cache_data(show_spinner=False)
def load_puzzles():
    """Load app inputs only; the reference solutions are never exposed to UI code."""
    raw = json.loads(Path(__file__).with_name('puzzles.json').read_text())
    puzzles = []
    for puzzle in raw['puzzles']:
        givens = {tuple(map(int, key.split('_'))): value
                  for key, value in puzzle['givens'].items()}
        puzzles.append({'givens': givens, 'given_count': len(givens)})
    return raw['n'], raw['box_h'], raw['box_w'], puzzles


def parse_symbol(name, n):
    """Decode the contract's atom names without evaluating strings."""
    match = re.fullmatch(r'(Is|Not)([1-9][0-9]*)_([1-9][0-9]*)_([1-9][0-9]*)', name) if isinstance(name, str) else None
    if not match:
        raise ValueError('The solver returned an invalid proof symbol.')
    prefix = match[1]
    r, c, v = map(int, match.groups()[1:])
    if not all(1 <= number <= n for number in (r, c, v)):
        raise ValueError('A proof step refers to a cell or value outside this puzzle.')
    return prefix, r, c, v


def validate_grid(grid, givens, n, box_h, box_w):
    """Check the UI boundary; do not infer or fill any values here."""
    cells = {(r, c) for r in range(1, n + 1) for c in range(1, n + 1)}
    if not isinstance(grid, dict) or set(grid) != cells:
        raise ValueError('The solver did not return a complete grid. No partial solution has been displayed.')
    if any(not isinstance(cell, tuple) or any(type(i) is not int for i in cell)
           for cell in grid):
        raise ValueError('The solver returned invalid cell coordinates.')
    if any(type(v) is not int or not 1 <= v <= n for v in grid.values()):
        raise ValueError('The solver returned an invalid cell value.')
    if any(grid[cell] != value for cell, value in givens.items()):
        raise ValueError('The solver result changed an original clue.')
    units = [[grid[r, c] for c in range(1, n + 1)] for r in range(1, n + 1)]
    units += [[grid[r, c] for r in range(1, n + 1)] for c in range(1, n + 1)]
    units += [[grid[r, c] for r in range(top, top + box_h)
               for c in range(left, left + box_w)]
              for top in range(1, n + 1, box_h)
              for left in range(1, n + 1, box_w)]
    if any(set(unit) != set(range(1, n + 1)) for unit in units):
        raise ValueError('The solver result violates a row, column, or box constraint.')
    return dict(grid)


def validate_trace(result, query, n, givens):
    """Validate shape/order and take a fresh snapshot; the backend proves the rules."""
    if (not isinstance(result, dict) or result.get('query') != str(query)
            or type(result.get('entailed')) is not bool
            or not isinstance(result.get('steps'), list)):
        raise ValueError('The solver returned an unsupported reasoning-trace format.')
    if not result['entailed'] and result['steps']:
        raise ValueError('An unproved query must not include a successful proof.')
    seen, steps = set(), []
    for step in result['steps']:
        if not isinstance(step, dict):
            raise ValueError('The solver returned an invalid proof step.')
        conclusion, premises, reason = (step.get(key) for key in ('conclusion', 'premises', 'reason'))
        prefix, r, c, v = parse_symbol(conclusion, n)
        if not isinstance(reason, str) or not isinstance(premises, list):
            raise ValueError('A proof step is missing its premises or reason.')
        for premise in premises:
            parse_symbol(premise, n)
        if conclusion in seen or any(premise not in seen for premise in premises):
            raise ValueError('The proof is missing an earlier supporting step or repeats a conclusion.')
        if reason == 'given' and (premises or prefix != 'Is' or givens.get((r, c)) != v):
            raise ValueError('The proof labels a deduction as an original clue.')
        seen.add(conclusion)
        steps.append({'conclusion': conclusion, 'premises': list(premises), 'reason': reason})
    if result['entailed'] and (not steps or steps[-1]['conclusion'] != str(query)):
        raise ValueError('The proof does not establish the requested value.')
    return {'query': str(query), 'entailed': result['entailed'], 'steps': steps}


def query_with_optional_trace(kb, query, n, givens):
    """Allow core BC to arrive before its optional trace helper."""
    traced = getattr(sudoku_solver, 'pl_bc_entails_with_trace', None)
    if callable(traced):
        try:
            return validate_trace(traced(kb, query), query, n, givens), True
        except NotImplementedError:
            pass
    verdict = pl_bc_entails(kb, query)
    if type(verdict) is not bool:
        raise ValueError('The solver must return True or False for a cell query.')
    return {'query': str(query), 'entailed': verdict, 'steps': []}, False


def check_cell(n, box_h, box_w, givens, r, c, v):
    """Ask about the original clues; optionally get a separate exclusion proof."""
    started = time.perf_counter()
    kb = build_definite_kb(n, box_h, box_w, dict(givens))
    positive, trace_available = query_with_optional_trace(kb, atom('Is', r, c, v), n, givens)
    exclusion = None
    if not positive['entailed'] and trace_available:
        try:
            negative, _ = query_with_optional_trace(kb, atom('Not', r, c, v), n, givens)
            if negative['entailed']:
                exclusion = negative
        except NotImplementedError:
            # Exclusion explanations can arrive after the core Is-query path.
            pass
    return {'cell': (r, c, v), 'positive': positive, 'exclusion': exclusion,
            'trace_available': trace_available, 'elapsed': time.perf_counter() - started}


def solve_with_optional_trace(algorithm, n, box_h, box_w, givens):
    """Prefer a trace from this same solve; retain the agreed grid-only fallback."""
    name = 'solve_full_grid_fc' if algorithm == 'Forward chaining' else 'solve_full_grid_bc'
    traced = getattr(sudoku_solver, name + '_with_trace', None)
    if callable(traced):
        try:
            result = traced(n, box_h, box_w, dict(givens))
        except NotImplementedError:
            pass
        else:
            if not isinstance(result, dict) or not isinstance(result.get('steps'), list) or not result['steps']:
                raise ValueError('The solver returned an invalid full-grid trace.')
            grid = validate_grid(result.get('grid'), givens, n, box_h, box_w)
            last = result['steps'][-1]
            if not isinstance(last, dict):
                raise ValueError('The solver returned an invalid full-grid trace step.')
            prefix, r, c, v = parse_symbol(last.get('conclusion'), n)
            proof = validate_trace({'query': str(atom(prefix, r, c, v)), 'entailed': True,
                                    'steps': result['steps']}, atom(prefix, r, c, v), n, givens)
            placed = {}
            for step in proof['steps']:
                prefix, r, c, v = parse_symbol(step['conclusion'], n)
                if (prefix == 'Is') != (grid[r, c] == v):
                    raise ValueError('The solve trace contradicts the returned grid.')
                if prefix == 'Is':
                    placed[r, c] = v
            if placed != grid:
                raise ValueError('The solve trace does not establish every returned cell.')
            return grid, proof['steps']
    solver = solve_full_grid_fc if algorithm == 'Forward chaining' else solve_full_grid_bc
    return validate_grid(solver(n, box_h, box_w, dict(givens)), givens, n, box_h, box_w), None


def statement(name, n):
    prefix, r, c, v = parse_symbol(name, n)
    return f'Row {r}, column {c} {"cannot be" if prefix == "Not" else "is"} {v}'


def explain_step(step, n):
    """Turn structured evidence into text, with a safe generic fallback."""
    conclusion, premises, reason = step['conclusion'], step['premises'], step['reason']
    prefix, r, c, v = parse_symbol(conclusion, n)
    if reason == 'given':
        return f'{statement(conclusion, n)}. This is an original clue.'
    if reason == 'last_candidate' and prefix == 'Is':
        excluded = [parse_symbol(p, n) for p in premises]
        if (len(excluded) == n - 1
                and all(p == 'Not' and (rr, cc) == (r, c) for p, rr, cc, _ in excluded)
                and {vv for _, _, _, vv in excluded} == set(range(1, n + 1)) - {v}):
            return (f'{statement(conclusion, n)}. All other values have been ruled out, '
                    f'so {v} is the only remaining candidate.')
    if prefix == 'Not' and len(premises) == 1:
        source_prefix, sr, sc, sv = parse_symbol(premises[0], n)
        if source_prefix == 'Is':
            if reason == 'cell_elimination' and (sr, sc) == (r, c) and sv != v:
                return f'{statement(conclusion, n)}, because this cell already contains {sv}.'
            if reason == 'row_elimination' and sr == r and sc != c and sv == v:
                return f'{statement(conclusion, n)}, because row {r} already contains {v} in column {sc}.'
            if reason == 'column_elimination' and sc == c and sr != r and sv == v:
                return f'{statement(conclusion, n)}, because column {c} already contains {v} in row {sr}.'
            if reason == 'box_elimination' and sv == v:
                return f'{statement(conclusion, n)}, because its box already contains {v} at row {sr}, column {sc}.'
    support = '; '.join(statement(p, n).lower() for p in premises)
    return (f'{statement(conclusion, n)} follows from the rule supported by: {support}.'
            if support else f'{statement(conclusion, n)} is a fact in the knowledge base.')


def board_html(values, givens, n, box_h, box_w, target=None, support=(), label='Sudoku board'):
    """Accessible table with box boundaries and text labels for cell states."""
    rows = []
    for r in range(1, n + 1):
        cells = []
        for c in range(1, n + 1):
            value = values.get((r, c), '')
            classes = []
            state = 'empty'
            if (r, c) in givens:
                classes.append('given')
                state = 'given'
            elif value != '':
                state = 'deduced'
            if (r, c) == target:
                classes.append('target')
                state += ', selected cell'
            elif (r, c) in support:
                classes.append('support')
                state += ', supporting cell'
            border = ('border-right:2px solid #416152;' if c % box_w == 0 else '')
            border += ('border-bottom:2px solid #416152;' if r % box_h == 0 else '')
            accessible = f'Row {r}, column {c}: {value if value != "" else "empty"} ({state})'
            cells.append(f'<td class="{" ".join(classes)}" style="{border}" '
                         f'aria-label="{html.escape(accessible)}">{html.escape(str(value))}</td>')
        rows.append(f'<tr><th scope="row">{r}</th>' + ''.join(cells) + '</tr>')
    headers = '<th aria-label="Row and column numbers"></th>' + ''.join(
        f'<th scope="col">{c}</th>' for c in range(1, n + 1))
    return ('<div class="board-wrap"><table class="sudoku" aria-label="' + html.escape(label)
            + f'"><colgroup><col style="width:26px"><col span="{n}"></colgroup>'
            + '<thead><tr>' + headers + '</tr></thead><tbody>'
            + ''.join(rows) + '</tbody></table></div>')


def clear_results():
    """Clear puzzle-dependent state before widgets are reconstructed."""
    for key in ('solution_result', 'query_result', 'solve_feedback', 'query_feedback',
                'query_row', 'query_col', 'query_value', 'proof_step', 'selected_cell',
                'solve_walk_step', 'solve_walk_mode'):
        st.session_state.pop(key, None)
    clear_kb()


def clear_kb():
    """A KB snapshot belongs to one puzzle and one representation."""
    for key in ('kb_result', 'kb_feedback', 'kb_search', 'kb_page', 'kb_notation', 'kb_types', 'kb_focus', 'kb_explain'):
        st.session_state.pop(key, None)


def clear_query():
    for key in ('query_result', 'query_feedback', 'proof_step'):
        st.session_state.pop(key, None)


def select_cell(r, c, value=None):
    """One selection drives the board, query coordinates, and KB focus."""
    st.session_state.selected_cell = (r, c)
    st.session_state.query_row = r
    st.session_state.query_col = c
    if value is not None:
        st.session_state.query_value = value
    clear_query()
    reset_kb_page()


def query_coordinates_changed():
    r, c = st.session_state.query_row, st.session_state.query_col
    select_cell(r, c)


def render_selectable_board(values, givens, n, box_h, box_w):
    """Native buttons retain keyboard support and update state without navigation."""
    styles = []
    with st.container(key='board_grid'):
        columns = st.columns([0.5] + [1] * n)
        for c in range(1, n + 1):
            columns[c].html(f'<div class="grid-index">{c}</div>')
        for r in range(1, n + 1):
            columns = st.columns([0.5] + [1] * n)
            columns[0].html(f'<div class="grid-index">{r}</div>')
            for c in range(1, n + 1):
                value = values.get((r, c))
                key = f'cell_{r}_{c}'
                rules = []
                if (r, c) in givens:
                    rules.append('background:#eef2e9;color:#243d33;')
                if (r, c) == st.session_state.selected_cell:
                    rules.append('background:#ffe9ae;box-shadow:inset 0 0 0 2px #b88b24;color:#594409;')
                if c == 1:
                    rules.append('border-left:2px solid #416152;')
                if r == 1:
                    rules.append('border-top:2px solid #416152;')
                if c % box_w == 0:
                    rules.append('border-right:2px solid #416152;')
                if r % box_h == 0:
                    rules.append('border-bottom:2px solid #416152;')
                styles.append(f'.st-key-{key} button {{' + ''.join(rules) + '}')
                columns[c].button(str(value) if value is not None else '·', key=key,
                                  help=f'Select row {r}, column {c}' + (f' · value {value}' if value else ' · empty'),
                                  use_container_width=True, on_click=select_cell, args=(r, c, value))
    st.html('<style>' + '\n'.join(styles) + '</style>')
    cell = st.session_state.selected_cell
    label = f'Selected cell {cell}' if cell else 'No cell selected'
    st.caption(f'{label} · Click a cell to use it in the question and KB focus.')


CONSTRAINT_TYPES = ['Fact', 'At least one value', 'At most one value',
                    'Row uniqueness', 'Column uniqueness', 'Box uniqueness',
                    'Last candidate', 'Other']


def clause_metadata(clause, n, box_h, box_w):
    """Classify meaning from expressions, not generator ordering or text substrings.

    A peer pair may share both a row/column and a box. Without provenance from
    the builder, both tags are honest; stored duplicates remain separate.
    """
    symbols = prop_symbols(clause)
    decoded = {}
    for symbol in symbols:
        try:
            decoded[symbol] = parse_symbol(str(symbol), n)
        except ValueError:
            pass
    cells = sorted({(r, c) for _, r, c, _ in decoded.values()})
    tags = []
    explanation = 'A clause from the supplied knowledge base; no specific Sudoku pattern was recognized.'
    if isinstance(clause, Expr) and not clause.args and clause in decoded:
        tags = ['Fact']
        explanation = statement(str(clause), n) + '. This is asserted as a fact in the KB.'
    elif isinstance(clause, Expr):
        literals = disjuncts(clause) if clause.op == '|' else ()
        positive = [decoded.get(item) for item in literals]
        if (len(literals) == n and all(positive) and len(cells) == 1
                and all(item[0] == 'Is' for item in positive)
                and {item[3] for item in positive} == set(range(1, n + 1))):
            tags = ['At least one value']
            explanation = f'Cell {tuple(cells[0])} must contain at least one value from 1 to {n}.'
        pair = None
        if (len(literals) == 2 and all(isinstance(x, Expr) and x.op == '~' and len(x.args) == 1 for x in literals)):
            pair = [decoded.get(x.args[0]) for x in literals]
            if not all(pair) or any(x[0] != 'Is' for x in pair):
                pair = None
        if clause.op == '==>' and len(clause.args) == 2:
            premise, conclusion = clause.args
            a, b = decoded.get(premise), decoded.get(conclusion)
            if a and b and a[0] == 'Is' and b[0] == 'Not':
                pair = [a, b]
            premises = conjuncts(premise)
            exclusions = [decoded.get(item) for item in premises]
            if (b and b[0] == 'Is' and len(premises) == n - 1 and all(exclusions)
                    and all(x[0] == 'Not' and x[1:3] == b[1:3] for x in exclusions)
                    and {x[3] for x in exclusions} == set(range(1, n + 1)) - {b[3]}):
                tags = ['Last candidate']
                explanation = f'If all other values are ruled out, cell {b[1:3]} must contain {b[3]}.'
        if pair:
            (_, r1, c1, v1), (_, r2, c2, v2) = pair
            if (r1, c1) == (r2, c2) and v1 != v2:
                tags = ['At most one value']
                explanation = f'Cell ({r1}, {c1}) cannot contain both {v1} and {v2}.'
            elif (r1, c1) != (r2, c2) and v1 == v2:
                if r1 == r2:
                    tags.append('Row uniqueness')
                if c1 == c2:
                    tags.append('Column uniqueness')
                if (r1 - 1) // box_h == (r2 - 1) // box_h and (c1 - 1) // box_w == (c2 - 1) // box_w:
                    tags.append('Box uniqueness')
                if tags:
                    explanation = f'Cells ({r1}, {c1}) and ({r2}, {c2}) cannot both contain {v1}.'
    return {'types': tags or ['Other'], 'cells': cells, 'explanation': explanation}


def snapshot_kb(kb, representation, puzzle_number, n=9, box_h=3, box_w=3):
    """Copy actual stored clauses and their CNF display; never run inference."""
    required_type = PropDefiniteKB if representation == 'Definite / Horn' else PropKB
    if not isinstance(kb, required_type):
        raise ValueError(f'The builder must return a {required_type.__name__}.')
    clauses, cnf, symbols = [], [], set()
    metadata, cnf_metadata = [], []
    facts = implications = 0
    for clause in kb.clauses:
        if not isinstance(clause, Expr) and type(clause) is not bool:
            raise ValueError('The knowledge base contains an unsupported clause.')
        clauses.append(str(clause))
        description = clause_metadata(clause, n, box_h, box_w)
        metadata.append(description)
        symbols.update(str(symbol) for symbol in prop_symbols(clause))
        if isinstance(clause, Expr):
            facts += int(not clause.args and clause.op[:1].isupper())
            implications += int(clause.op == '==>')
        if representation == 'Definite / Horn' and isinstance(clause, Expr):
            for part in conjuncts(to_cnf(clause)):
                cnf.append(str(part))
                cnf_metadata.append({**description, 'cells': clause_metadata(part, n, box_h, box_w)['cells']})
        else:
            # PropKB.tell already stored each general clause in CNF.
            cnf.append(str(clause))
            cnf_metadata.append(description)
    return {'representation': representation, 'puzzle_number': puzzle_number,
            'clauses': clauses, 'cnf': cnf, 'symbols': sorted(symbols),
            'facts': facts, 'implications': implications,
            'metadata': metadata, 'cnf_metadata': cnf_metadata}


def kb_download(snapshot, notation):
    """Export all clauses in the selected notation, independent of search/page."""
    clauses = snapshot['cnf'] if notation == 'CNF' else snapshot['clauses']
    title = (f'# Puzzle {snapshot["puzzle_number"]}: {snapshot["representation"]}\n'
             f'# Notation: {notation}; clauses: {len(clauses)}\n'
             '# All lines below are conjoined (AND).\n\n')
    return title + '\n'.join(clauses) + '\n'


def reset_kb_page():
    st.session_state.pop('kb_page', None)
    st.session_state.pop('kb_explain', None)


def render_kb_inspector(n, box_h, box_w, givens, puzzle_number):
    st.divider()
    st.subheader('Explore the knowledge base')
    st.write('See the facts and rules that represent this puzzle, before inference begins.')
    representation = st.radio('Knowledge representation', ['General / CNF', 'Definite / Horn'],
                              key='kb_representation', horizontal=True, on_change=clear_kb)
    if representation == 'General / CNF':
        st.caption('General clauses → resolution or truth-table checking. The general builder stores '
                   'its clauses in conjunctive normal form (CNF). Each displayed line is joined by AND.')
        st.info('The full-grid controls above use Horn rules with forward or backward chaining. '
                'Resolution and truth-table experiments on the general KB belong in the notebook; '
                'the supplied algorithms are impractical on the full 9×9 grid.')
    else:
        st.caption('Definite clauses → forward or backward chaining. View facts and implication rules, '
                   'or their equivalent CNF. Not-prefixed names are positive atoms, not logical negations.')
    if st.button('Generate knowledge base', key='build_kb'):
        clear_kb()
        builder = build_general_kb if representation == 'General / CNF' else build_definite_kb
        with st.spinner('Generating facts and rules…'):
            try:
                started = time.perf_counter()
                kb = builder(n, box_h, box_w, dict(givens))
                elapsed = time.perf_counter() - started
                snapshot = snapshot_kb(kb, representation, puzzle_number, n, box_h, box_w)
                snapshot['elapsed'] = elapsed
                st.session_state.kb_result = snapshot
            except NotImplementedError:
                st.session_state.kb_feedback = {'kind': 'info', 'text': f'The {representation} builder is not available yet. '
                                               'Its actual clauses will appear here once it is implemented.'}
            except ValueError as error:
                st.session_state.kb_feedback = {'kind': 'warning', 'text': str(error)}
    feedback('kb_feedback')
    snapshot = st.session_state.get('kb_result')
    if not snapshot:
        return
    if 'metadata' not in snapshot:
        clear_kb()
        st.info('Regenerate the knowledge base to enable the new filters.')
        return
    count_col, symbol_col, fact_col = st.columns(3)
    count_col.metric('Stored clauses', len(snapshot['clauses']))
    symbol_col.metric('Propositional symbols', len(snapshot['symbols']))
    fact_col.metric('Positive atomic facts', snapshot['facts'])
    st.caption(f'Puzzle {snapshot["puzzle_number"]} · {snapshot["representation"]} · '
               f'{snapshot["elapsed"]:.3f} s to build the KB')
    if representation == 'Definite / Horn':
        notation = st.radio('Display notation', ['Stored form', 'CNF'], key='kb_notation',
                            horizontal=True, on_change=reset_kb_page)
        st.caption(f'{snapshot["implications"]:,} stored implication rules. '
                   'P & Q ==> R is equivalent to ~P | ~Q | R.')
    else:
        notation = 'CNF'
        st.caption('These are the actual stored CNF clauses. The original formulas before conversion '
                   'are not retained by PropKB, so they are not reconstructed here.')
    clauses = snapshot['cnf'] if notation == 'CNF' else snapshot['clauses']
    metadata = snapshot['cnf_metadata'] if notation == 'CNF' else snapshot['metadata']
    types = st.multiselect('Constraint types', CONSTRAINT_TYPES, key='kb_types',
                          placeholder='All facts and constraint types', on_change=reset_kb_page)
    cell = st.session_state.selected_cell
    focus_label = f'Focus on current selected cell {cell}' if cell else 'Select a cell to enable KB focus'
    focus = st.checkbox(focus_label, key='kb_focus', disabled=cell is None,
                        on_change=reset_kb_page)
    st.caption('Focus shows clauses that explicitly mention this cell. Multiple selected types are combined with OR. '
               'A clause can belong to both a row/column and a box; duplicates are retained.')
    search = st.text_input('Search clauses', key='kb_search', placeholder='For example: Is1_2_3',
                           on_change=reset_kb_page).strip()
    matches = [(index, clause) for index, clause in enumerate(clauses, 1)
               if search.casefold() in clause.casefold()
               and (not types or set(types).intersection(metadata[index - 1]['types']))
               and (not focus or cell in metadata[index - 1]['cells'])]
    page_size = 50
    pages = max(1, (len(matches) + page_size - 1) // page_size)
    page = st.number_input('Clause page', min_value=1, max_value=pages, value=1, step=1, key='kb_page')
    visible = matches[(page - 1) * page_size:page * page_size]
    st.caption(f'{len(matches):,} of {len(clauses):,} clauses match · Page {page} of {pages} · Up to 50 lines per page')
    if visible:
        st.code('\n'.join(f'{index:>5}. {clause}' for index, clause in visible), language='text')
        with st.expander('Explain a displayed clause'):
            index = st.selectbox('Clause number', [index for index, _ in visible], key='kb_explain')
            description = metadata[index - 1]
            st.write(description['explanation'])
            st.caption(' · '.join(description['types']))
    else:
        st.info('No clauses match these filters. Try another type or turn off cell focus.' if clauses else 'This knowledge base contains no clauses.')
    slug = 'general' if representation == 'General / CNF' else 'definite'
    st.download_button('Download all clauses', kb_download(snapshot, notation),
                       file_name=f'puzzle-{puzzle_number}-{slug}-{notation.lower().replace(" ", "-")}.txt',
                       mime='text/plain', key='download_kb')
    with st.expander('How to read the symbols'):
        st.markdown('`Is1_2_3`: row 1, column 2 has value 3.  \n'
                    '`Not1_2_3`: the positive atom saying this value has been ruled out.  \n'
                    '`~`: logical NOT · `|`: OR · `&`: AND · `==>`: implies.  \n'
                    'For example, `~Is1_1_1 | ~Is1_2_1` prevents both cells from having value 1. '
                    'This is a notation example, not an additional generated clause.')


def feedback(key):
    message = st.session_state.get(key)
    if message:
        getattr(st, message['kind'])(message['text'])


def render_query_result(result):
    r, c, v = result['cell']
    if result['positive']['entailed']:
        st.success(f'True — row {r}, column {c} must be {v}.')
    elif result['exclusion']:
        st.info(f'False — {v} is ruled out at row {r}, column {c}.')
    else:
        st.warning(f'False — the current rules do not establish {v} at row {r}, column {c}. '
                   'An unproved value is not necessarily impossible.')
    st.caption(f'Backward chaining · {result["elapsed"]:.3f} s including knowledge-base construction'
               ' and any exclusion check')
    if not result['trace_available']:
        st.info('The cell verdict is available. Step-by-step explanations are not available yet.')


def move_proof_step(offset, total):
    """Update the slider before rerendering, staying inside the current proof."""
    st.session_state.proof_step = max(1, min(total, st.session_state.get('proof_step', 1) + offset))


def reset_solve_walk():
    st.session_state.pop('solve_walk_step', None)


def move_solve_step(offset, total):
    st.session_state.solve_walk_step = max(0, min(total, st.session_state.get('solve_walk_step', 0) + offset))


def solve_checkpoints(steps, givens, n, mode):
    """Choose display checkpoints without changing the underlying trace order."""
    if mode == 'All deductions':
        return list(range(len(steps)))
    checkpoints = []
    for index, step in enumerate(steps):
        prefix, r, c, _ = parse_symbol(step['conclusion'], n)
        if prefix == 'Is' and (r, c) not in givens:
            checkpoints.append(index)
    return checkpoints


def replay_solve(steps, through, givens, n):
    """Replay established placements only; the returned solution is not a source."""
    values = dict(givens)
    for step in steps[:through + 1]:
        prefix, r, c, v = parse_symbol(step['conclusion'], n)
        if prefix == 'Is':
            values[r, c] = v
    return values


def render_solve_walkthrough(result, givens, n, box_h, box_w):
    st.divider()
    st.subheader('Follow the solve')
    steps = result.get('steps')
    if steps is None:
        st.info('This solver returned a grid without a walkthrough. Full-grid trace support is optional.')
        return
    st.caption(f'{result["algorithm"]} · Replay the successful deductions recorded during this solve. '
               'This does not show attempted goals or failed search branches.')
    mode = st.radio('Walkthrough detail', ['Cell placements', 'All deductions'], horizontal=True,
                    key='solve_walk_mode', on_change=reset_solve_walk)
    st.caption('Cell placements groups the intervening eliminations before each new value. '
               'All deductions includes clue-processing steps and individual eliminations. Both start from the original clues.')
    checkpoints = solve_checkpoints(steps, givens, n, mode)
    total = len(checkpoints)
    current = st.session_state.get('solve_walk_step', 0)
    previous, slider, following = st.columns([1, 3, 1], vertical_alignment='center')
    previous.button('Previous step', key='solve_walk_previous', use_container_width=True,
                    disabled=current == 0, on_click=move_solve_step, args=(-1, total))
    with slider:
        position = st.slider('Solve step', 0, total, key='solve_walk_step') if total else 0
        if not total:
            st.caption('The original clues already fill the board.')
    following.button('Next step', key='solve_walk_next', use_container_width=True,
                     disabled=position == total, on_click=move_solve_step, args=(1, total))
    through = checkpoints[position - 1] if position else -1
    values = replay_solve(steps, through, givens, n)
    step = steps[through] if position else None
    target = parse_symbol(step['conclusion'], n)[1:3] if step else None
    support = {parse_symbol(p, n)[1:3] for p in step['premises']} if step else set()
    board, description = st.columns([1.1, 1], gap='large')
    with board:
        st.html(board_html(values, givens, n, box_h, box_w, target, support, 'Solve progress'))
        st.caption(f'{len(values)} / {n*n} cells filled · Gold: current cell · Green tint: supporting cells')
    with description:
        st.caption(f'SOLVE STEP {position} OF {total}')
        if step:
            st.markdown(f'**{REASON_TITLES.get(step["reason"], "Apply a logical rule")}**')
            st.write(explain_step(step, n))
            st.caption(f'Recorded deduction {through + 1} of {len(steps)}')
            if step['premises']:
                with st.expander('Supporting facts', expanded=True):
                    for premise in step['premises']:
                        st.write('• ' + statement(premise, n) + '.')
        else:
            st.markdown('**Start from the original clues**')
            st.write('Use Next step to see how the solver fills the remaining cells.')
    st.download_button('Download solve trace', json.dumps({'algorithm': result['algorithm'], 'steps': steps}, indent=2),
                       file_name='sudoku-solve-trace.json', mime='application/json', key='download_solve_trace')


def render_tutor(result, givens, n, box_h, box_w):
    proof = result['positive'] if result['positive']['entailed'] else result['exclusion']
    if not proof or not proof['steps']:
        return
    steps = proof['steps']
    st.divider()
    st.subheader('Follow the proof')
    st.write('Explore the facts and deductions supporting the answer. Each step builds on earlier steps.')
    if not result['positive']['entailed']:
        st.caption('This is a separate proof that the requested value is ruled out.')
    current_step = st.session_state.get('proof_step', 1)
    previous_column, slider_column, next_column = st.columns([1, 3, 1], vertical_alignment='center')
    previous_column.button('Previous step', key='proof_previous', use_container_width=True,
                           disabled=current_step <= 1, on_click=move_proof_step, args=(-1, len(steps)))
    with slider_column:
        step_number = st.slider('Proof step', 1, len(steps), key='proof_step') if len(steps) > 1 else 1
        if len(steps) == 1:
            st.caption('Step 1 of 1')
    next_column.button('Next step', key='proof_next', use_container_width=True,
                       disabled=step_number >= len(steps), on_click=move_proof_step, args=(1, len(steps)))
    step = steps[step_number - 1]
    _, r, c, v = parse_symbol(step['conclusion'], n)
    support = {parse_symbol(p, n)[1:3] for p in step['premises']}
    values = dict(givens)
    for previous in steps[:step_number]:
        prefix, rr, cc, vv = parse_symbol(previous['conclusion'], n)
        if prefix == 'Is':
            values[rr, cc] = vv
    board_column, description_column = st.columns([1.1, 1], gap='large')
    with board_column:
        st.html(board_html(values, givens, n, box_h, box_w, (r, c), support, 'Proof progress'))
        st.html('<div class="board-legend">Gold · current cell &nbsp; Green tint · supporting cells</div>')
    with description_column:
        st.caption(f'STEP {step_number} OF {len(steps)}')
        st.markdown(f'**{REASON_TITLES.get(step["reason"], "Apply a logical rule")}**')
        st.write(explain_step(step, n))
        if step['premises']:
            with st.expander('Supporting facts', expanded=True):
                for premise in step['premises']:
                    st.write('• ' + statement(premise, n) + '.')
        with st.expander('Read the complete proof'):
            for index, item in enumerate(steps, 1):
                st.write(f'{index}. {explain_step(item, n)}')


def main():
    st.set_page_config(page_title='Group 23 - Sudoku Solver', page_icon='🧩', layout='wide')
    # Query submission reruns before reaching the walkthrough widgets. Keep
    # their state owned by the session so that widget cleanup cannot erase it.
    for key in ('solve_walk_step', 'solve_walk_mode'):
        if key in st.session_state:
            st.session_state[key] = st.session_state[key]
    st.html(STYLE)
    n, box_h, box_w, puzzles = load_puzzles()
    st.html('<div class="eyebrow">IT5005 / KNOWLEDGE REPRESENTATION & INFERENCE</div>')
    st.title('Group 23 - Sudoku Solver')
    st.write('Every number has a reason. Solve a puzzle, ask about a cell, and follow the logic.')
    st.divider()

    board_column, controls_column = st.columns([1.1, 1], gap='large')
    with board_column:
        selected = st.selectbox('Choose a puzzle', range(len(puzzles)), key='puzzle_index',
                                format_func=lambda i: f'Puzzle {i + 1} · {puzzles[i]["given_count"]} givens',
                                on_change=clear_results)
        givens = puzzles[selected]['givens']
        solved = st.session_state.get('solution_result')
        values = solved['grid'] if solved else givens
        if 'selected_cell' not in st.session_state:
            first_empty = next(((r, c) for r in range(1, n + 1) for c in range(1, n + 1)
                                if (r, c) not in givens), (1, 1))
            st.session_state.selected_cell = None
            st.session_state.query_row, st.session_state.query_col = first_empty
        render_selectable_board(values, givens, n, box_h, box_w)
        st.html('<div class="board-legend"><b>Dark numbers</b> · original clues &nbsp; '
                '<span style="color:#197352">Green numbers</span> · deduced</div>')
        if solved:
            st.success(f'{n*n} / {n*n} cells solved · {solved["algorithm"]} · {solved["elapsed"]:.3f} s')
        else:
            st.caption(f'{n} × {n} grid · {box_h} × {box_w} boxes · {n*n-len(givens)} empty cells')

    with controls_column:
        st.subheader('Solve the whole board')
        algorithm = st.radio('Inference method', ['Forward chaining', 'Backward chaining'], key='algorithm', horizontal=True)
        st.caption('Both methods use the definite / Horn KB. Forward chaining builds from facts; '
                   'backward chaining works from a question toward supporting facts.')
        solve_column, reset_column = st.columns([2, 1])
        solve_pressed = solve_column.button('Solve puzzle', type='primary', use_container_width=True, key='solve')
        reset_column.button('Reset', use_container_width=True, key='reset', on_click=clear_results)
        if solve_pressed:
            st.session_state.pop('solution_result', None)
            st.session_state.pop('solve_feedback', None)
            reset_solve_walk()
            with st.spinner('Following the Sudoku rules…'):
                try:
                    started = time.perf_counter()
                    grid, steps = solve_with_optional_trace(algorithm, n, box_h, box_w, givens)
                    elapsed = time.perf_counter() - started
                    st.session_state.solution_result = {'grid': grid, 'algorithm': algorithm, 'elapsed': elapsed, 'steps': steps}
                except NotImplementedError:
                    st.session_state.solve_feedback = {'kind': 'info', 'text': f'{algorithm} is not available yet. You can still explore the puzzles.'}
                except ValueError as error:
                    st.session_state.solve_feedback = {'kind': 'warning', 'text': str(error)}
            st.rerun()
        feedback('solve_feedback')
        with st.expander('What if a puzzle has multiple solutions?'):
            st.write('These rules infer only forced values; they do not guess or choose between solutions. '
                     'An ambiguous puzzle remains incomplete. An incomplete result may also mean the rules '
                     'need stronger reasoning, so it does not establish how many solutions exist.')
        st.divider()
        st.subheader('Ask about one cell')
        st.write('Does the puzzle imply that this cell has this value?')
        row_column, col_column, value_column = st.columns(3)
        r = row_column.number_input('Row', 1, n, key='query_row',
                                    on_change=query_coordinates_changed)
        c = col_column.number_input('Column', 1, n, key='query_col',
                                    on_change=query_coordinates_changed)
        v = value_column.number_input('Value', 1, n, 1, key='query_value', on_change=clear_query)
        submitted = st.button('Check & explain', use_container_width=True, key='check_cell')
        if submitted:
            st.session_state.selected_cell = (r, c)
            reset_kb_page()
            for key in ('query_result', 'query_feedback', 'proof_step'):
                st.session_state.pop(key, None)
            with st.spinner('Looking for a supporting proof…'):
                try:
                    st.session_state.query_result = check_cell(n, box_h, box_w, givens, r, c, v)
                except NotImplementedError:
                    st.session_state.query_feedback = {'kind': 'info', 'text': 'Cell checking is not available yet. The puzzle clues are ready to explore.'}
                except ValueError as error:
                    st.session_state.query_feedback = {'kind': 'warning', 'text': str(error)}
            st.rerun()
        feedback('query_feedback')
        if st.session_state.get('query_result'):
            render_query_result(st.session_state.query_result)
        else:
            st.caption('Check a cell to see its verdict and, when available, a step-by-step explanation.')

    if st.session_state.get('solution_result'):
        render_solve_walkthrough(st.session_state.solution_result, givens, n, box_h, box_w)
    if st.session_state.get('query_result'):
        render_tutor(st.session_state.query_result, givens, n, box_h, box_w)
    render_kb_inspector(n, box_h, box_w, givens, selected + 1)
    st.divider()
    st.caption('Propositional logic · Elimination & last-candidate reasoning · No guessing')


if __name__ == '__main__':
    main()
