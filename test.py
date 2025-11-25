# optimized_killer_solver_mask.py
from time import time
from itertools import combinations
import json

# -------------------------
# Utilidades de bitmask
# -------------------------
def mask_for_digit(d): return 1 << (d-1)
def digits_from_mask(m):
    d = []
    bit = 1
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
# Pegar aquí tu raw_json (misma estructura que antes)
# -------------------------


# raw_json = [
#   {
#     "sum": 3,
#     "cells": ["A1","A2"]
#   },
#   {
#     "sum": 24,
#     "cells": ["B1", "C1", "B2"]
#   },
#   {
#     "sum": 20,
#     "cells": ["D1", "E1","E2"]
#   },
#   {
#     "sum": 12,
#     "cells": ["F1", "F2", "F3"]
#   },
#   {
#     "sum": 14,
#     "cells": ["G1", "H1","I1"]
#   },
#   {
#     "sum": 13,
#     "cells": ["G2", "H2","H3"]
#   },
#   {
#     "sum": 6,
#     "cells": ["C2","D2"]
#   },
#   {
#     "sum": 9,
#     "cells": ["I2","I3"]
#   },
#   {
#     "sum": 14,
#     "cells": ["A3", "B3","B4"]
#   },
#   {
#     "sum": 13,
#     "cells": ["C3", "C4","D3"]
#   },
#   {
#     "sum": 12,
#     "cells": ["E3", "E4","D4"]
#   },
#   {
#     "sum": 11,
#     "cells": ["G3", "G4"]
#   },
#   {
#     "sum": 14,
#     "cells": ["A4", "A5","B5"]
#   },
#   {
#     "sum": 23,
#     "cells": ["F4", "F5", "F6", "E6"]
#   },
#   {
#     "sum": 16,
#     "cells": ["H4", "H5","G5"]
#   },
#   {
#     "sum": 28,
#     "cells": ["I4", "I5","I6","H6","H7","I7"]
#   },
#   {
#     "sum": 11,
#     "cells": ["C5", "C6","D6"]
#   },
#   {
#     "sum": 14,
#     "cells": ["D5","E5"]
#   },
#   {
#     "sum": 14,
#     "cells": ["A6", "B6"]
#   },
#   {
#     "sum": 25,
#     "cells": ["G6","G7","F7","E7","E8"]
#   },
#   {
#     "sum": 11,
#     "cells": ["A7", "B7","B8"]
#   },
#   {
#     "sum": 12,
#     "cells": ["C7","D7"]
#   },
#   {
#     "sum": 13,
#     "cells": ["C8", "C9","B9"]
#   },
#   {
#     "sum": 14,
#     "cells": ["D8","D9"]
#   },
#   {
#     "sum": 16,
#     "cells": ["A8", "A9"]
#   },
#   {
#     "sum": 11,
#     "cells": ["F8", "G8"]
#   },
#   {
#     "sum": 13,
#     "cells": ["H8","I8"]
#   },
#   {
#     "sum": 13,
#     "cells": ["G9", "H9","I9"]
#   },
#   {
#     "sum": 6,
#     "cells": ["E9", "F9"]
#   }
# ]
# -------------------------
# Parse jaulas y estructuras
# -------------------------
def read_json():
    with open("puzzle.json","r") as f:
        data = json.load(f)
    return data
raw_json = read_json()
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
# Fast propagation with undo stack
# -------------------------
def eliminate(dom, coord, valmask, changes):
    cur = dom[coord]
    if cur & valmask:
        new = cur & ~valmask
        if new == cur:
            return True
        changes.append((coord, cur))
        dom[coord] = new
        if new == 0:
            return False
        if count_bits(new) == 1:
            singleton_mask = new
            for p in PEERS[coord]:
                if not eliminate(dom, p, singleton_mask, changes):
                    return False
    return True

def assign(dom, coord, valmask, changes):
    cur = dom[coord]
    if cur == valmask:
        return True
    changes.append((coord, cur))
    dom[coord] = valmask
    if count_bits(valmask) == 0:
        return False
    for p in PEERS[coord]:
        if not eliminate(dom, p, valmask, changes):
            return False
    return True

def prune_by_cage(dom, changes):
    for cage in cages:
        cells = cage["cells"]
        combos = cage_combos_masks[cage["id"]]
        valid = []
        union_mask = 0
        for cell in cells:
            union_mask |= dom[cell]
        for cm in combos:
            if (cm & ~union_mask) != 0:
                continue
            ok = True
            b = cm
            while b:
                lsb = (b & -b)
                b -= lsb
                found = False
                for cell in cells:
                    if dom[cell] & lsb:
                        found = True; break
                if not found:
                    ok = False; break
            if ok:
                valid.append(cm)
        if not valid:
            return False
        allowed_per_cell = {cell:0 for cell in cells}
        for cm in valid:
            b = cm
            while b:
                lsb = (b & -b)
                b -= lsb
                for cell in cells:
                    if dom[cell] & lsb:
                        allowed_per_cell[cell] |= lsb
        for cell in cells:
            newmask = dom[cell] & allowed_per_cell[cell] if allowed_per_cell[cell] else dom[cell]
            if newmask != dom[cell]:
                changes.append((cell, dom[cell]))
                dom[cell] = newmask
                if newmask == 0:
                    return False
                if count_bits(newmask) == 1:
                    singleton = newmask
                    for p in PEERS[cell]:
                        if not eliminate(dom, p, singleton, changes):
                            return False
    return True

def initial_propagate(dom):
    changes = []
    for cell in ALL_CELLS:
        if count_bits(dom[cell]) == 1:
            valmask = dom[cell]
            for p in PEERS[cell]:
                if not eliminate(dom, p, valmask, changes):
                    for c,prev in reversed(changes):
                        dom[c] = prev
                    return False
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
    return [v for _,v in impacts]

# -------------------------
# Backtracking with undo stack
# -------------------------
def backtrack(dom):
    solved = True
    for cell in ALL_CELLS:
        if count_bits(dom[cell]) != 1:
            solved = False
            break
    if solved:
        return True
    var = select_unassigned_variable(dom)
    if var is None:
        return False
    for v in order_values(dom, var):
        vm = mask_for_digit(v)
        changes = []
        if not assign(dom, var, vm, changes):
            for c,prev in reversed(changes):
                dom[c] = prev
            continue
        if not prune_by_cage(dom, changes):
            for c,prev in reversed(changes):
                dom[c] = prev
            continue
        if backtrack(dom):
            return True
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
