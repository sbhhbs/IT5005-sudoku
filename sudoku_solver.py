"""IT5005 Assignment 1: student implementation file.

Implement the functions marked below. Do not modify utils.py or logic_.py.
"""

from utils import *
from logic_ import *


# Do not change this function; it is used to create atomic propositions.
def atom(prefix, r, c, v):
    """prefix is 'Is' or 'Not'. Returns the Expr for e.g. Is3_2_4."""
    return expr(f'{prefix}{r}_{c}_{v}')


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
    raise NotImplementedError(
        'build_definite_kb: encode the puzzle as definite clauses'
    )


def solve_full_grid_fc(n, box_h, box_w, givens):
    """Solve the whole puzzle using build_definite_kb + pl_fc_entails.

    Returns
    -------
    dict[(int, int), int] -- {(row, col): value} for every cell
    """
    raise NotImplementedError(
        'solve_full_grid_fc: solve every cell with forward chaining'
    )


def pl_bc_entails(kb, query):
    """Your own backward-chaining implementation.

    Parameters
    ----------
    kb : PropDefiniteKB
    query : Expr

    Returns
    -------
    bool
    """
    raise NotImplementedError(
        'pl_bc_entails: implement backward chaining, soundly'
    )


def solve_full_grid_bc(n, box_h, box_w, givens):
    """Solve the whole puzzle using build_definite_kb + your own pl_bc_entails.

    For each cell, try each candidate value until pl_bc_entails confirms one
    -- the same per-cell strategy as solve_full_grid_fc, but backed by
    backward chaining instead of a single shared forward-chaining pass.

    Returns
    -------
    dict[(int, int), int] -- {(row, col): value} for every cell
    """
    raise NotImplementedError(
        'solve_full_grid_bc: solve every cell with backward chaining'
    )
