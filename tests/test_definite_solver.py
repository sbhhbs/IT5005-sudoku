"""Member 2 contract checks using real inference and independent expectations."""

from copy import deepcopy
from itertools import permutations, product
import json
from pathlib import Path
import random

import pytest
from streamlit.testing.v1 import AppTest

from logic_ import PropDefiniteKB, PropKB, conjuncts, pl_fc_entails
from utils import Expr, expr
import sudoku_solver as solver
from sudoku_solver import atom

ROOT = Path(__file__).resolve().parents[1]
POOL = json.loads((ROOT / 'puzzles.json').read_text())


def coordinates(mapping):
    return {tuple(map(int, key.split('_'))): value for key, value in mapping.items()}


def assert_proof(kb, result, givens=None, n=None, h=None, w=None):
    """Validate every edge against stored clauses, not private proof metadata."""
    json.dumps(result)
    seen = set()
    facts = {str(clause) for clause in kb.clauses if not clause.args}
    rules = {(frozenset(str(p) for p in conjuncts(clause.args[0])), str(clause.args[1]))
             for clause in kb.clauses if clause.op == '==>'}
    if not result['entailed']:
        assert result['steps'] == []
        return
    for step in result['steps']:
        conclusion, premises = step['conclusion'], step['premises']
        assert conclusion not in seen
        assert set(premises) <= seen
        if premises:
            assert (frozenset(premises), conclusion) in rules
        else:
            assert conclusion in facts
        if givens is not None:
            import sudoku_app as ui
            prefix, r, c, v = ui.parse_symbol(conclusion, n)
            reason = step['reason']
            decoded = [ui.parse_symbol(p, n) for p in premises]
            if reason == 'given':
                assert not premises and prefix == 'Is' and givens[r, c] == v
            elif reason == 'last_candidate':
                assert prefix == 'Is'
                assert {(p, rr, cc, vv) for p, rr, cc, vv in decoded} == {
                    ('Not', r, c, other) for other in range(1, n + 1) if other != v}
            else:
                assert prefix == 'Not' and len(decoded) == 1
                p, rr, cc, vv = decoded[0]
                assert p == 'Is'
                if reason == 'cell_elimination':
                    assert (rr, cc) == (r, c) and vv != v
                elif reason == 'row_elimination':
                    assert rr == r and cc != c and vv == v
                elif reason == 'column_elimination':
                    assert cc == c and rr != r and vv == v
                else:
                    assert reason == 'box_elimination'
                    assert (rr, cc) != (r, c) and vv == v
                    assert (rr - 1) // h == (r - 1) // h and (cc - 1) // w == (c - 1) // w
        seen.add(conclusion)
    assert result['steps'][-1]['conclusion'] == result['query']


@pytest.mark.parametrize('puzzle', POOL['puzzles'])
def test_both_full_solvers_and_every_bc_candidate_on_supplied_puzzles(puzzle):
    givens, expected = coordinates(puzzle['givens']), coordinates(puzzle['solution'])
    original = deepcopy(givens)
    for solve in (solver.solve_full_grid_fc, solver.solve_full_grid_bc):
        result = solve(9, 3, 3, givens)
        assert result == expected and result is not givens
        result.clear()
        assert givens == original
    kb = solver.build_definite_kb(9, 3, 3, givens)
    before = list(kb.clauses)
    for r, c, v in product(range(1, 10), repeat=3):
        assert solver.pl_bc_entails(kb, atom('Is', r, c, v)) is (expected[r, c] == v)
        assert solver.pl_bc_entails(kb, atom('Not', r, c, v)) is (expected[r, c] != v)
    for (r, c), v in expected.items():
        proof = solver.pl_bc_entails_with_trace(kb, atom('Is', r, c, v))
        assert_proof(kb, proof, givens, 9, 3, 3)
    # Use the same provided FC algorithm with an indexed copy to avoid repeated
    # full-clause scans on the 9x9 KB; indexing does not change the rules.
    fc_kb = solver.build_fc_index(kb)
    for query in (atom('Is', 1, 1, expected[1, 1]), atom('Is', 1, 1, expected[1, 1] % 9 + 1),
                  atom('Not', 1, 1, expected[1, 1] % 9 + 1)):
        assert pl_fc_entails(fc_kb, query) is solver.pl_bc_entails(kb, query)
    assert kb.clauses == before and givens == original


@pytest.mark.parametrize('n,h,w', [(1, 1, 1), (4, 2, 2), (6, 2, 3), (6, 3, 2)])
def test_dimensions_complete_inputs_and_fresh_results(n, h, w):
    expected = {(r + 1, c + 1): ((r % h) * w + r // h + c) % n + 1
                for r, c in product(range(n), repeat=2)}
    givens = {cell: v for cell, v in expected.items() if cell[0] != cell[1]}
    for solve in (solver.solve_full_grid_fc, solver.solve_full_grid_bc):
        assert solve(n, h, w, givens) == expected
        result = solve(n, h, w, expected)
        assert result == expected and result is not expected
    kb = solver.build_definite_kb(n, h, w, givens)
    assert_proof(kb, solver.pl_bc_entails_with_trace(kb, atom('Is', 1, 1, 1)), givens, n, h, w)


@pytest.mark.parametrize('solve', [solver.solve_full_grid_fc, solver.solve_full_grid_bc])
def test_unsolved_and_indirect_contradiction_are_errors_without_input_mutation(solve):
    for givens, message in [({}, 'determined 0 of 16'), ({(1, 1): 1}, 'could not be established'),
                            ({(1, 1): 1, (1, 2): 2, (1, 3): 3, (2, 4): 4}, 'Contradictory')]:
        before = deepcopy(givens)
        with pytest.raises(ValueError, match=message):
            solve(4, 2, 2, givens)
        assert givens == before


@pytest.mark.parametrize('n,h,w,givens', [
    (0, 1, 1, {}), (True, 1, 1, {}), (4, 2.0, 2, {}), (4, 1, 2, {}),
    (4, 2, 2, []), (4, 2, 2, {'1_1': 1}), (4, 2, 2, {(1,): 1}),
    (4, 2, 2, {(True, 1): 1}), (4, 2, 2, {(1, 1): True}),
    (4, 2, 2, {(0, 1): 1}), (4, 2, 2, {(1, 1): 5}),
    (4, 2, 2, {(1, 1): 1, (1, 4): 1}),
    (4, 2, 2, {(1, 1): 1, (4, 1): 1}),
    (4, 2, 2, {(1, 1): 1, (2, 2): 1}),
])
def test_invalid_inputs_are_rejected_before_building(n, h, w, givens):
    original = deepcopy(givens)
    for function in (solver.build_definite_kb, solver.solve_full_grid_fc, solver.solve_full_grid_bc):
        with pytest.raises(ValueError):
            function(n, h, w, givens)
    assert givens == original


def make_kb(sentences):
    kb = PropDefiniteKB()
    for sentence in sentences:
        kb.tell(expr(sentence))
    return kb


def test_generic_cycles_alternatives_and_rule_order():
    for sentences in permutations(['A ==> B', 'B ==> A', 'C ==> A', 'C']):
        kb = make_kb(sentences)
        for name in ['B', 'A', 'D', 'C', 'A']:
            query = expr(name)
            assert solver.pl_bc_entails(kb, query) is pl_fc_entails(kb, query)
            trace = solver.pl_bc_entails_with_trace(kb, query)
            assert_proof(kb, trace)
            assert all(step['reason'] == 'rule_application' for step in trace['steps'])
    kb = make_kb(['A ==> B', 'B ==> A', '(A & C) ==> D', 'C'])
    assert solver.pl_bc_entails(kb, expr('D')) is False
    assert solver.pl_bc_entails(kb, expr('A')) is False
    # A branch-local failure of B while proving A must not poison later proofs.
    kb = make_kb(['(B & D) ==> A', 'A ==> B', 'C ==> A', 'C', 'D'])
    assert solver.pl_bc_entails(kb, expr('A')) is True
    assert solver.pl_bc_entails(kb, expr('B')) is True


def test_random_small_horn_kbs_match_provided_fc():
    rng = random.Random(23)
    names = list('ABCDEFGH')
    for _ in range(40):
        facts = rng.sample(names, rng.randrange(4))
        sentences = facts + [f'({" & ".join(rng.sample(names, rng.randint(1, 3)))}) ==> {rng.choice(names)}'
                             for _ in range(14)]
        kb = make_kb(list(dict.fromkeys(sentences)))
        rng.shuffle(names)
        for name in names:
            query = expr(name)
            assert solver.pl_bc_entails(kb, query) is pl_fc_entails(kb, query)
            assert_proof(kb, solver.pl_bc_entails_with_trace(kb, query))


def test_cache_invalidation_and_fresh_trace_snapshots():
    kb = make_kb(['A ==> B', 'B ==> C'])
    assert solver.pl_bc_entails(kb, expr('C')) is False
    kb.tell(expr('A'))
    trace = solver.pl_bc_entails_with_trace(kb, expr('C'))
    assert trace['entailed'] is True
    trace['steps'][0]['conclusion'] = 'CORRUPTED'
    trace['steps'][-1]['premises'].clear()
    assert_proof(kb, solver.pl_bc_entails_with_trace(kb, expr('C')))
    kb.retract(expr('A'))
    assert solver.pl_bc_entails(kb, expr('C')) is False
    kb.clauses[:] = [expr('C')]
    assert solver.pl_bc_entails_with_trace(kb, expr('C'))['steps'] == [
        {'conclusion': 'C', 'premises': [], 'reason': 'rule_application'}]


def test_long_proof_does_not_depend_on_python_recursion_depth():
    kb = make_kb(['P0'] + [f'P{i} ==> P{i+1}' for i in range(1100)])
    trace = solver.pl_bc_entails_with_trace(kb, expr('P1100'))
    assert len(trace['steps']) == 1101
    assert_proof(kb, trace)


def test_partial_puzzle_queries_given_failed_and_excluded():
    givens = {(1, 1): 1, (1, 2): 2, (1, 3): 3}
    kb = solver.build_definite_kb(4, 2, 2, givens)
    before = list(kb.clauses)
    given = solver.pl_bc_entails_with_trace(kb, atom('Is', 1, 1, 1))
    assert given['steps'] == [{'conclusion': 'Is1_1_1', 'premises': [], 'reason': 'given'}]
    for prefix, r, c, v, expected in [('Is', 1, 4, 4, True), ('Is', 1, 4, 1, False),
                                     ('Not', 1, 4, 1, True), ('Is', 4, 4, 1, False)]:
        query = atom(prefix, r, c, v)
        trace = solver.pl_bc_entails_with_trace(kb, query)
        assert trace['entailed'] is expected
        assert solver.pl_bc_entails(kb, query) is expected
        assert_proof(kb, trace, givens, 4, 2, 2)
    assert kb.clauses == before


def test_invalid_generic_kbs_and_queries():
    for query in ['A', True, expr('~A'), expr('A & B'), Expr('P', expr('x'))]:
        with pytest.raises(ValueError):
            solver.pl_bc_entails(make_kb(['A']), query)
    with pytest.raises(ValueError):
        solver.pl_bc_entails(PropKB(), expr('A'))
    for invalid in [True, expr('~A'), expr('A | B'), expr('P(x)'), Expr('==>', True, expr('A'))]:
        kb = make_kb(['A'])
        kb.clauses.append(invalid)
        with pytest.raises(ValueError):
            solver.pl_bc_entails(kb, expr('A'))


def test_fc_solver_calls_original_library_algorithm(monkeypatch):
    calls = []
    def observed(kb, query):
        before = list(kb.clauses)
        calls.append(query)
        result = pl_fc_entails(kb, query)
        assert kb.clauses == before
        return result
    monkeypatch.setattr(solver, 'pl_fc_entails', observed)
    assert solver.solve_full_grid_fc(1, 1, 1, {}) == {(1, 1): 1}
    assert len(calls) == 1


@pytest.mark.parametrize('method', ['Forward chaining', 'Backward chaining'])
def test_real_frontend_solve_and_trace(method):
    app = AppTest.from_file(str(ROOT / 'sudoku_app.py'), default_timeout=15).run()
    app.radio(key='algorithm').set_value(method)
    app.button(key='solve').click().run()
    assert not app.exception
    assert app.session_state.solution_result['grid'] == coordinates(POOL['puzzles'][0]['solution'])
    app.button(key='cell_2_2').click().run()
    assert app.number_input(key='query_value').value == 9
    app.button(key='check_cell').click().run()
    assert not app.exception
    assert app.session_state.query_result['positive']['entailed'] is True
    assert app.session_state.query_result['trace_available'] is True
    assert len(app.session_state.query_result['positive']['steps']) > 1
    app.slider(key='proof_step').set_value(len(app.session_state.query_result['positive']['steps'])).run()
    app.number_input(key='query_value').set_value(1).run()
    app.button(key='check_cell').click().run()
    assert not app.exception
    assert app.session_state.query_result['positive']['entailed'] is False
    assert app.session_state.query_result['exclusion']['entailed'] is True
    app.radio(key='kb_representation').set_value('Definite / Horn').run()
    app.button(key='build_kb').click().run()
    assert not app.exception
    assert app.session_state.kb_result['implications'] > 0


@pytest.mark.parametrize('puzzle', POOL['puzzles'])
@pytest.mark.parametrize('method', ['fc', 'bc'])
def test_full_solve_trace_is_ordered_truthful_and_reaches_reference_grid(puzzle, method):
    givens = coordinates(puzzle['givens'])
    before = deepcopy(givens)
    solve = getattr(solver, f'solve_full_grid_{method}_with_trace')
    result = solve(9, 3, 3, givens)
    assert result['grid'] == coordinates(puzzle['solution'])
    kb = solver.build_definite_kb(9, 3, 3, givens)
    assert_proof(kb, {'query': result['steps'][-1]['conclusion'], 'entailed': True, 'steps': result['steps']},
                 givens, 9, 3, 3)
    import sudoku_app as ui
    assert ui.replay_solve(result['steps'], -1, givens, 9) == givens
    assert ui.replay_solve(result['steps'], len(result['steps']) - 1, givens, 9) == result['grid']
    assert len(ui.solve_checkpoints(result['steps'], givens, 9, 'Cell placements')) == 81 - len(givens)
    for step in result['steps']:
        prefix, r, c, v = ui.parse_symbol(step['conclusion'], 9)
        assert (prefix == 'Is') == (result['grid'][r, c] == v)
    result['grid'].clear()
    result['steps'][-1]['premises'].clear()
    assert givens == before


def test_fc_walkthrough_uses_fc_without_calling_bc(monkeypatch):
    calls = []
    def observed(kb, query):
        calls.append(query)
        return pl_fc_entails(kb, query)
    def no_bc(*args):
        raise AssertionError('An FC walkthrough must not be reconstructed using BC.')
    monkeypatch.setattr(solver, 'pl_fc_entails', observed)
    monkeypatch.setattr(solver, 'bc_ask', no_bc)
    result = solver.solve_full_grid_fc_with_trace(1, 1, 1, {})
    assert calls and result['grid'] == {(1, 1): 1}
    assert result['steps'] == [{'conclusion': 'Is1_1_1', 'premises': [], 'reason': 'last_candidate'}]


@pytest.mark.parametrize('method', ['fc', 'bc'])
def test_ambiguous_puzzle_never_selects_an_arbitrary_solution(method):
    # Two explicit valid completions share these same first-row givens.
    first = {(r + 1, c + 1): v for r, row in enumerate([
        [1, 2, 3, 4], [3, 4, 1, 2], [2, 1, 4, 3], [4, 3, 2, 1]]) for c, v in enumerate(row)}
    second = {(r, c): first[(7 - r if r >= 3 else r), c] for r, c in first}
    givens = {(1, c): first[1, c] for c in range(1, 5)}
    import sudoku_app as ui
    assert first != second
    assert ui.validate_grid(first, givens, 4, 2, 2) == first
    assert ui.validate_grid(second, givens, 4, 2, 2) == second
    with pytest.raises(ValueError, match='determined 4 of 16'):
        getattr(solver, f'solve_full_grid_{method}_with_trace')(4, 2, 2, givens)


@pytest.mark.parametrize('method', ['Forward chaining', 'Backward chaining'])
def test_real_solve_walkthrough_navigation_and_query_independence(method):
    import sudoku_app as ui
    app = AppTest.from_file(str(ROOT / 'sudoku_app.py'), default_timeout=15).run()
    app.radio(key='algorithm').set_value(method)
    app.button(key='solve').click().run()
    assert not app.exception
    assert app.slider(key='solve_walk_step').value == 0
    assert app.slider(key='solve_walk_step').max == 51
    assert app.button(key='solve_walk_previous').disabled
    result = app.session_state.solution_result
    clues = coordinates(POOL['puzzles'][0]['givens'])
    app.button(key='solve_walk_next').click().run()
    assert app.slider(key='solve_walk_step').value == 1
    first = ui.solve_checkpoints(result['steps'], clues, 9, 'Cell placements')[0]
    assert len(ui.replay_solve(result['steps'], first, clues, 9)) == 31
    app.slider(key='solve_walk_step').set_value(51).run()
    assert app.button(key='solve_walk_next').disabled
    app.radio(key='solve_walk_mode').set_value('All deductions').run()
    assert app.slider(key='solve_walk_step').value == 0
    assert app.slider(key='solve_walk_step').max == len(result['steps'])
    app.button(key='solve_walk_next').click().run()
    app.button(key='cell_2_2').click().run()
    app.button(key='check_cell').click().run()
    assert app.slider(key='solve_walk_step').value == 1
    app.button(key='proof_next').click().run()
    assert app.slider(key='proof_step').value == 2
    assert app.slider(key='solve_walk_step').value == 1
    app.button(key='solve_walk_previous').click().run()
    assert app.slider(key='proof_step').value == 2
    app.button(key='solve').click().run()
    assert app.slider(key='solve_walk_step').value == 0
    app.button(key='reset').click().run()
    assert 'solution_result' not in app.session_state
    assert not app.slider
    assert not app.exception


@pytest.mark.parametrize('steps', [[],
    [{'conclusion': 'Not1_1_1', 'premises': [], 'reason': 'rule_application'}],
    [{'conclusion': 'Is1_1_1', 'premises': ['Not1_1_1'], 'reason': 'last_candidate'}],
])
def test_frontend_rejects_malformed_or_contradictory_full_trace(monkeypatch, steps):
    import sudoku_app as ui
    monkeypatch.setattr(solver, 'solve_full_grid_fc_with_trace',
                        lambda *args: {'grid': {(1, 1): 1}, 'steps': steps})
    with pytest.raises(ValueError):
        ui.solve_with_optional_trace('Forward chaining', 1, 1, 1, {})
