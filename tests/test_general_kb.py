"""Check the integrated general KB against the original assignment library."""

import json
from copy import deepcopy
from itertools import combinations, product
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from logic_ import PropKB, associate, pl_resolution, pl_true, prop_symbols, tt_entails
from sudoku_solver import atom, build_general_kb


ROOT = Path(__file__).resolve().parents[1]
POOL = json.loads((ROOT / 'puzzles.json').read_text())


@pytest.mark.parametrize('puzzle', POOL['puzzles'])
def test_reference_solution_satisfies_every_clause_without_mutating_givens(puzzle):
    givens = {tuple(map(int, key.split('_'))): value
              for key, value in puzzle['givens'].items()}
    original = deepcopy(givens)
    kb = build_general_kb(9, 3, 3, givens)
    assert isinstance(kb, PropKB)
    assert givens == original
    assert len(kb.clauses) == 11745 + len(givens)
    model = {atom('Is', r, c, v): puzzle['solution'][f'{r}_{c}'] == v
             for r, c, v in product(range(1, 10), repeat=3)}
    assert all(pl_true(clause, model) is True for clause in kb.clauses)
    assert prop_symbols(associate('&', kb.clauses)) == set(model)
    assert all(atom('Is', r, c, v) in kb.clauses for (r, c), v in givens.items())


@pytest.mark.parametrize('n,h,w', [(4, 2, 2), (6, 2, 3), (6, 3, 2)])
def test_every_cell_and_peer_constraint_including_rectangular_boxes(n, h, w):
    kb = build_general_kb(n, h, w, {})
    clauses = set(kb.clauses)
    cells = list(product(range(1, n + 1), repeat=2))
    expected_symbols = {atom('Is', r, c, v) for r, c in cells for v in range(1, n + 1)}
    # No out-of-range symbols, including rightmost/bottom rectangular boxes.
    assert prop_symbols(associate('&', kb.clauses)) == expected_symbols
    for r, c in cells:
        assert associate('|', [atom('Is', r, c, v) for v in range(1, n + 1)]) in clauses
        for a, b in combinations(range(1, n + 1), 2):
            assert (~atom('Is', r, c, a) | ~atom('Is', r, c, b)) in clauses
    for (r1, c1), (r2, c2) in combinations(cells, 2):
        same_box = (r1 - 1) // h == (r2 - 1) // h and (c1 - 1) // w == (c2 - 1) // w
        if r1 == r2 or c1 == c2 or same_box:
            for v in range(1, n + 1):
                assert (~atom('Is', r1, c1, v) | ~atom('Is', r2, c2, v)) in clauses


def test_tiny_grid_models_match_sudoku_rules_exactly():
    kb = build_general_kb(2, 1, 2, {})
    symbols = [atom('Is', r, c, v) for r, c, v in product((1, 2), repeat=3)]
    accepted = []
    for values in product((False, True), repeat=8):
        model = dict(zip(symbols, values))
        if all(pl_true(clause, model) is True for clause in kb.clauses):
            accepted.append({str(symbol) for symbol, value in model.items() if value})
    assert accepted == [
        {'Is1_1_2', 'Is1_2_1', 'Is2_1_1', 'Is2_2_2'},
        {'Is1_1_1', 'Is1_2_2', 'Is2_1_2', 'Is2_2_1'},
    ]


@pytest.mark.parametrize('method', ['resolution', 'truth_table'])
def test_provided_inference_can_prove_and_reject_tiny_grid_queries(method):
    kb = build_general_kb(2, 1, 2, {(1, 1): 1})
    before = list(kb.clauses)
    def entails(query):
        return (pl_resolution(kb, query) if method == 'resolution'
                else tt_entails(associate('&', kb.clauses), query))
    assert entails(atom('Is', 2, 2, 1)) is True
    assert entails(atom('Is', 2, 2, 2)) is False
    assert kb.clauses == before


def test_app_generates_real_general_kb_and_download():
    import sudoku_app as ui

    app = AppTest.from_file(str(ROOT / 'sudoku_app.py'), default_timeout=15).run()
    app.button(key='build_kb').click().run()
    assert not app.exception
    count = len(POOL['puzzles'][0]['givens'])
    assert [metric.value for metric in app.metric] == [str(11745 + count), '729', str(count)]
    assert len(app.code[0].value.splitlines()) == 50
    snapshot = app.session_state.kb_result
    downloaded = ui.kb_download(snapshot, 'CNF')
    assert 'Is1_1_1' in downloaded
    assert f'clauses: {11745 + count}' in downloaded
    app.text_input(key='kb_search').set_value('~Is9_9_9').run()
    assert not app.exception
    assert all('~Is9_9_9' in line for line in app.code[0].value.splitlines())
