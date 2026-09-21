"""Frontend integration checks; backend fixtures never enter the live app."""

from copy import deepcopy
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import sudoku_app as ui


ROOT = Path(__file__).resolve().parents[1]
GIVENS = {(1, 1): 1, (1, 2): 2, (1, 3): 3}
GRID = {(r + 1, c + 1): value for r, row in enumerate([
    [1, 2, 3, 4], [3, 4, 1, 2], [2, 1, 4, 3], [4, 3, 2, 1],
]) for c, value in enumerate(row)}
STEPS = [
    {'conclusion': 'Is1_1_1', 'premises': [], 'reason': 'given'},
    {'conclusion': 'Not1_4_1', 'premises': ['Is1_1_1'], 'reason': 'row_elimination'},
    {'conclusion': 'Is1_2_2', 'premises': [], 'reason': 'given'},
    {'conclusion': 'Not1_4_2', 'premises': ['Is1_2_2'], 'reason': 'row_elimination'},
    {'conclusion': 'Is1_3_3', 'premises': [], 'reason': 'given'},
    {'conclusion': 'Not1_4_3', 'premises': ['Is1_3_3'], 'reason': 'row_elimination'},
    {'conclusion': 'Is1_4_4', 'premises': ['Not1_4_1', 'Not1_4_2', 'Not1_4_3'], 'reason': 'last_candidate'},
]


def entrypoint():
    import sudoku_app
    sudoku_app.main()


@pytest.fixture
def fixture_ui(monkeypatch):
    """Run the real UI with two explicit small puzzles and controllable backend calls."""
    puzzles = [{'givens': dict(GIVENS), 'given_count': 3},
               {'givens': {(4, 4): 1}, 'given_count': 1}]
    monkeypatch.setattr(ui, 'load_puzzles', lambda: (4, 2, 2, puzzles))
    monkeypatch.setattr(ui, 'build_definite_kb', lambda n, h, w, givens: object())
    monkeypatch.setattr(ui, 'solve_full_grid_fc', lambda *args: dict(GRID))
    monkeypatch.setattr(ui, 'solve_full_grid_bc', lambda *args: dict(GRID))
    monkeypatch.setattr(ui, 'pl_bc_entails', lambda kb, query: False)
    monkeypatch.delattr(ui.sudoku_solver, 'pl_bc_entails_with_trace', raising=False)
    return AppTest.from_function(entrypoint).run()


def submit_query(app, r=1, c=4, v=4):
    app.number_input(key='query_row').set_value(r)
    app.number_input(key='query_col').set_value(c)
    app.number_input(key='query_value').set_value(v)
    app.button(key='FormSubmitter:cell_query-Check & explain').click().run()
    assert not app.exception
    return app


def set_trace(monkeypatch, callback):
    monkeypatch.setattr(ui.sudoku_solver, 'pl_bc_entails_with_trace', callback, raising=False)


def fixture_trace(kb, query):
    name = str(query)
    if name == 'Is1_4_4':
        return {'query': name, 'entailed': True, 'steps': deepcopy(STEPS)}
    if name == 'Not1_4_1':
        return {'query': name, 'entailed': True, 'steps': deepcopy(STEPS[:2])}
    if name == 'Is1_1_1':
        return {'query': name, 'entailed': True, 'steps': deepcopy(STEPS[:1])}
    return {'query': name, 'entailed': False, 'steps': []}


def test_real_starter_loads_from_another_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    ui.load_puzzles.clear()
    n, h, w, puzzles = ui.load_puzzles()
    assert (n, h, w) == (9, 3, 3)
    assert len(puzzles) == 5
    assert all(set(puzzle) == {'givens', 'given_count'} for puzzle in puzzles)
    app = AppTest.from_file(str(ROOT / 'sudoku_app.py')).run()
    assert not app.exception
    assert app.title[0].value == 'Group 23 - Sudoku Solver'
    assert len(app.selectbox[0].options) == 5


@pytest.mark.parametrize('method', ['Forward chaining', 'Backward chaining'])
def test_unavailable_backend_has_honest_solve_message(method, monkeypatch):
    def unavailable(*args):
        raise NotImplementedError
    function = 'solve_full_grid_fc' if method == 'Forward chaining' else 'solve_full_grid_bc'
    monkeypatch.setattr(ui.sudoku_solver, function, unavailable)
    app = AppTest.from_file(str(ROOT / 'sudoku_app.py')).run()
    app.radio(key='algorithm').set_value(method)
    app.button(key='solve').click().run()
    assert not app.exception
    assert any(f'{method} is not available yet' in msg.value for msg in app.info)
    assert 'solution_result' not in app.session_state


def test_unavailable_backend_has_honest_query_message(monkeypatch):
    def unavailable(*args):
        raise NotImplementedError
    monkeypatch.setattr(ui.sudoku_solver, 'build_definite_kb', unavailable)
    app = AppTest.from_file(str(ROOT / 'sudoku_app.py')).run()
    submit_query(app)
    assert any('Cell checking is not available yet' in msg.value for msg in app.info)
    assert 'query_result' not in app.session_state


@pytest.mark.parametrize('method,function', [('Forward chaining', 'solve_full_grid_fc'),
                                             ('Backward chaining', 'solve_full_grid_bc')])
def test_full_grid_dispatch_and_clue_isolation(fixture_ui, monkeypatch, method, function):
    calls = []

    def solve(n, h, w, givens):
        calls.append((n, h, w, dict(givens)))
        # Simulate an early backend that mutates its argument; the UI's clues survive.
        givens.clear()
        return dict(GRID)

    monkeypatch.setattr(ui, function, solve)
    app = fixture_ui
    app.radio(key='algorithm').set_value(method)
    app.button(key='solve').click().run()
    assert not app.exception
    assert calls == [(4, 2, 2, GIVENS)]
    assert app.session_state.solution_result['grid'] == GRID
    assert app.session_state.solution_result['elapsed'] >= 0
    assert any(f'16 / 16 cells solved · {method}' in item.value for item in app.success)
    assert ui.load_puzzles()[3][0]['givens'] == GIVENS


def test_query_uses_original_clues_after_solving(fixture_ui, monkeypatch):
    app = fixture_ui
    app.button(key='solve').click().run()
    calls = []
    monkeypatch.setattr(ui, 'build_definite_kb', lambda n, h, w, g: calls.append(dict(g)))
    submit_query(app)
    assert calls == [GIVENS]


def test_incomplete_grid_never_displays_as_solved(fixture_ui, monkeypatch):
    app = fixture_ui
    app.button(key='solve').click().run()
    monkeypatch.setattr(ui, 'solve_full_grid_fc', lambda *args: dict(GIVENS))
    app.button(key='solve').click().run()
    assert not app.exception
    assert 'solution_result' not in app.session_state
    assert any('did not return a complete grid' in item.value for item in app.warning)


def test_unsolved_error_is_displayed(fixture_ui, monkeypatch):
    def unresolved(*args):
        raise ValueError('The current Horn rules determined 3 of 16 cells.')
    monkeypatch.setattr(ui, 'solve_full_grid_fc', unresolved)
    app = fixture_ui
    app.button(key='solve').click().run()
    assert not app.exception
    assert any('3 of 16 cells' in item.value for item in app.warning)


def test_true_trace_and_slider_render_live_proof(fixture_ui, monkeypatch):
    set_trace(monkeypatch, fixture_trace)
    app = submit_query(fixture_ui)
    assert any('True — row 1, column 4 must be 4' in item.value for item in app.success)
    assert app.slider(key='proof_step').max == 7
    app.slider(key='proof_step').set_value(7).run()
    assert not app.exception
    assert any('only remaining candidate' in item.value for item in app.markdown)
    assert any('proof' in item.value.lower() for item in app.subheader)


def test_false_with_separate_exclusion_proof(fixture_ui, monkeypatch):
    set_trace(monkeypatch, fixture_trace)
    app = submit_query(fixture_ui, v=1)
    assert not app.session_state.query_result['positive']['entailed']
    assert app.session_state.query_result['exclusion']['query'] == 'Not1_4_1'
    assert any('1 is ruled out' in item.value for item in app.info)
    assert app.slider(key='proof_step').max == 2


def test_unknown_is_not_described_as_impossible(fixture_ui, monkeypatch):
    set_trace(monkeypatch, fixture_trace)
    app = submit_query(fixture_ui, r=2, c=1, v=1)
    assert any('not necessarily impossible' in item.value for item in app.warning)
    assert not app.slider
    assert app.session_state.query_result['exclusion'] is None


def test_shorter_new_proof_resets_slider(fixture_ui, monkeypatch):
    set_trace(monkeypatch, fixture_trace)
    app = submit_query(fixture_ui)
    app.slider(key='proof_step').set_value(7).run()
    submit_query(app, r=1, c=1, v=1)
    assert not app.slider
    assert len(app.session_state.query_result['positive']['steps']) == 1
    submit_query(app, v=1)
    assert app.slider(key='proof_step').value == 1


@pytest.mark.parametrize('trace_mode', ['absent', 'stub'])
def test_plain_bc_works_before_trace_is_available(fixture_ui, monkeypatch, trace_mode):
    monkeypatch.setattr(ui, 'pl_bc_entails', lambda *args: True)
    if trace_mode == 'stub':
        def stub(*args):
            raise NotImplementedError
        set_trace(monkeypatch, stub)
    app = submit_query(fixture_ui)
    assert any('True —' in item.value for item in app.success)
    assert any('explanations are not available yet' in item.value for item in app.info)
    assert not app.slider


@pytest.mark.parametrize('action', ['reset', 'change_puzzle'])
def test_puzzle_state_is_cleared(fixture_ui, monkeypatch, action):
    set_trace(monkeypatch, fixture_trace)
    app = fixture_ui
    app.button(key='solve').click().run()
    submit_query(app)
    app.slider(key='proof_step').set_value(7).run()
    if action == 'reset':
        app.button(key='reset').click().run()
    else:
        app.selectbox(key='puzzle_index').set_value(1).run()
    assert not app.exception
    assert 'solution_result' not in app.session_state
    assert 'query_result' not in app.session_state
    assert not app.slider
    assert app.number_input(key='query_value').value == 1


def test_malformed_trace_is_reported_without_old_verdict(fixture_ui, monkeypatch):
    set_trace(monkeypatch, fixture_trace)
    app = submit_query(fixture_ui)
    set_trace(monkeypatch, lambda kb, query: {'query': str(query), 'entailed': True, 'steps': [STEPS[-1]]})
    submit_query(app)
    assert 'query_result' not in app.session_state
    assert any('missing an earlier supporting step' in item.value for item in app.warning)


def test_trace_snapshot_is_independent_and_names_are_not_evaluated():
    source = fixture_trace(None, ui.atom('Is', 1, 4, 4))
    result = ui.validate_trace(source, ui.atom('Is', 1, 4, 4), 4, GIVENS)
    result['steps'][1]['premises'].clear()
    assert source['steps'][1]['premises'] == ['Is1_1_1']
    for name in ('__import__("os")', 'Is0_1_1', 'Is1_1_5', 'Is_1_1_1'):
        with pytest.raises(ValueError):
            ui.parse_symbol(name, 4)
    assert ui.parse_symbol('Not12_10_16', 16) == ('Not', 12, 10, 16)


def test_invalid_grid_rejected_and_rectangular_boxes_supported():
    invalid = dict(GRID)
    invalid[2, 1] = invalid[2, 2]
    with pytest.raises(ValueError, match='constraint'):
        ui.validate_grid(invalid, GIVENS, 4, 2, 2)
    grid6 = {(r + 1, c + 1): (3 * (r % 2) + r // 2 + c) % 6 + 1
             for r in range(6) for c in range(6)}
    assert ui.validate_grid(grid6, {}, 6, 2, 3) == grid6
    rendered = ui.board_html(grid6, {}, 6, 2, 3, (1, 1), {(2, 1)})
    assert rendered.count('<td ') == 36
    assert rendered.count('border-right:2px') == 12
    assert rendered.count('border-bottom:2px') == 18
    assert 'selected cell' in rendered and 'supporting cell' in rendered
