# optimized_killer_solver_mask_logged.py
from time import time
from itertools import combinations
import json

VERBOSE = True
#Nombre del archivo para poner el verbose
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
def mask_for_digit(d):
    return 1 << (d-1)
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
    #Cell es la combinación de la columnda junto con su fila, A1 por ejemplo
    #ord() convierte las letras en su código ASCII, por ejemplo A = 65
    #La diferencia de estos es la columna
    #El número se le resta 1 para obtener la fila, entonces convierte A1 a (0,0)
    #Este ultimo valor se agrega coords como una lista de coordenadas [(0,0),(0,1)]
    col = ord(cell[0]) - ord("A")
    row = int(cell[1]) - 1
    return (row, col)

#Sencillamente devuelve la celda con sus coordenadas en letra+numero col, row
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

#Lee el json y lo asigna a raw_json
raw_json = read_json("puzzle.json")

# -------------------------
# Parse jaulas y estructuras
# -------------------------
cages = []
cage_map = {}
#raw_json es una lista de objetos y el for cicla en este
#enumerate obtiene de una vez el index y el objeto ciclado
#[1,2,3] idx=0 c=1, idx=1 c=2
for idx, c in enumerate(raw_json):
    #Lo que se hace en esta linea es recorrer las celdas de cada objeto por ejemplo
    #c :{'sum': 9, 'cells': ['A1', 'B1']}
    coords = [cell_to_coord(cell) for cell in c["cells"]]
    #cage_obj solo estandariza los objetos
    cage_obj = {"sum": c["sum"], "cells": coords, "id": idx}
    #Cages agrega todos esos objetos para ponerlos en una lista
    cages.append(cage_obj)
    for coord in coords:
        #cage_map serái el historial de valores para las celdas
        cage_map[coord] = cage_obj

#All_CELLS es una lista con las coordenadas de todos las celdas ejemplo [(0,0),(0,1)...]
ALL_CELLS = []
#Recorre las filas
for r in range(9):
    #Recorre las columnas
    for c in range(9):
        #Se agregan los valores a ALL_CELLS
        ALL_CELLS.append((r, c))

#PEERS es un diccionari que tiene como valor una celda (r,c) cuyos valores
#Son otras celdas que comparten la misma restricción, es decir que están en la misma fila
#En la misma columna y en el mismo subcuadro 3x3
PEERS = {}
for (r,c) in ALL_CELLS:
    peers = []
    #Complementando los comentarios anterior, aquí se agregan las filas y columnas
    for i in range(9):
        if (i != c): 
            peers.append((r,i))
        if (i != r):
            peers.append((i,c))
    #Aquí se agregan las celdas que comparten los subcuadros 3x3
    br, bc = (r//3)*3, (c//3)*3
    for i in range(br, br+3):
        for j in range(bc, bc+3):
            if (i,j) != (r,c) and (i,j) not in peers:
                peers.append((i,j))
    PEERS[(r,c)] = peers
# -------------------------
# Precompute valid combos per cage as masks (combinaciones sin repetición)
# -------------------------
#Solo genera una lista tal que [1,2,4,8,16,32,64,128,256]
DIGIT_MASKS = [mask_for_digit(d) for d in range(1,10)]
#All mask es la suma de todos los digitos de lal ista DIGIT_MASKS
ALL_MASK = sum(DIGIT_MASKS)

#Recordar que un cage en un killer sudoku son los valores de un bloque de celdas
#Con una suma que cumplir, por ejempo sum:15, [A1,A2,A3] la suma de A1,A2,Z3
#Debe dar 15

cage_combos_masks = {}
#Recordar que cages fue una variable que se inicializó hace unas líneas de código
#atrás y era la lista de valores con su determinada suma
for cage in cages:
    #k es la cantidad de coordenadas que hay en una lista, ejemplo [(0,1),(0,2)]
    #k = 2
    k = len(cage["cells"])
    #s es la suma
    s = cage["sum"]
    combos = []
    #combinations lo que hace es tomar todas las posibles combinaciones de k cantidad
    #de valores, si k=2, entonce son todas las combinaciones sin repetir de
    #dos números
    for comb in combinations(range(1,10), k):
        #Si alguna de esas combinaciones es igual a la suma entonces entra al if
        if sum(comb) == s:
            mask = 0
            for v in comb: 
                #mask_for_digit convierte los números en binario
                mask |= mask_for_digit(v)
            #La lista combos es una lista de los números binarios
            combos.append(mask)
    if not combos:
        raise ValueError(f"Cage {cage['id']} has no combos")
    #cage_combos_masks es un diccionario de valores que empieza desde id:0 con valores
    #correspondientes a una lista binaria de números cuya suma es igual a lo que pide la
    #restricción
    cage_combos_masks[cage['id']] = combos

# -------------------------
# Initial domains: all digits allowed but intersect with cage allowed digits
# -------------------------

#Recordar que ALL_MASK es la cantidad totoal de digitos en binario, 511 en este caso
#ALL_CELLS son todas las coordenadas de celdas que hay en el sudoku
domains = {cell: ALL_MASK for cell in ALL_CELLS}
for cage in cages:
    allowed = 0
    #Construye una mascara con todos los valores permitidos
    for m in cage_combos_masks[cage["id"]]:
        allowed |= m
    for coord in cage["cells"]:
        domains[coord] &= allowed
#Crea un diccionario con cada celda como id y su valor en binario
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


#Aquí se usa la heurística MRV (Minimum Remaining Values)
def select_unassigned_variable(dom):
    best = None
    best_count = 10
    #Toma todas las celdas e itera en ella
    for cell in ALL_CELLS:
        c = count_bits(dom[cell])
        #En un Sudoku normal (9x9),cada bit representa un dígito del 1 al 9, si se pasa de 10 algo falla
        if 1 < c < best_count:
                #Se asigna best_count para y best para saber cuál es la celda con menos opciones
            best_count = c
            best = cell
            #Si encuentra una celda igual a 2 ya es el mejor caso posible, sería 1 pero este ya está resueta
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
    #Recordar que ALL_CELLS son todas las celdas del sudoku
    #cell es cada celda
    #dom es un diccionario con celda y los valores en binario
    for cell in ALL_CELLS:
        #Entra al valor correspondiente a la celda
        #Basicamente cuenta cuantos bits tiene una celda
        #Si es difente de 1 es porque la celda NO tiene exactamente un valor posible
        if count_bits(dom[cell]) != 1:
            solved = False
            break
    #Entra al if cuando solved es true, es decir cuando el sudoku está hecho
    if solved:
        if VERBOSE: log("Sudoku completo.")
        return True
    #var es la celda con el dominio más pequeño
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
#Se hace una copia del dominio para que no haya conflicto
dom_copy = domains.copy()
#Ahora sí empiza el backtracking
solved = backtrack(dom_copy)
end = time()

if solved:
    grid = [[lowest_bit_value(dom_copy[(r,c)]) for c in range(9)] for r in range(9)]
    print(f"Solved in {end-start:.4f}s")
    for row in grid:
        print(row)
else:
    print("No solution found.")
