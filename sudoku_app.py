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
from logic_ import PropKB, PropDefiniteKB, Expr, prop_symbols, to_cnf, conjuncts
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
                'query_row', 'query_col', 'query_value', 'proof_step'):
        st.session_state.pop(key, None)
    clear_kb()


def clear_kb():
    """A KB snapshot belongs to one puzzle and one representation."""
    for key in ('kb_result', 'kb_feedback', 'kb_search', 'kb_page', 'kb_notation'):
        st.session_state.pop(key, None)


def snapshot_kb(kb, representation, puzzle_number):
    """Copy actual stored clauses and their CNF display; never run inference."""
    required_type = PropDefiniteKB if representation == 'Definite / Horn' else PropKB
    if not isinstance(kb, required_type):
        raise ValueError(f'The builder must return a {required_type.__name__}.')
    clauses, cnf, symbols = [], [], set()
    facts = implications = 0
    for clause in kb.clauses:
        if not isinstance(clause, Expr) and type(clause) is not bool:
            raise ValueError('The knowledge base contains an unsupported clause.')
        clauses.append(str(clause))
        symbols.update(str(symbol) for symbol in prop_symbols(clause))
        if isinstance(clause, Expr):
            facts += int(not clause.args and clause.op[:1].isupper())
            implications += int(clause.op == '==>')
        if representation == 'Definite / Horn' and isinstance(clause, Expr):
            cnf.extend(str(part) for part in conjuncts(to_cnf(clause)))
        else:
            # PropKB.tell already stored each general clause in CNF.
            cnf.append(str(clause))
    return {'representation': representation, 'puzzle_number': puzzle_number,
            'clauses': clauses, 'cnf': cnf, 'symbols': sorted(symbols),
            'facts': facts, 'implications': implications}


def kb_download(snapshot, notation):
    """Export all clauses in the selected notation, independent of search/page."""
    clauses = snapshot['cnf'] if notation == 'CNF' else snapshot['clauses']
    title = (f'# Puzzle {snapshot["puzzle_number"]}: {snapshot["representation"]}\n'
             f'# Notation: {notation}; clauses: {len(clauses)}\n'
             '# All lines below are conjoined (AND).\n\n')
    return title + '\n'.join(clauses) + '\n'


def reset_kb_page():
    st.session_state.pop('kb_page', None)


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
                snapshot = snapshot_kb(kb, representation, puzzle_number)
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
    search = st.text_input('Search clauses', key='kb_search', placeholder='For example: Is1_2_3',
                           on_change=reset_kb_page).strip()
    matches = [(index, clause) for index, clause in enumerate(clauses, 1)
               if search.casefold() in clause.casefold()]
    page_size = 50
    pages = max(1, (len(matches) + page_size - 1) // page_size)
    page = st.number_input('Clause page', min_value=1, max_value=pages, value=1, step=1, key='kb_page')
    visible = matches[(page - 1) * page_size:page * page_size]
    st.caption(f'{len(matches):,} of {len(clauses):,} clauses match · Page {page} of {pages} · Up to 50 lines per page')
    if visible:
        st.code('\n'.join(f'{index:>5}. {clause}' for index, clause in visible), language='text')
    else:
        st.info('No clauses match this search.' if clauses else 'This knowledge base contains no clauses.')
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
    step_number = st.slider('Proof step', 1, len(steps), key='proof_step') if len(steps) > 1 else 1
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
        result = st.session_state.get('query_result')
        target = result['cell'][:2] if result else None
        st.html(board_html(solved['grid'] if solved else givens, givens, n, box_h, box_w, target))
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
            solver = solve_full_grid_fc if algorithm == 'Forward chaining' else solve_full_grid_bc
            with st.spinner('Following the Sudoku rules…'):
                try:
                    started = time.perf_counter()
                    grid = solver(n, box_h, box_w, dict(givens))
                    elapsed = time.perf_counter() - started
                    grid = validate_grid(grid, givens, n, box_h, box_w)
                    st.session_state.solution_result = {'grid': grid, 'algorithm': algorithm, 'elapsed': elapsed}
                except NotImplementedError:
                    st.session_state.solve_feedback = {'kind': 'info', 'text': f'{algorithm} is not available yet. You can still explore the puzzles.'}
                except ValueError as error:
                    st.session_state.solve_feedback = {'kind': 'warning', 'text': str(error)}
            st.rerun()
        feedback('solve_feedback')
        st.divider()
        st.subheader('Ask about one cell')
        st.write('Does the puzzle imply that this cell has this value?')
        first_empty = next(((r, c) for r in range(1, n + 1) for c in range(1, n + 1)
                            if (r, c) not in givens), (1, 1))
        with st.form('cell_query'):
            row_column, col_column, value_column = st.columns(3)
            r = row_column.number_input('Row', 1, n, first_empty[0], key='query_row')
            c = col_column.number_input('Column', 1, n, first_empty[1], key='query_col')
            v = value_column.number_input('Value', 1, n, 1, key='query_value')
            submitted = st.form_submit_button('Check & explain', use_container_width=True)
        if submitted:
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

    if st.session_state.get('query_result'):
        render_tutor(st.session_state.query_result, givens, n, box_h, box_w)
    render_kb_inspector(n, box_h, box_w, givens, selected + 1)
    st.divider()
    st.caption('Propositional logic · Elimination & last-candidate reasoning · No guessing')


if __name__ == '__main__':
    main()
