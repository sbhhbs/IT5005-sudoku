"""Focused checks for FC walkthroughs on the supplied course puzzles."""

from copy import deepcopy
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from logic_ import conjuncts, pl_fc_entails
import sudoku_solver as solver

ROOT = Path(__file__).resolve().parents[1]
POOL = json.loads((ROOT / 'puzzles.json').read_text())


def coordinates(mapping):
    return {tuple(map(int, key.split('_'))): value for key, value in mapping.items()}


@pytest.mark.parametrize('puzzle', POOL['puzzles'])
def test_fc_walkthrough_uses_supplied_fc_and_proves_the_grid(puzzle, monkeypatch):
    givens, expected = coordinates(puzzle['givens']), coordinates(puzzle['solution'])
    original = deepcopy(givens)
    calls, clauses = [], []

    def observed(kb, query):
        if not clauses:
            clauses.extend(kb.clauses)
        calls.append(str(query))
        before = list(kb.clauses)
        result = pl_fc_entails(kb, query)
        assert kb.clauses == before
        return result

    def no_bc(*args, **kwargs):
        raise AssertionError('FC walkthrough must not run BC.')

    monkeypatch.setattr(solver, 'pl_fc_entails', observed)
    monkeypatch.setattr(solver, 'bc_ask', no_bc)
    result = solver.solve_full_grid_fc_with_trace(9, 3, 3, givens)
    assert result['grid'] == expected and givens == original
    # Each API must invoke the supplied FC routine once, not once per candidate.
    assert len(calls) == 1
    calls.clear()
    assert solver.solve_full_grid_fc(9, 3, 3, givens) == expected
    assert len(calls) == 1 and givens == original
    rules = {(frozenset(map(str, conjuncts(clause.args[0]))), str(clause.args[1]))
             for clause in clauses if clause.op == '==>'}
    facts = {str(solver.atom('Is', r, c, v)) for (r, c), v in givens.items()}
    seen = set()
    for step in result['steps']:
        conclusion, premises = step['conclusion'], step['premises']
        assert conclusion not in seen and set(premises) <= seen
        if premises:
            assert (frozenset(premises), conclusion) in rules
        else:
            assert conclusion in facts and step['reason'] == 'given'
        seen.add(conclusion)
    assert {str(solver.atom('Is', r, c, v)) for (r, c), v in expected.items()} <= seen
    json.dumps(result['steps'])


def test_frontend_can_step_through_real_fc_walkthrough():
    app = AppTest.from_file(str(ROOT / 'sudoku_app.py'), default_timeout=60).run()
    app.button(key='solve').click().run()
    assert not app.exception
    assert app.session_state.solution_result['grid'] == coordinates(POOL['puzzles'][0]['solution'])
    assert app.slider(key='solve_walk_step').value == 0
    assert app.slider(key='solve_walk_step').max == 51
    app.button(key='solve_walk_next').click().run()
    assert app.slider(key='solve_walk_step').value == 1
    app.button(key='solve_walk_previous').click().run()
    assert app.slider(key='solve_walk_step').value == 0
    app.slider(key='solve_walk_step').set_value(51).run()
    assert app.button(key='solve_walk_next').disabled
    assert not app.exception


@pytest.mark.parametrize('solve', [solver.solve_full_grid_fc, solver.solve_full_grid_fc_with_trace])
def test_single_pass_does_not_return_an_incomplete_grid(solve):
    givens = {(1, 1): 1}
    with pytest.raises(ValueError, match='No value could be established'):
        solve(9, 3, 3, givens)
    assert givens == {(1, 1): 1}
