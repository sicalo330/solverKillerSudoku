# optimized_killer_solver_mask_logged.py
from time import time
from itertools import combinations
import json

# -------------------------
# Config logging / verbose
# -------------------------
VERBOSE = True
log_file = "killer_solver.txt"

def log(msg):
    if not VERBOSE:
        return
    with open(log_file, "a", encoding="utf8") as f:
        f.write(msg + "\n")

if VERBOSE:
    open(log_file, "w").close()
    log("=== Killer Sudoku Solver Started ===")

# -------------------------
# Utilidades de bitmask
# -------------------------
def mask_for_digit(d): return 1 << (d-1)
def digits_from_mask(m):
    d = []
    i = 1
    while m:
        if m & 1:
            d.append(i)
        m >>= 1
        i += 1
    return d

def count_bits(m):
    return m.bit_count()

def lowest_bit_value(m):
    if m == 0: return None
    lsb = (m & -m)
    return (lsb.bit_length())  # devuelve posición (1..9)

# -------------------------
# Conversión celda <-> coord
# -------------------------
def cell_to_coord(cell):
    col = ord(cell[0]) - ord("A")
    row = int(cell[1]) - 1
    return (row, col)

def coord_to_cell(rc):
    r, c = rc
    return f"{chr(c + ord('A'))}{r+1}"

# -------------------------
# Leer puzzle desde JSON
# -------------------------
def read_json(file):
    with open(file,"r", encoding="utf8") as f:
        data = json.load(f)
    return data

raw_json = read_json("puzzle.json")

# -------------------------
# Parse jaulas y estructuras
# -------------------------
cages = []
cage_map = {}
for idx, c in enumerate(raw_json):
    coords = [cell_to_coord(cell) for cell in c["cells"]]
    cage_obj = {"sum": c["sum"], "cells": coords, "id": idx}
    cages.append(cage_obj)
    for coord in coords:
        cage_map[coord] = cage_obj

ALL_CELLS = [(r,c) for r in range(9) for c in range(9)]
# peers as lists for faster iteration
PEERS = {}
for r,c in ALL_CELLS:
    peers = []
    for i in range(9):
        if i != c: peers.append((r,i))
        if i != r: peers.append((i,c))
    br, bc = (r//3)*3, (c//3)*3
    for i in range(br, br+3):
        for j in range(bc, bc+3):
            if (i,j) != (r,c) and (i,j) not in peers:
                peers.append((i,j))
    PEERS[(r,c)] = peers

# -------------------------
# Precompute valid combos per cage as masks (combinaciones sin repetición)
# -------------------------
DIGIT_MASKS = [mask_for_digit(d) for d in range(1,10)]
ALL_MASK = sum(DIGIT_MASKS)

cage_combos_masks = {}
for cage in cages:
    k = len(cage["cells"])
    s = cage["sum"]
    combos = []
    for comb in combinations(range(1,10), k):
        if sum(comb) == s:
            mask = 0
            for v in comb: mask |= mask_for_digit(v)
            combos.append(mask)
    if not combos:
        raise ValueError(f"Cage {cage['id']} has no combos")
    cage_combos_masks[cage['id']] = combos

# -------------------------
# Initial domains: all digits allowed but intersect with cage allowed digits
# -------------------------
domains = {cell: ALL_MASK for cell in ALL_CELLS}
for cage in cages:
    allowed = 0
    for m in cage_combos_masks[cage["id"]]:
        allowed |= m
    for coord in cage["cells"]:
        domains[coord] &= allowed

# -------------------------
# Fast propagation with undo stack (logged versions)
# -------------------------
def eliminate(dom, coord, valmask, changes):
    cur = dom[coord]
    if cur & valmask:
        new = cur & ~valmask
        if new == cur:
            return True

        if VERBOSE:
            log(f"[ELIMINATE] {coord_to_cell(coord)} remove {digits_from_mask(valmask)} "
                f"=> {digits_from_mask(new)}")

        changes.append((coord, cur))
        dom[coord] = new

        if new == 0:
            if VERBOSE: log(f"[FAIL] Domain of {coord_to_cell(coord)} became EMPTY")
            return False

        if count_bits(new) == 1:
            singleton = new
            if VERBOSE: log(f"[UNIT] {coord_to_cell(coord)} is now {digits_from_mask(singleton)}")
            for p in PEERS[coord]:
                if not eliminate(dom, p, singleton, changes):
                    return False

    return True

def assign(dom, coord, valmask, changes):
    cur = dom[coord]
    if cur == valmask:
        return True

    if VERBOSE:
        log(f"[ASSIGN] {coord_to_cell(coord)} = {digits_from_mask(valmask)}")

    changes.append((coord, cur))
    dom[coord] = valmask

    if count_bits(valmask) == 0:
        return False

    for p in PEERS[coord]:
        if not eliminate(dom, p, valmask, changes):
            return False

    return True

def prune_by_cage(dom, changes):
    if VERBOSE: log("[CAGE] Starting cage pruning")

    for cage in cages:
        cells = cage["cells"]
        combos = cage_combos_masks[cage["id"]]

        valid = []
        union_mask = 0
        for cell in cells:
            union_mask |= dom[cell]

        # Filtrar combos válidos
        for cm in combos:
            if (cm & ~union_mask) != 0:
                continue
            ok = True
            b = cm
            while b:
                lsb = (b & -b)
                b -= lsb
                if not any(dom[cell] & lsb for cell in cells):
                    ok = False
                    break
            if ok:
                valid.append(cm)

        if not valid:
            if VERBOSE: log(f"[CAGE FAIL] Cage {cage['id']} has no valid combos")
            return False

        # allowed_per_cell por restricción de combinaciones
        allowed = {cell: 0 for cell in cells}

        for cm in valid:
            b = cm
            while b:
                lsb = (b & -b)
                b -= lsb
                for cell in cells:
                    if dom[cell] & lsb:
                        allowed[cell] |= lsb

        # Reducir dominios
        for cell in cells:
            new = dom[cell] & allowed[cell]
            if new != dom[cell]:
                if VERBOSE:
                    log(f"[CAGE REDUCE] {coord_to_cell(cell)} "
                        f"{digits_from_mask(dom[cell])} → {digits_from_mask(new)}")

                changes.append((cell, dom[cell]))
                dom[cell] = new

                if new == 0:
                    if VERBOSE: log(f"[FAIL] Domain of {coord_to_cell(cell)} became EMPTY")
                    return False

                if count_bits(new) == 1:
                    singleton = new
                    for p in PEERS[cell]:
                        if not eliminate(dom, p, singleton, changes):
                            return False

    return True

def initial_propagate(dom):
    changes = []
    # Propagate singletons
    for cell in ALL_CELLS:
        if count_bits(dom[cell]) == 1:
            valmask = dom[cell]
            for p in PEERS[cell]:
                if not eliminate(dom, p, valmask, changes):
                    for c,prev in reversed(changes):
                        dom[c] = prev
                    return False
    # Prune by cage
    if not prune_by_cage(dom, changes):
        for c,prev in reversed(changes):
            dom[c] = prev
        return False
    return True

if not initial_propagate(domains):
    raise ValueError("Inconsistency at initial propagation")

# -------------------------
# Heuristics: MRV & LCV using masks
# -------------------------
def select_unassigned_variable(dom):
    best = None
    best_count = 10
    for cell in ALL_CELLS:
        c = count_bits(dom[cell])
        if 1 < c < best_count:
            best_count = c
            best = cell
            if best_count == 2: break
    if VERBOSE and best is not None:
        log(f"[SELECT] {coord_to_cell(best)} with {count_bits(dom[best])} options: {digits_from_mask(dom[best])}")
    return best

def order_values(dom, var):
    vals = digits_from_mask(dom[var])
    impacts = []
    for v in vals:
        vm = mask_for_digit(v)
        cnt = 0
        for p in PEERS[var]:
            if dom[p] & vm:
                cnt += 1
        impacts.append((cnt, v))
    impacts.sort()
    ordered = [v for _,v in impacts]
    if VERBOSE:
        log(f"[ORDER] {coord_to_cell(var)} order {ordered}")
    return ordered

# -------------------------
# Backtracking with undo stack
# -------------------------
def backtrack(dom, depth=0):
    # check if solved
    solved = True
    for cell in ALL_CELLS:
        if count_bits(dom[cell]) != 1:
            solved = False
            break
    if solved:
        if VERBOSE: log("[SOLVED] Puzzle complete.")
        return True

    var = select_unassigned_variable(dom)
    if var is None:
        return False

    if VERBOSE:
        log(f"{'  '*depth}[BRANCH] Try variable {coord_to_cell(var)} with domain {digits_from_mask(dom[var])}")

    for v in order_values(dom, var):
        vm = mask_for_digit(v)
        changes = []
        if VERBOSE:
            log(f"{'  '*depth}[TRY] {coord_to_cell(var)} = {v}")
        if not assign(dom, var, vm, changes):
            if VERBOSE: log(f"{'  '*depth}[FAIL-ASSIGN] {coord_to_cell(var)} = {v}")
            for c,prev in reversed(changes):
                dom[c] = prev
            continue
        if not prune_by_cage(dom, changes):
            if VERBOSE: log(f"{'  '*depth}[FAIL-PRUNE] after assigning {coord_to_cell(var)} = {v}")
            for c,prev in reversed(changes):
                dom[c] = prev
            continue
        if backtrack(dom, depth+1):
            return True
        # undo
        if VERBOSE: log(f"{'  '*depth}[BACKTRACK] undo {coord_to_cell(var)} = {v}")
        for c,prev in reversed(changes):
            dom[c] = prev
    return False

# -------------------------
# Ejecutar y medir tiempo
# -------------------------
start = time()
dom_copy = domains.copy()
solved = backtrack(dom_copy)
end = time()

if solved:
    grid = [[lowest_bit_value(dom_copy[(r,c)]) for c in range(9)] for r in range(9)]
    print(f"Solved in {end-start:.4f}s")
    for row in grid:
        print(row)
else:
    print("No solution found.")
