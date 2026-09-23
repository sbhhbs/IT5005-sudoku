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
    kb = PropDefiniteKB()

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
                rule = Expr('==>', antecedent, atom('Is', r, c, v))
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
        premises, conclusion = parse_definite_clause(clause)
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
    return _index_memo(tuple(kb.clauses))


# ---------------------------------------------------------------------------
# 2.3 (b) Forward chaining on the full grid
# ---------------------------------------------------------------------------

def build_fc_index(kb):
    """Return a copy of kb whose clauses_with_premise lookup is precomputed.
    Example input KB:
    kb.clauses = [
        Is1_1_3,
        Is1_1_3 ==> Not1_1_4,
        Is1_1_3 ==> Not1_2_3,
    ]

    Example output KB (indexed_kb):
    indexed_kb.clauses = [             # Same clauses, in a new list
        Is1_1_3,
        Is1_1_3 ==> Not1_1_4,
        Is1_1_3 ==> Not1_2_3,
    ]
    indexed_kb.clauses_with_premise(Is1_1_3) returns:
        [Is1_1_3 ==> Not1_1_4, Is1_1_3 ==> Not1_2_3]

    The output KB has the same facts and rules, but looks up rules by premise
    using a precomputed index instead of scanning every clause.
    """
    

    indexed_kb = PropDefiniteKB()
    indexed_kb.clauses = list(kb.clauses)

    premise_index = {}
    for clause in indexed_kb.clauses:
        if clause.op == '==>':
            for p in conjuncts(clause.args[0]):
                premise_index.setdefault(p, []).append(clause)

    indexed_kb.clauses_with_premise = lambda p: premise_index.get(p, [])
    return indexed_kb


def solve_full_grid_fc(n, box_h, box_w, givens):
    """Solve the whole puzzle using build_definite_kb + pl_fc_entails.

    Returns
    -------
    dict[(int, int), int] -- {(row, col): value} for every cell
    """
    kb = build_definite_kb(n, box_h, box_w, givens)
    fc_kb = build_fc_index(kb)

    solution = {}
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v in range(1, n + 1):
                if pl_fc_entails(fc_kb, atom('Is', r, c, v)):
                    solution[(r, c)] = v
                    break
            else:
                raise ValueError(f'No value could be established for cell ({r}, {c}).')
    return solution


# ---------------------------------------------------------------------------
# 2.3 (c) Backward chaining
# ---------------------------------------------------------------------------

def bc_ask(query, facts, rules_by_conclusion, proved, why=None):

    while True: # repeat until query is proved or more tries are useless
        failed = set()                              # goals that could not be proved in this round (1 bc(query) search (Whole DFS))
        active = set()                              # goals on the current DFS path that have not yet been proved
        proved_before = len(proved)

        def bc(q):
            if q in facts or q in proved:            # q matches a fact or in proved
                return True
            if q in failed:                          # already failed this round
                return False
            if q in active:                          # cycle detected; stop this branch
                return False
            if q not in rules_by_conclusion:         # no clause concludes q
                failed.add(q)
                return False

            active.add(q)
            for premise in rules_by_conclusion[q]:   # for each clause concluding q
                count = len(premise)                 # count = number of symbols in premise
                for p in premise:
                    if bc(p):
                        proved.add(p)                # record p as proved
                        count -= 1
                    else:
                        break
                if count == 0:                       # every premise proved
                    active.discard(q)
                    proved.add(q)
                    if why is not None and q not in why:
                        why[q] = premise
                    return True
            active.discard(q)
            failed.add(q)
            return False

        if bc(query):
            return True
        if len(proved) == proved_before:             # fixpoint: query not entailed
            return False

def pl_bc_entails(kb, query):
    """Return True iff the PropDefiniteKB `kb` entails the atomic Expr `query`."""

    if not isinstance(kb, PropDefiniteKB):
        raise ValueError('kb must be a PropDefiniteKB.')
    if not isinstance(query, Expr) or query.args:
        raise ValueError('query must be an atomic Expr.')

    facts, rules_by_conclusion = build_bc_index(kb)
    return bc_ask(query, facts, rules_by_conclusion, proved=set())


# ---------------------------------------------------------------------------
# 2.3 (d) Backward chaining on the full grid
# ---------------------------------------------------------------------------

def solve_full_grid_bc(n, box_h, box_w, givens):
    """Solve the whole puzzle with build_definite_kb + our own backward chaining.

    Returns
    -------
    dict[(int, int), int] -- {(row, col): value} for every cell
    """
    kb = build_definite_kb(n, box_h, box_w, givens)

    solution = {}
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v in range(1, n + 1):
                if pl_bc_entails(kb, atom('Is', r, c, v)):
                    solution[(r, c)] = v
                    break
            else:
                raise ValueError(f'No value could be established for cell ({r}, {c}).')
    return solution


# ---------------------------------------------------------------------------
# Part C.4 -- reasoning trace ("tutor mode") for the Streamlit app
# ---------------------------------------------------------------------------

def decode_atom(a):
    """'Is3_2_4' -> ('Is', 3, 2, 4). Only utils/logic_ are imported, so parse by hand."""
    name = str(a)
    prefix = 'Is' if name.startswith('Is') else 'Not'
    r, c, v = name[len(prefix):].split('_')
    return prefix, int(r), int(c), int(v)


def step_reason(conclusion, premises, n):
    """Name the Sudoku rule that licensed this step, for human-readable output."""
    if not premises:
        return 'given'
    prefix, r, c, v = decode_atom(conclusion)
    if prefix == 'Is' and len(premises) == n - 1:
        return 'last_candidate'
    if prefix == 'Not' and len(premises) == 1:
        source_prefix, sr, sc, sv = decode_atom(premises[0])
        if source_prefix == 'Is':
            if (sr, sc) == (r, c):
                return 'cell_elimination'
            if sr == r:
                return 'row_elimination'
            if sc == c:
                return 'column_elimination'
            return 'box_elimination'
    return 'rule_application'


def trace_steps(goals, facts, why, n, emitted=None):
    """Flatten the recorded proof DAG into steps ordered premises-before-conclusion.
    {
        'conclusion': 'Not1_2_3',
        'premises': ['Is1_1_3'],
        'reason': 'row_elimination',
    }
    """
    steps = []
    emitted = set() if emitted is None else emitted

    for goal in goals:
        # Iterative post-order walk, so deep proofs cannot hit the recursion limit.
        stack = [(goal, False)]
        while stack:
            node, expanded = stack.pop()
            if node in emitted:
                continue
            premises = why.get(node, ())
            if not expanded and premises:
                stack.append((node, True))
                for p in reversed(premises):
                    if p not in emitted:
                        stack.append((p, False))
                continue
            if node in emitted:
                continue
            emitted.add(node)
            steps.append({'conclusion': str(node),
                          'premises': [str(p) for p in premises],
                          'reason': step_reason(node, premises, n)})
    return steps


def pl_bc_entails_with_trace(kb, query):
    """Optional helper used by the app's tutor view.

    Returns {'query': str, 'entailed': bool, 'steps': [...]}, where each step is
    {'conclusion', 'premises', 'reason'} and every premise appears as the
    conclusion of an earlier step. An unproved query returns no steps.
    """
    if not isinstance(kb, PropDefiniteKB):
        raise ValueError('kb must be a PropDefiniteKB.')
    if not isinstance(query, Expr) or query.args:
        raise ValueError('query must be an atomic Expr.')

    facts, rules_by_conclusion = build_bc_index(kb)
    n = max(decode_atom(a)[3] for a in rules_by_conclusion) if rules_by_conclusion else 0
    why = {}
    entailed = bc_ask(query, facts, rules_by_conclusion, set(), why)
    steps = trace_steps([query], facts, why, n) if entailed else []
    return {'query': str(query), 'entailed': entailed, 'steps': steps}


def solve_full_grid_bc_with_trace(n, box_h, box_w, givens):
    """Optional helper: solve the grid and return the deductions actually used."""
    kb = build_definite_kb(n, box_h, box_w, givens)
    facts, rules_by_conclusion = build_bc_index(kb)

    grid, why, proved, emitted, steps = {}, {}, set(), set(), []
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v in range(1, n + 1):
                goal = atom('Is', r, c, v)
                if bc_ask(goal, facts, rules_by_conclusion, proved, why):
                    grid[(r, c)] = v
                    steps.extend(trace_steps([goal], facts, why, n, emitted))
                    break
            else:
                raise ValueError(f'No value could be established for cell ({r}, {c}).')
    return {'grid': grid, 'steps': steps}