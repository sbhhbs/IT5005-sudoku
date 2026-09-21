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
    monkeypatch.delattr(ui.sudoku_solver, 'solve_full_grid_fc_with_trace', raising=False)
    monkeypatch.delattr(ui.sudoku_solver, 'solve_full_grid_bc_with_trace', raising=False)
    return AppTest.from_function(entrypoint).run()


def submit_query(app, r=1, c=4, v=4):
    app.number_input(key='query_row').set_value(r)
    app.number_input(key='query_col').set_value(c)
    app.number_input(key='query_value').set_value(v)
    app.button(key='check_cell').click().run()
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
    assert [tab.label for tab in app.tabs] == ['Solve the grid', 'Ask about cell', 'Knowledge base explore']
    assert app.tabs[0].button(key='solve').label == 'Solve puzzle'
    assert app.tabs[1].button(key='check_cell').label == 'Check & explain'
    assert app.tabs[2].button(key='build_kb').label == 'Generate knowledge base'


@pytest.mark.parametrize('method', ['Forward chaining', 'Backward chaining'])
def test_unavailable_backend_has_honest_solve_message(method, monkeypatch):
    def unavailable(*args):
        raise NotImplementedError
    function = 'solve_full_grid_fc' if method == 'Forward chaining' else 'solve_full_grid_bc'
    monkeypatch.setattr(ui.sudoku_solver, function, unavailable)
    monkeypatch.setattr(ui.sudoku_solver, function + '_with_trace', unavailable, raising=False)
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
    assert app.button(key='proof_previous').disabled
    assert not app.button(key='proof_next').disabled
    app.button(key='proof_next').click().run()
    assert app.slider(key='proof_step').value == 2
    assert any('STEP 2 OF 7' in item.value for item in app.caption)
    app.button(key='proof_previous').click().run()
    assert app.slider(key='proof_step').value == 1
    assert app.button(key='proof_previous').disabled
    app.slider(key='proof_step').set_value(7).run()
    assert not app.exception
    assert app.button(key='proof_next').disabled
    app.button(key='proof_previous').click().run()
    assert app.slider(key='proof_step').value == 6
    app.button(key='proof_next').click().run()
    assert any('only remaining candidate' in item.value for item in app.markdown)
    assert any('proof' in item.value.lower() for item in app.subheader)
    submit_query(app, r=1, c=1, v=1)
    assert not app.slider
    assert app.button(key='proof_previous').disabled
    assert app.button(key='proof_next').disabled
    assert not app.exception


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


def general_fixture_kb(*args):
    from logic_ import PropKB
    kb = PropKB()
    kb.tell(ui.atom('Is', 1, 1, 1))
    kb.tell(ui.atom('Is', 1, 4, 1) | ui.atom('Is', 1, 4, 4))
    kb.tell(~ui.atom('Is', 1, 1, 1) | ~ui.atom('Is', 1, 4, 1))
    return kb


def definite_fixture_kb(*args):
    from logic_ import PropDefiniteKB, Expr
    kb = PropDefiniteKB()
    kb.tell(ui.atom('Is', 1, 1, 1))
    kb.tell(Expr('==>', ui.atom('Is', 1, 1, 1), ui.atom('Not', 1, 4, 1)))
    return kb


def test_general_inspector_builds_actual_clauses_without_inference(fixture_ui, monkeypatch):
    calls = []
    def build(n, h, w, givens):
        calls.append((n, h, w, dict(givens)))
        return general_fixture_kb()
    def no_inference(*args):
        raise AssertionError('Inspecting the KB must not run inference')
    monkeypatch.setattr(ui, 'build_general_kb', build)
    monkeypatch.setattr(ui, 'solve_full_grid_fc', no_inference)
    monkeypatch.setattr(ui, 'pl_bc_entails', no_inference)
    app = fixture_ui
    app.button(key='build_kb').click().run()
    assert not app.exception
    assert calls == [(4, 2, 2, GIVENS)]
    assert [metric.value for metric in app.metric] == ['3', '3', '1']
    assert 'Is1_1_1' in app.code[0].value
    app.text_input(key='kb_search').set_value('~Is1_1_1').run()
    assert not app.exception
    assert len(app.code[0].value.splitlines()) == 1
    assert app.code[0].value.strip().startswith('3.')
    # Download contains all clauses even while the view is filtered.
    download = ui.kb_download(app.session_state.kb_result, 'CNF')
    assert '(Is1_4_1 | Is1_4_4)' in download
    assert 'clauses: 3' in download
    app.text_input(key='kb_search').set_value('nonexistent').run()
    assert not app.code
    assert any('No clauses match' in item.value for item in app.info)


def test_definite_inspector_shows_equivalent_cnf(fixture_ui, monkeypatch):
    monkeypatch.setattr(ui, 'build_definite_kb', definite_fixture_kb)
    app = fixture_ui
    app.radio(key='kb_representation').set_value('Definite / Horn').run()
    app.button(key='build_kb').click().run()
    assert not app.exception
    assert '==>' in app.code[0].value
    app.radio(key='kb_notation').set_value('CNF').run()
    assert not app.exception
    assert '==>' not in app.code[0].value
    assert '~Is1_1_1' in app.code[0].value
    assert 'Not1_4_1' in app.code[0].value
    assert app.session_state.kb_result['implications'] == 1


@pytest.mark.parametrize('action', ['reset', 'change_puzzle', 'change_representation'])
def test_kb_snapshot_is_cleared_with_its_context(fixture_ui, monkeypatch, action):
    monkeypatch.setattr(ui, 'build_general_kb', general_fixture_kb)
    app = fixture_ui
    app.button(key='build_kb').click().run()
    assert 'kb_result' in app.session_state
    if action == 'reset':
        app.button(key='reset').click().run()
    elif action == 'change_puzzle':
        app.selectbox(key='puzzle_index').set_value(1).run()
    else:
        app.radio(key='kb_representation').set_value('Definite / Horn').run()
    assert not app.exception
    assert 'kb_result' not in app.session_state
    assert not app.code


def test_kb_pagination_resets_after_filter(fixture_ui, monkeypatch):
    def larger_kb(*args):
        kb = general_fixture_kb()
        for _ in range(60):
            kb.tell(ui.atom('Is', 1, 1, 1))
        return kb
    monkeypatch.setattr(ui, 'build_general_kb', larger_kb)
    app = fixture_ui
    app.button(key='build_kb').click().run()
    assert len(app.code[0].value.splitlines()) == 50
    app.number_input(key='kb_page').set_value(2).run()
    assert len(app.code[0].value.splitlines()) == 13
    app.text_input(key='kb_search').set_value('~Is1_1_1').run()
    assert not app.exception
    assert app.number_input(key='kb_page').value == 1
    assert len(app.code[0].value.splitlines()) == 1


def test_kb_unavailable_and_bad_result_are_visible(fixture_ui, monkeypatch):
    def unavailable(*args):
        raise NotImplementedError
    monkeypatch.setattr(ui, 'build_general_kb', unavailable)
    app = fixture_ui
    app.button(key='build_kb').click().run()
    assert not app.exception
    assert any('General / CNF builder is not available yet' in item.value for item in app.info)
    monkeypatch.setattr(ui, 'build_general_kb', lambda *args: None)
    app.button(key='build_kb').click().run()
    assert not app.exception
    assert any('must return a PropKB' in item.value for item in app.warning)
    assert 'kb_result' not in app.session_state


def test_kb_snapshot_and_conversion_do_not_mutate_builder_result():
    kb = definite_fixture_kb()
    original = list(kb.clauses)
    snapshot = ui.snapshot_kb(kb, 'Definite / Horn', 1)
    snapshot['clauses'].clear()
    snapshot['cnf'].clear()
    assert kb.clauses == original


def test_board_selection_updates_query_and_clears_previous_answer(fixture_ui, monkeypatch):
    set_trace(monkeypatch, fixture_trace)
    app = submit_query(fixture_ui)
    assert 'query_result' in app.session_state
    app.button(key='cell_1_2').click().run()
    assert not app.exception
    assert app.session_state.selected_cell == (1, 2)
    assert app.number_input(key='query_row').value == 1
    assert app.number_input(key='query_col').value == 2
    assert app.number_input(key='query_value').value == 2
    assert 'query_result' not in app.session_state
    assert not app.slider
    app.button(key='cell_3_4').click().run()
    assert app.session_state.selected_cell == (3, 4)
    assert app.number_input(key='query_row').value == 3
    assert app.number_input(key='query_col').value == 4
    assert app.number_input(key='query_value').value == 2  # Empty cells preserve the proposed value.


def test_type_focus_and_search_combine_without_rebuilding_kb(fixture_ui, monkeypatch):
    calls = []
    def build(n, h, w, givens):
        calls.append(1)
        return ui.sudoku_solver.build_general_kb(n, h, w, givens)
    monkeypatch.setattr(ui, 'build_general_kb', build)
    app = fixture_ui
    app.button(key='build_kb').click().run()
    original = deepcopy(app.session_state.kb_result)
    app.number_input(key='kb_page').set_value(2).run()
    app.button(key='cell_2_2').click().run()
    assert app.number_input(key='kb_page').value == 1
    app.checkbox(key='kb_focus').check().run()
    app.multiselect(key='kb_types').set_value(['At least one value']).run()
    assert len(app.code[0].value.splitlines()) == 1
    assert 'Is2_2_1 | Is2_2_2 | Is2_2_3 | Is2_2_4' in app.code[0].value
    assert 'cell (2, 2)' in app.checkbox(key='kb_focus').label
    assert any('must contain at least one value' in item.value for item in app.markdown)
    app.button(key='cell_3_4').click().run()
    assert app.checkbox(key='kb_focus').value is True
    assert 'Is3_4_1 | Is3_4_2' in app.code[0].value
    # Coordinate inputs also drive the board and filter immediately, without inference.
    app.number_input(key='query_row').set_value(2).run()
    app.number_input(key='query_col').set_value(3).run()
    assert app.session_state.selected_cell == (2, 3)
    assert 'Is2_3_1 | Is2_3_2' in app.code[0].value
    app.text_input(key='kb_search').set_value('Is1_1_1').run()
    assert not app.code
    assert any('No clauses match' in item.value for item in app.info)
    assert calls == [1]
    assert app.session_state.kb_result == original
    assert 'Is1_1_1' in ui.kb_download(original, 'CNF')
    assert not app.exception


def test_fact_filter_and_cell_focus(fixture_ui, monkeypatch):
    monkeypatch.setattr(ui, 'build_general_kb', ui.sudoku_solver.build_general_kb)
    app = fixture_ui
    app.button(key='build_kb').click().run()
    app.multiselect(key='kb_types').set_value(['Fact']).run()
    assert len(app.code[0].value.splitlines()) == 3
    assert app.checkbox(key='kb_focus').disabled
    app.button(key='cell_1_4').click().run()
    app.checkbox(key='kb_focus').check().run()
    assert not app.code  # No fact is asserted for the empty cell.
    app.button(key='cell_1_2').click().run()
    assert len(app.code[0].value.splitlines()) == 1
    assert app.code[0].value.strip().endswith('Is1_2_2')
    app.multiselect(key='kb_types').set_value(['Fact', 'At least one value']).run()
    assert len(app.code[0].value.splitlines()) == 2
    app.button(key='reset').click().run()
    assert app.session_state.selected_cell is None
    assert 'kb_result' not in app.session_state
    assert 'kb_types' not in app.session_state
    assert not app.exception


@pytest.mark.parametrize('expression,expected', [
    ('Is1_1_1', ['Fact']),
    ('Is1_1_1 | Is1_1_2 | Is1_1_3 | Is1_1_4', ['At least one value']),
    ('~Is1_1_1 | ~Is1_1_2', ['At most one value']),
    ('~Is1_1_1 | ~Is1_4_1', ['Row uniqueness']),
    ('~Is1_1_1 | ~Is4_1_1', ['Column uniqueness']),
    ('~Is1_1_1 | ~Is2_2_1', ['Box uniqueness']),
    ('~Is1_1_1 | ~Is1_2_1', ['Row uniqueness', 'Box uniqueness']),
    ('~Is1_1_1 | ~Is2_1_1', ['Column uniqueness', 'Box uniqueness']),
    ('Is1_1_1 ==> Not1_2_1', ['Row uniqueness', 'Box uniqueness']),
    ('(Not1_1_1 & Not1_1_2 & Not1_1_3) ==> Is1_1_4', ['Last candidate']),
    ('Is1_1_1 | Is1_2_1', ['Other']),
])
def test_clause_types_are_classified_by_meaning(expression, expected):
    from utils import expr
    assert ui.clause_metadata(expr(expression), 4, 2, 2)['types'] == expected


def test_rectangular_box_classification_and_exact_cell_coordinates():
    from utils import expr
    assert ui.clause_metadata(expr('~Is5_4_1 | ~Is6_6_1'), 6, 2, 3)['types'] == ['Box uniqueness']
    assert ui.clause_metadata(expr('~Is2_3_1 | ~Is3_4_1'), 6, 2, 3)['types'] == ['Other']
    assert ui.clause_metadata(expr('~Is1_1_1 | ~Is1_10_1'), 16, 4, 4)['cells'] == [(1, 1), (1, 10)]


def test_horn_cnf_filters_keep_rule_meaning(fixture_ui, monkeypatch):
    monkeypatch.setattr(ui, 'build_definite_kb', definite_fixture_kb)
    app = fixture_ui
    app.radio(key='kb_representation').set_value('Definite / Horn').run()
    app.button(key='build_kb').click().run()
    app.multiselect(key='kb_types').set_value(['Row uniqueness']).run()
    app.button(key='cell_1_4').click().run()
    app.checkbox(key='kb_focus').check().run()
    assert len(app.code[0].value.splitlines()) == 1
    assert '==>' in app.code[0].value
    app.radio(key='kb_notation').set_value('CNF').run()
    assert len(app.code[0].value.splitlines()) == 1
    assert '~Is1_1_1' in app.code[0].value
    assert 'Not1_4_1' in app.code[0].value
    assert not app.exception


@pytest.mark.parametrize('action', ['reset', 'change_puzzle'])
def test_reset_clears_selection_without_selecting_another_cell(fixture_ui, monkeypatch, action):
    monkeypatch.setattr(ui, 'build_general_kb', ui.sudoku_solver.build_general_kb)
    app = fixture_ui
    app.button(key='cell_3_3').click().run()
    assert app.session_state.selected_cell == (3, 3)
    if action == 'reset':
        app.button(key='reset').click().run()
    else:
        app.selectbox(key='puzzle_index').set_value(1).run()
    assert app.session_state.selected_cell is None
    assert any('No cell selected' in item.value for item in app.caption)
    app.button(key='build_kb').click().run()
    assert app.checkbox(key='kb_focus').disabled
    assert not app.checkbox(key='kb_focus').value
    app.button(key='cell_2_2').click().run()
    assert not app.checkbox(key='kb_focus').disabled
    assert app.number_input(key='query_row').value == 2
    assert app.number_input(key='query_col').value == 2
    assert not app.exception


@pytest.mark.parametrize('method,name', [('Forward chaining', 'solve_full_grid_fc_with_trace'),
                                       ('Backward chaining', 'solve_full_grid_bc_with_trace')])
def test_solve_walkthrough_with_explicit_backend_fixture(fixture_ui, monkeypatch, method, name):
    # This controlled UI fixture asserts additional rules for the remaining
    # placements. It is not an inference result for the three-clue puzzle.
    steps = deepcopy(STEPS)
    established = {step['conclusion'] for step in steps}
    for (r, c), value in GRID.items():
        conclusion = str(ui.atom('Is', r, c, value))
        if conclusion not in established:
            steps.append({'conclusion': conclusion, 'premises': ['Is1_4_4'], 'reason': 'rule_application'})
    calls = []
    def traced(n, h, w, givens):
        calls.append(dict(givens))
        return {'grid': dict(GRID), 'steps': deepcopy(steps)}
    monkeypatch.setattr(ui.sudoku_solver, name, traced, raising=False)
    app = fixture_ui
    app.radio(key='algorithm').set_value(method)
    app.button(key='solve').click().run()
    assert not app.exception
    assert calls == [GIVENS]
    assert app.slider(key='solve_walk_step').value == 0
    assert app.slider(key='solve_walk_step').max == 13
    assert app.button(key='solve_walk_previous').disabled
    app.button(key='solve_walk_next').click().run()
    assert app.slider(key='solve_walk_step').value == 1
    assert any('4 / 16 cells filled' in item.value for item in app.caption)
    app.slider(key='solve_walk_step').set_value(13).run()
    assert app.button(key='solve_walk_next').disabled
    assert any('16 / 16 cells filled' in item.value for item in app.caption)
    app.radio(key='solve_walk_mode').set_value('All deductions').run()
    assert app.slider(key='solve_walk_step').value == 0
    assert app.slider(key='solve_walk_step').max == len(steps)
    app.button(key='solve_walk_next').click().run()
    set_trace(monkeypatch, fixture_trace)
    submit_query(app)
    assert app.slider(key='solve_walk_step').value == 1
    app.button(key='proof_next').click().run()
    assert app.slider(key='proof_step').value == 2
    app.button(key='solve_walk_previous').click().run()
    assert app.slider(key='proof_step').value == 2
    app.button(key='reset').click().run()
    assert not app.slider
    assert 'solution_result' not in app.session_state
    assert not app.exception


@pytest.mark.parametrize('steps', [[],
    [{'conclusion': 'Not1_1_1', 'premises': [], 'reason': 'rule_application'}],
    [{'conclusion': 'Is1_1_1', 'premises': ['Not1_1_1'], 'reason': 'last_candidate'}],
])
def test_frontend_rejects_invalid_solve_trace_without_backend_dependency(monkeypatch, steps):
    monkeypatch.setattr(ui.sudoku_solver, 'solve_full_grid_fc_with_trace',
                        lambda *args: {'grid': {(1, 1): 1}, 'steps': steps}, raising=False)
    with pytest.raises(ValueError):
        ui.solve_with_optional_trace('Forward chaining', 1, 1, 1, {})
