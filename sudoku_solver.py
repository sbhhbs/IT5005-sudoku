"""IT5005 Assignment 1: student implementation file.

Implement the functions marked below. Do not modify utils.py or logic_.py.
"""

from utils import *
from logic_ import *


# Do not change this function; it is used to create atomic propositions.
def atom(prefix, r, c, v):
    """prefix is 'Is' or 'Not'. Returns the Expr for e.g. Is3_2_4."""
    return expr(f'{prefix}{r}_{c}_{v}')

# 2.2.2. Build KB
def build_general_kb(n, box_h, box_w, givens):
    """Return a PropKB encoding this n x n Sudoku's constraints plus the given
    cells, as general clauses.

    Adapted from Serim's general-KB implementation. Uses the supplied PropKB
    and Expr classes; givens are read without mutation. Box dimensions must
    be positive, tile the grid, and satisfy box_h * box_w == n.
    Stored clauses include duplicate row/column constraints within boxes.

    Parameters
    ----------
    n, box_h, box_w : int
    givens : dict[(int, int), int]

    Returns
    -------
    PropKB
    """
    kb = PropKB()

    # 1. Each cell has at least one value
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            clause = associate('|', [atom('Is', r, c, v) for v in range(1, n + 1)])
            kb.tell(clause)

    # 2. Each cell has at most one value
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v1 in range(1, n + 1):
                for v2 in range(v1 + 1, n + 1):
                    clause = Expr('|', Expr('~', atom('Is', r, c, v1)), Expr('~', atom('Is', r, c, v2)))
                    kb.tell(clause)

    # 3. No two cells in same row have same value
    for r in range(1, n + 1):
        for v in range(1, n + 1):
            for c1 in range(1, n + 1):
                for c2 in range(c1 + 1, n + 1):
                    clause = Expr('|', Expr('~', atom('Is', r, c1, v)), Expr('~', atom('Is', r, c2, v)))
                    kb.tell(clause)

    # 4. No two cells in same column have same value
    for c in range(1, n + 1):
        for v in range(1, n + 1):
            for r1 in range(1, n + 1):
                for r2 in range(r1 + 1, n + 1):
                    clause = Expr('|', Expr('~', atom('Is', r1, c, v)), Expr('~', atom('Is', r2, c, v)))
                    kb.tell(clause)

    # 5. No two cells in same box have same value. Iterate the number of
    # boxes along each axis (not the dimensions of a single box).
    for box_r in range(n // box_h):
        for box_c in range(n // box_w):
            for v in range(1, n + 1):
                cells_in_this_box = []
                for r in range(box_r * box_h + 1, (box_r + 1) * box_h + 1):
                    for c in range(box_c * box_w + 1, (box_c + 1) * box_w + 1):
                        cells_in_this_box.append((r, c))
                for i, (r1, c1) in enumerate(cells_in_this_box):
                    for (r2, c2) in cells_in_this_box[i + 1:]:
                        clause = Expr('|', Expr('~', atom('Is', r1, c1, v)), Expr('~', atom('Is', r2, c2, v)))
                        kb.tell(clause)

    # 6. Givens
    for (r, c), v in givens.items():
        kb.tell(atom('Is', r, c, v))

    return kb

def _validate_sudoku_inputs(n, box_h, box_w, givens):
    """Reject malformed or directly conflicting clues without mutating them."""
    if any(type(x) is not int or x <= 0 for x in (n, box_h, box_w)) or box_h * box_w != n:
        raise ValueError('Dimensions must be positive integers with box_h * box_w == n.')
    if not isinstance(givens, dict):
        raise ValueError('Givens must be a dictionary mapping (row, column) to value.')
    rows, columns, boxes = set(), set(), set()
    for cell, value in givens.items():
        if (not isinstance(cell, tuple) or len(cell) != 2
                or any(type(x) is not int or not 1 <= x <= n for x in cell)
                or type(value) is not int or not 1 <= value <= n):
            raise ValueError('Every given needs integer coordinates and a value in 1..n; booleans are not allowed.')
        r, c = cell
        row, column, box = (r, value), (c, value), ((r - 1) // box_h, (c - 1) // box_w, value)
        if row in rows or column in columns or box in boxes:
            raise ValueError('Contradictory givens repeat a value in a row, column, or box.')
        rows.add(row)
        columns.add(column)
        boxes.add(box)


def _is_atomic_proposition(value):
    return isinstance(value, Expr) and not value.args and is_prop_symbol(value.op)


def _parse_horn_clause(clause):
    """Validate before calling helpers that assume a well-formed clause."""
    if _is_atomic_proposition(clause):
        return (), clause
    if not isinstance(clause, Expr) or clause.op != '==>' or len(clause.args) != 2:
        raise ValueError('The KB contains a non-propositional or non-definite clause.')
    antecedent, head = clause.args
    premises, pending = [], [antecedent]
    while pending:
        item = pending.pop()
        if isinstance(item, Expr) and item.op == '&' and item.args:
            pending.extend(reversed(item.args))
        elif _is_atomic_proposition(item):
            premises.append(item)
        else:
            raise ValueError('Every Horn premise must be a positive atomic proposition.')
    if not premises or not _is_atomic_proposition(head):
        raise ValueError('Every Horn rule must conclude a positive atomic proposition.')
    return tuple(dict.fromkeys(premises)), head


# 2.2.2. Build KB
def build_definite_kb(n, box_h, box_w, givens):
    """Return a PropDefiniteKB encoding this n x n Sudoku's constraints plus
    the given cells, using elimination + last-candidate reasoning.

    Parameters
    ----------
    n, box_h, box_w : int
    givens : dict[(int, int), int] -- {(row, col): value}, 1-indexed

    Returns
    -------
    PropDefiniteKB
    """
    _validate_sudoku_inputs(n, box_h, box_w, givens)
    kb = PropDefiniteKB()
    # Private geometry and original clues distinguish facts from later deductions.
    kb._sudoku_context = (n, box_h, box_w, dict(givens))

    # Condition 6 (Facts): givens directly imply Is_r_c_v
    # Is_r_c_v
    for (r, c), v in givens.items():
        kb.tell(atom('Is', r, c, v))

    # Condition 2 (Rules): A cell cannot have two different values
    # Is_r_c_v => Not_r_c_w (for v != w)
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v in range(1, n + 1):
                for w in range(1, n + 1):
                    if v != w:
                        # If (1,1)=3, then the (1,1) cell cannot have any other value:
                        # Is1_1_3 ==> Not1_1_1, Is1_1_3 ==> Not1_1_2, Is1_1_3 ==> Not1_1_4 ... Is1_1_3 ==> Not1_1_9
                        rule = expr(f'{atom("Is", r, c, v)} ==> {atom("Not", r, c, w)}')
                        kb.tell(rule)

    # Condition 3 (Rules): No two cells in the same row have the same value
    # Is_r_c1_v => Not_r_c2_v (for c1 != c2)
    for r in range(1, n + 1):
        for v in range(1, n + 1):
            for c1 in range(1, n + 1):
                for c2 in range(1, n + 1):
                    if c1 != c2:
                        # If (1,1)=3, then every other cell in row 1 cannot be 3:
                        # Is1_1_3 ==> Not1_2_3, Is1_1_3 ==> Not1_3_3, ... Is1_1_3 ==> Not1_9_3
                        rule = expr(f'{atom("Is", r, c1, v)} ==> {atom("Not", r, c2, v)}')
                        kb.tell(rule)

    # Condition 4 (Rules): No two cells in the same column have the same value
    # Is_r1_c_v => Not_r2_c_v (for r1 != r2)
    for c in range(1, n + 1):
        for v in range(1, n + 1):
            for r1 in range(1, n + 1):
                for r2 in range(1, n + 1):
                    if r1 != r2:
                        rule = expr(f'{atom("Is", r1, c, v)} ==> {atom("Not", r2, c, v)}')
                        kb.tell(rule)

    # Condition 5 (Rules): No two cells in the same box have the same value
    # Is_r1_c1_v => Not_r2​_c2​_v, where (r1,c1) and (r2,c2) are in the same box
    for box_r in range(n // box_h):
        for box_c in range(n // box_w):
            cells_in_box = []
            for r in range(box_r * box_h + 1, (box_r + 1) * box_h + 1):
                for c in range(box_c * box_w + 1, (box_c + 1) * box_w + 1):
                    cells_in_box.append((r, c))

            for v in range(1, n + 1):
                for (r1, c1) in cells_in_box:
                    for (r2, c2) in cells_in_box:
                        if (r1, c1) != (r2, c2):
                            rule = expr(f'{atom("Is", r1, c1, v)} ==> {atom("Not", r2, c2, v)}')
                            kb.tell(rule)

    # Condition 1 (Rules): Every cell has at least one value.
    # In general KB, Is_r_c_1 ∨ Is_r_c_2 ∨ ... ∨ Is_r_c_n
    # In definite clause, Not_r_c_1 ∧ ... ∧ Not_r_c_{v-1} ∧ Not_r_c_{v+1}... ∧ Not_r_c_n => Is_r_c_v
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v in range(1, n + 1):
                other_values = [atom('Not', r, c, w) for w in range(1, n + 1) if w != v]
                antecedent = associate('&', other_values)
                # A 1x1 grid has one forced value and no elimination premises.
                rule = Expr('==>', antecedent, atom('Is', r, c, v)) if other_values else atom('Is', r, c, v)
                kb.tell(rule)
    
    return kb


# ---------------------------------------------------------------------------
# Shared KB indexing helper
# ---------------------------------------------------------------------------

def _index_clauses(clauses):
    """Index Definite KB into following data structures, 
    so that we can reference the c.CONCLUSION as a key to find the c.PREMISE:

    facts = {Is1_1_3, ...}
    rules_by_conclusion = {
        Not1_1_4: [(Is1_1_3,), ...],
        Is1_1_4: [(Not1_1_1, Not1_1_2, Not1_1_3), ...],
    }
    """
    facts = set()
    rules_by_conclusion = {}

    for clause in clauses:
        premises, conclusion = _parse_horn_clause(clause)
        if premises:
            rules_by_conclusion.setdefault(conclusion, []).append(tuple(premises))
        else:
            facts.add(conclusion)

    for conclusion, alternatives in rules_by_conclusion.items():
        seen, unique_rules = set(), []
        for premises in alternatives:
            if premises not in seen:
                seen.add(premises)
                unique_rules.append(premises)
        unique_rules.sort(key=lambda premises: (len(premises),
                                                sum(p not in facts for p in premises)))
        rules_by_conclusion[conclusion] = unique_rules

    return facts, rules_by_conclusion


# Returns the saved result if called by same clause list,
# otherwise call _index_clauses() and save the result if the clauses are new.
_index_memo = memoize(_index_clauses, maxsize=4)


def build_bc_index(kb):
    """Build the search index for the large KB once and reuse it, 
    but do not modify the original KB or the cached index.

        facts               : set of atomic Exprs asserted without premises.
        rules_by_conclusion : {conclusion: [tuple_of_premises, ...]}
    """
    if not isinstance(kb, PropDefiniteKB):
        raise ValueError('kb must be a PropDefiniteKB.')
    signature = tuple(kb.clauses)
    cached = getattr(kb, '_bc_index_cache', None)
    if cached is None or cached[0] != signature:
        for clause in signature:
            _parse_horn_clause(clause)
        cached = (signature, _index_memo(signature))
        kb._bc_index_cache = cached
    return cached[1]


# ---------------------------------------------------------------------------
# 2.3 (b) Forward chaining on the full grid
# ---------------------------------------------------------------------------

def build_fc_index(kb):
    """Copy a definite KB with a premise index; leave its logical clauses intact.

    Duplicate clauses and repeated premises are normalized in this private copy
    so the supplied FC counter processes each logical premise exactly once.
    """
    build_bc_index(kb)  # Validate the public input before using library helpers.
    indexed_kb = PropDefiniteKB()
    normalized = {}
    premise_index = {}
    for clause in kb.clauses:
        premises, head = _parse_horn_clause(clause)
        rule = Expr('==>', associate('&', premises), head) if premises else head
        normalized.setdefault(rule, premises)
    indexed_kb.clauses = list(normalized)
    for clause, premises in normalized.items():
        for premise in premises:
            premise_index.setdefault(premise, []).append(clause)
    indexed_kb.clauses_with_premise = lambda p: premise_index.get(p, [])
    return indexed_kb


def _check_sudoku_contradictions(kb, symbols):
    """Check encountered Is/Not conflicts only for a KB with Sudoku metadata."""
    if not hasattr(kb, '_sudoku_context'):
        return
    positives, negatives = {}, set()
    for symbol in symbols:
        try:
            prefix, r, c, v = decode_atom(symbol)
        except ValueError:
            continue
        if prefix == 'Not':
            negatives.add((r, c, v))
        else:
            if (r, c) in positives and positives[r, c] != v:
                raise ValueError(f'Contradictory conclusions assign multiple values to cell ({r}, {c}).')
            positives[r, c] = v
    for (r, c), v in positives.items():
        if (r, c, v) in negatives:
            raise ValueError(f'Contradictory conclusions: cell ({r}, {c}) is both {v} and not {v}.')


def _complete_grid(kb, known, n, box_h, box_w, givens):
    """Return a fresh complete grid or an error, never partial or guessed values."""
    _check_sudoku_contradictions(kb, known)
    grid = {}
    for symbol in known:
        prefix, r, c, v = decode_atom(symbol)
        if prefix == 'Is':
            grid[r, c] = v
    if len(grid) != n * n:
        raise ValueError(f'The current Horn rules determined {len(grid)} of {n*n} cells. '
                         'A complete grid could not be established without stronger reasoning.')
    _validate_sudoku_inputs(n, box_h, box_w, grid)
    if any(grid[cell] != value for cell, value in givens.items()):
        raise ValueError('The inferred grid changed an original given.')
    return grid


def _solve_fc(n, box_h, box_w, givens, with_trace=False):
    """Observe one complete run of the unchanged supplied FC algorithm.

    The absent probe exhausts the agenda. Its premise-lookup callback records
    processed atoms and the rules about to fire, without a second inference
    engine or a BC reconstruction. Plain and traced solving use this same run.
    """
    kb = build_definite_kb(n, box_h, box_w, givens)
    fc_kb = build_fc_index(kb)
    lookup = fc_kb.clauses_with_premise
    known, why, steps = set(), {}, []

    def observed_lookup(symbol):
        known.add(symbol)
        if with_trace:
            premises = why.get(symbol, ())
            steps.append(_proof_step(symbol, premises, kb))
        clauses = lookup(symbol)
        if with_trace:
            for clause in clauses:
                premises = tuple(conjuncts(clause.args[0]))
                if all(p in known for p in premises):
                    why.setdefault(clause.args[1], premises)
        return clauses

    fc_kb.clauses_with_premise = observed_lookup
    pl_fc_entails(fc_kb, Expr('SudokuCompletionProbe'))
    grid = _complete_grid(kb, known, n, box_h, box_w, givens)
    return {'grid': grid, 'steps': steps} if with_trace else grid


def solve_full_grid_fc(n, box_h, box_w, givens):
    """Solve using the supplied FC algorithm; return only a complete grid."""
    return _solve_fc(n, box_h, box_w, givens)


# ---------------------------------------------------------------------------
# 2.3 (c) Backward chaining
# ---------------------------------------------------------------------------

def bc_ask(query, facts, rules_by_conclusion, proved, why=None):
    """Member 2's DFS with retry rounds, using an explicit stack for deep proofs.

    Alternatives are OR branches; each rule's premises are an AND branch. Cycle
    cutoffs are local to one round. Retry after new proofs, because a grounded
    alternative can make a previously blocked cyclic branch succeed.
    """
    while True:
        failed, active = set(), set()
        proved_before = len(proved)
        # Frame: goal, alternative-rule index, next-premise index.
        stack = [[query, 0, 0]]
        while stack:
            q, rule_index, premise_index = stack[-1]
            if q in facts or q in proved:
                stack.pop()
                continue
            alternatives = rules_by_conclusion.get(q, ())
            if rule_index >= len(alternatives):
                active.discard(q)
                failed.add(q)
                stack.pop()
                continue
            active.add(q)
            premises = alternatives[rule_index]
            if premise_index == len(premises):
                active.remove(q)
                proved.add(q)
                if why is not None:
                    why.setdefault(q, premises)
                stack.pop()
                continue
            p = premises[premise_index]
            if p in facts or p in proved:
                proved.add(p)
                stack[-1][2] += 1
            elif p in failed or p in active:
                stack[-1][1] += 1
                stack[-1][2] = 0
            else:
                stack.append([p, 0, 0])
        if query in facts or query in proved:
            return True
        if len(proved) == proved_before:
            return False


def _run_bc(kb, query):
    """Shared plain/traced BC engine, with per-KB provenance and safe invalidation."""
    if not _is_atomic_proposition(query):
        raise ValueError('query must be an atomic propositional Expr.')
    facts, rules = build_bc_index(kb)
    signature = tuple(kb.clauses)
    state = getattr(kb, '_bc_state', None)
    if state is None or state['signature'] != signature:
        _check_sudoku_contradictions(kb, facts)
        state = {'signature': signature, 'proved': set(), 'why': {}, 'failed': set(), 'checked': 0}
        kb._bc_state = state
    proved, why = state['proved'], state['why']
    entailed = False if query in state['failed'] else bc_ask(query, facts, rules, proved, why)
    if len(proved) != state['checked']:
        _check_sudoku_contradictions(kb, facts | proved)
        state['checked'] = len(proved)
    if not entailed:
        # bc_ask exhausted every retry round, not merely one cyclic branch.
        state['failed'].add(query)
    return entailed, facts, why


def pl_bc_entails(kb, query):
    """Return a built-in Boolean without changing the KB's logical clauses."""
    return _run_bc(kb, query)[0]


# ---------------------------------------------------------------------------
# 2.3 (d) Backward chaining on the full grid
# ---------------------------------------------------------------------------

def _solve_bc(n, box_h, box_w, givens, with_trace=False):
    """Use the same BC engine and proof reuse for plain and traced solves."""
    kb = build_definite_kb(n, box_h, box_w, givens)
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            # Check all candidates so a second conflicting value is not hidden.
            for v in range(1, n + 1):
                pl_bc_entails(kb, atom('Is', r, c, v))
    facts, _ = build_bc_index(kb)
    state = kb._bc_state
    grid = _complete_grid(kb, facts | state['proved'], n, box_h, box_w, givens)
    if not with_trace:
        return grid
    # Original facts first, then every successful deduction in discovery order.
    # Unlike a single-query proof, retain deductions from unsuccessful searches.
    steps = [_proof_step(fact, (), kb) for fact in sorted(facts, key=str)]
    steps.extend(_proof_step(head, premises, kb) for head, premises in state['why'].items())
    return {'grid': grid, 'steps': steps}


def solve_full_grid_bc(n, box_h, box_w, givens):
    """Solve with the group's BC implementation; return only a complete grid."""
    return _solve_bc(n, box_h, box_w, givens)


# ---------------------------------------------------------------------------
# Part C.4 -- reasoning trace ("tutor mode") for the Streamlit app
# ---------------------------------------------------------------------------

def decode_atom(a):
    """Parse a Sudoku atom; generic Horn symbols are handled separately."""
    name = str(a)
    if name.startswith('Is'):
        prefix = 'Is'
    elif name.startswith('Not'):
        prefix = 'Not'
    else:
        raise ValueError('Not a Sudoku atom.')
    r, c, v = name[len(prefix):].split('_')
    return prefix, int(r), int(c), int(v)


def step_reason(conclusion, premises, kb):
    """Classify actual Sudoku rules; generic facts/rules use rule_application."""
    context = getattr(kb, '_sudoku_context', None)
    if context is None:
        return 'rule_application'
    n, box_h, box_w, givens = context
    try:
        prefix, r, c, v = decode_atom(conclusion)
        decoded = [decode_atom(p) for p in premises]
    except ValueError:
        return 'rule_application'
    if not premises:
        if prefix == 'Is' and givens.get((r, c)) == v:
            return 'given'
        if n == 1 and (prefix, r, c, v) == ('Is', 1, 1, 1):
            return 'last_candidate'
        return 'rule_application'
    if (prefix == 'Is' and len(premises) == n - 1
            and set(decoded) == {('Not', r, c, other) for other in range(1, n + 1) if other != v}):
        return 'last_candidate'
    if prefix == 'Not' and len(decoded) == 1:
        source_prefix, sr, sc, sv = decoded[0]
        if source_prefix == 'Is':
            if (sr, sc) == (r, c) and sv != v:
                return 'cell_elimination'
            if sv == v and (sr, sc) != (r, c):
                if sr == r:
                    return 'row_elimination'
                if sc == c:
                    return 'column_elimination'
                if (sr - 1) // box_h == (r - 1) // box_h and (sc - 1) // box_w == (c - 1) // box_w:
                    return 'box_elimination'
    return 'rule_application'


def _proof_step(conclusion, premises, kb):
    return {'conclusion': str(conclusion), 'premises': [str(p) for p in premises],
            'reason': step_reason(conclusion, premises, kb)}


def trace_steps(goals, facts, why, kb, emitted=None):
    """Flatten only supporting evidence, with premises before conclusions."""
    steps = []
    emitted = set() if emitted is None else emitted
    for goal in goals:
        stack = [(goal, False)]
        while stack:
            node, expanded = stack.pop()
            if node in emitted:
                continue
            premises = why.get(node, ())
            if not expanded and premises:
                stack.append((node, True))
                stack.extend((p, False) for p in reversed(premises) if p not in emitted)
                continue
            emitted.add(node)
            steps.append(_proof_step(node, premises, kb))
    return steps


def pl_bc_entails_with_trace(kb, query):
    """Return a fresh supporting proof, or an empty list for an unproved goal."""
    entailed, facts, why = _run_bc(kb, query)
    steps = trace_steps([query], facts, why, kb) if entailed else []
    return {'query': str(query), 'entailed': entailed, 'steps': steps}


def solve_full_grid_fc_with_trace(n, box_h, box_w, givens):
    """Return a complete grid and steps observed during the supplied FC run."""
    return _solve_fc(n, box_h, box_w, givens, with_trace=True)


def solve_full_grid_bc_with_trace(n, box_h, box_w, givens):
    """Return a complete grid and successful deductions from the same BC run."""
    return _solve_bc(n, box_h, box_w, givens, with_trace=True)
