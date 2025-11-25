# optimized_killer_solver.py
from itertools import combinations
from copy import deepcopy
import time

# -------------------------
# Utilidades
# -------------------------
def cell_to_coord(cell):
    col = ord(cell[0]) - ord("A")
    row = int(cell[1]) - 1
    return (row, col)

def coord_to_cell(rc):
    r, c = rc
    return f"{chr(c + ord('A'))}{r+1}"

# -------------------------
# Cambia aquí tu raw_json
# -------------------------
raw_json = [
    {"sum": 21, "cells": ["A1", "B1","C1","D1"]},
    {"sum": 37, "cells": ["E1", "F1","E2","F2","F3","G3"]},
    {"sum": 13, "cells": ["G1", "H1","I1"]},
    {"sum": 17, "cells": ["G2", "H2","I2"]},
    {"sum": 7, "cells": ["A2", "A3"]},
    {"sum": 11, "cells": ["B2", "B3"]},
    {"sum": 14, "cells": ["C2", "C3"]},
    {"sum": 8, "cells": ["D2", "D3","E3"]},
    {"sum": 10, "cells": ["H3", "H4","H5"]},
    {"sum": 7, "cells": ["I3", "I4"]},
    {"sum": 22, "cells": ["A4", "A5","B4","B5"]},
    {"sum": 8, "cells": ["C4", "D4"]},
    {"sum": 8, "cells": ["C5", "D5"]},
    {"sum": 13, "cells": ["E4", "F4"]},
    {"sum": 11, "cells": ["E5", "F5"]},
    {"sum": 9, "cells": ["G4", "G5"]},
    {"sum": 12, "cells": ["A6", "B6"]},
    {"sum": 6, "cells": ["C6","D6"]},
    {"sum": 10, "cells": ["E6","F6"]},
    {"sum": 14, "cells": ["G6","H6"]},
    {"sum": 18, "cells": ["I5","I6","I7"]},
    {"sum": 15, "cells": ["A7","B7","C7"]},
    {"sum": 23, "cells": ["D7","E7","D8","E8"]},
    {"sum": 13, "cells": ["F7","G7","H7"]},
    {"sum": 15, "cells": ["A8","B8"]},
    {"sum": 6, "cells": ["A9","B9"]},
    {"sum": 18, "cells": ["C8","C9","D9","E9"]},
    {"sum": 16, "cells": ["F8","G8","F9","G9"]},
    {"sum": 8, "cells": ["H8","H9"]},
    {"sum": 15, "cells": ["I8","I9"]},
]

# -------------------------
# Parseo jaulas y estructuras
# -------------------------
cages = []
cage_map = {}              # coord -> cage_obj
for c in raw_json:
    coords = [cell_to_coord(cell) for cell in c["cells"]]
    cage_obj = {"sum": c["sum"], "cells": coords}
    cages.append(cage_obj)
    for coord in coords:
        cage_map[coord] = cage_obj

# peers: para cada celda, las coordenadas que comparten fila/col/box
ALL_CELLS = [(r,c) for r in range(9) for c in range(9)]
def box_index(r,c): return (r//3, c//3)

PEERS = {}
for r,c in ALL_CELLS:
    peers = set()
    # fila y columna
    for i in range(9):
        if i != c: peers.add((r,i))
        if i != r: peers.add((i,c))
    # box
    br, bc = (r//3)*3, (c//3)*3
    for i in range(br, br+3):
        for j in range(bc, bc+3):
            if (i,j) != (r,c):
                peers.add((i,j))
    PEERS[(r,c)] = peers

# -------------------------
# Precomputar combinaciones válidas por jaula
# -------------------------
# Para cada jaula, calculamos todas las combinaciones de dígitos 1..9 sin repetición
# cuya longitud = tamaño de la jaula y suma = sum_j. Luego extraemos los dígitos posibles
# por celda (unión de los dígitos usados en esas combinaciones).
DIGITS = set(range(1,10))
cage_combos = {}   # cage_id -> list of tuples (combinations)
cage_allowed_digits = {}  # cage_id -> set(digits)

for idx, cage in enumerate(cages):
    k = len(cage["cells"])
    s = cage["sum"]
    combos = [comb for comb in combinations(range(1,10), k) if sum(comb) == s]
    # combos son combinaciones sin orden. Para asignaciones posicionales, se usarán como filtrado conjunto.
    cage_combos[idx] = combos
    # unión de dígitos que aparecen en alguna combinación
    allowed = set()
    for comb in combos:
        allowed.update(comb)
    cage_allowed_digits[idx] = allowed
    cage["id"] = idx  # anexa id para referencia fácil

# sanity check: si alguna jaula no tiene combos => puzzle inválido
for idx, combos in cage_combos.items():
    if not combos:
        raise ValueError(f"Cage {idx} sum={cages[idx]['sum']} size={len(cages[idx]['cells'])} has NO possible combos.")

# -------------------------
# Dominio inicial por celda
# -------------------------
# Dominio inicial = intersección entre:
# - dígitos posibles por jaula (unión combos)
# - 1..9
domains = {cell: set(DIGITS) for cell in ALL_CELLS}
for cage in cages:
    idx = cage["id"]
    allowed = cage_allowed_digits[idx]
    for coord in cage["cells"]:
        domains[coord] = domains[coord].intersection(allowed)

# -------------------------
# Propagación inicial sencilla:
# - si un dominio es singleton, eliminar valor de peers
# - repetir hasta estabilidad
# -------------------------
def propagate(dom):
    queue = [cell for cell in ALL_CELLS if len(dom[cell]) == 1]
    while queue:
        cell = queue.pop()
        valset = dom[cell]
        if not valset:
            return False
        val = next(iter(valset))
        for p in PEERS[cell]:
            if val in dom[p]:
                dom[p] = dom[p] - {val}
                if not dom[p]:
                    return False
                if len(dom[p]) == 1:
                    queue.append(p)
    return True

if not propagate(domains):
    raise ValueError("Inconsistent puzzle at initial propagation.")

# -------------------------
# Helper: aplicar filtrado de jaula más fino
# Para una jaula, eliminar cualquier dígito en el dominio de una celda
# que no aparece en ninguna combinación consistente con los dominios actuales.
# Esto hace que combinaciones imposibles (por dominios vecinos) se descarten.
# -------------------------
def prune_by_cage(dom):
    changed = True
    while changed:
        changed = False
        for cage in cages:
            idx = cage["id"]
            combos = cage_combos[idx]
            cells = cage["cells"]
            # Filtrar combos que son compatibles con los dominios actuales (cada número del combo
            # debe estar dentro del dominio de alguna celda, sin asignar posición estricta).
            valid_combos = []
            for comb in combos:
                # combinaciones sin orden: debemos poder asignar los k valores a las k celdas
                # sin violar dominios (esto es matching bipartito, pero una prueba rápida: verificar
                # si para cada valor existe al menos una celda whose domain contains it, y la multiconjunto es posible).
                comb_possible = True
                # quick check: for each value in comb, at least one cell contains it
                for v in comb:
                    if not any(v in dom[cell] for cell in cells):
                        comb_possible = False
                        break
                if comb_possible:
                    valid_combos.append(comb)
            if not valid_combos:
                return False  # jaula sin combos posibles -> inconsistencia
            # ahora para cada cell, los valores permitidos son la unión de todos valores que aparecen
            # en valid_combos y que también están en su dominio actual.
            allowed_by_combos = {cell: set() for cell in cells}
            for comb in valid_combos:
                for v in comb:
                    for cell in cells:
                        if v in dom[cell]:
                            allowed_by_combos[cell].add(v)
            # aplicar reducción
            for cell in cells:
                new_dom = dom[cell].intersection(allowed_by_combos[cell]) if allowed_by_combos[cell] else dom[cell]
                if new_dom != dom[cell]:
                    dom[cell] = new_dom
                    changed = True
                    if not dom[cell]:
                        return False
    return True

if not prune_by_cage(domains):
    raise ValueError("Inconsistency after cage pruning.")

# -------------------------
# MRV and LCV helpers
# -------------------------
def select_unassigned_variable(dom):
    # devuelve la celda con menor dominio >1
    unassigned = [(cell, dom[cell]) for cell in ALL_CELLS if len(dom[cell]) > 1]
    if not unassigned:
        return None
    # MRV
    unassigned.sort(key=lambda x: (len(x[1]), -len(PEERS[x[0]])))
    return unassigned[0][0]

def order_values(dom, var):
    # LCV: contar cuántos valores eliminaría en peers si ponemos v
    vals = list(dom[var])
    def impact(v):
        cnt = 0
        for p in PEERS[var]:
            if v in dom[p]:
                cnt += 1
        return cnt
    vals.sort(key=lambda v: impact(v))  # menor impacto primero
    return vals

# -------------------------
# Backtracking con forward checking
# -------------------------
def backtrack(dom):
    # si todo asignado (dominios de tamaño 1), terminamos
    if all(len(dom[cell]) == 1 for cell in ALL_CELLS):
        return dom

    var = select_unassigned_variable(dom)
    if var is None:
        return None

    for val in order_values(dom, var):
        # crear copia ligera de dominios
        new_dom = deepcopy(dom)
        new_dom[var] = {val}
        # propagar eliminación en peers
        consistent = True
        for p in PEERS[var]:
            if val in new_dom[p]:
                new_dom[p] = new_dom[p] - {val}
                if not new_dom[p]:
                    consistent = False
                    break
        if not consistent:
            continue
        # pruning por jaula y propagación singleton
        if not propagate(new_dom):
            continue
        if not prune_by_cage(new_dom):
            continue
        result = backtrack(new_dom)
        if result:
            return result
    return None

# -------------------------
# Ejecutar solver
# -------------------------
start = time.time()
solution = backtrack(domains)
end = time.time()

if solution:
    # convertir a grid
    grid = [[next(iter(solution[(r,c)])) for c in range(9)] for r in range(9)]
    print(f"Solved in {end-start:.3f}s")
    for row in grid:
        print(row)
else:
    print("No solution found (inconsistency or too hard).")
