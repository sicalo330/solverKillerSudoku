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

#Esta función convierte el valor del dominio en bits
def mask_for_digit(d):
    return 1 << (d-1)

#Esta función toma el bit del dominio de la celda correspondiente y lo convierte a la lista de dominios simple
#Es decir toma el bit del dominio y lo convierte en digito
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

def read_json(file):
    with open(file,"r", encoding="utf8") as f:
        data = json.load(f)
    return data

#Lee el json y lo asigna a raw_json
raw_json = read_json("puzzle.json")

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

#Recordar que ALL_MASK es la cantidad totoal de digitos en binario, 511 en este caso
#ALL_CELLS son todas las coordenadas de celdas que hay en el sudoku
domains = {cell: ALL_MASK for cell in ALL_CELLS}
for cage in cages:
    allowed = 0
    #Construye una mascara con todos los valores permitidos
    for m in cage_combos_masks[cage["id"]]:
        allowed |= m
    for coord in cage["cells"]:
        #Crea un diccionario con cada celda como id y su valor en binario
        domains[coord] &= allowed


def eliminate(dom, coord, valmask, changes):
    #Obtiene el dominio actual
    cur = dom[coord]
    #Se pregunta si el dominio contiene el valor que se quiere eliminar
    if cur & valmask:
        #~valmask es el valor de los bits excepto el que se quiere eliminar, es decir elimina cur
        new = cur & ~valmask
        #Si el dominio es el mismo que se quiere eliminar retorna true(Recordar que es if not eliminate())
        # es decir que entra si retorna true, no se debe registrar el cambio
        if new == cur:
            return True

        #En el caso de que lo que se quiera eliminar está en el dominio
        if VERBOSE:
            log(f"[ELIMINATE] {coord_to_cell(coord)} remove {digits_from_mask(valmask)} "
                f"=> {digits_from_mask(new)}")
        #Se registra el cambio, necesario si el backtracking falla
        changes.append((coord, cur))
        #Se realiza definitamente el cambio del dominio
        dom[coord] = new

        #Si entra al if, significa que la celda no tiene ningun valor valido, es decir una contradicción lógica
        if new == 0:
            if VERBOSE: log(f"[FAIL] Domain of {coord_to_cell(coord)} became EMPTY")
            return False


        #Se cuentan los bits, y si da 1, significa que solo un valor es posible de agregar
        if count_bits(new) == 1:
            singleton = new
            if VERBOSE: log(f"[UNIT] {coord_to_cell(coord)} is now {digits_from_mask(singleton)}")
            for p in PEERS[coord]:
                #Hace recursividad si encuentra alguna contradicción
                #Por ejemplo, una celda quiere poner 3, entonces busca si es posible eliminar el 3 de las celdas vecinas
                #Si uno de los vecino se queda sin opciones  retorna false.
                if not eliminate(dom, p, singleton, changes):
                    return False
    return True

def assign(dom, coord, valmask, changes):
    #Obtiene el dominio de la celda
    cur = dom[coord]
    #Revisa si ya se asignó el valor, de ser así, no haya nada que hacer
    if cur == valmask:
        return True
    if VERBOSE:
        log(f"[ASSIGN] {coord_to_cell(coord)} = {digits_from_mask(valmask)}")

    #changes es una lista que guarda ese valor como una forma de historial o pista de cambios
    changes.append((coord, cur))
    #Asigna el nuevo valro
    dom[coord] = valmask
    #SI la cantidad de bits es 0, es decir no hay valor que agregar entonces se retorna false
    if count_bits(valmask) == 0:
        return False
    
    for p in PEERS[coord]:
        #Si se va a usar el valor, se elimina del dominio para que ningún vecino lo pueda usar
        if not eliminate(dom, p, valmask, changes):
            return False
    #Si retorna true es porque un valor del dominio sí se puede poner sin que las restricciones se contradigan
    return True

#Aplica la restricción de la suma de las celdas
def prune_by_cage(dom, changes):
    if VERBOSE: log("[CAGE] Starting cage pruning")

    #Recordar que cages es la suma de las celdas del kiler sudoku
    for cage in cages:
        cells = cage["cells"]
        #Recordar que combos es la combinación de digitos que pueden estar en la celda
        combos = cage_combos_masks[cage["id"]]

        valid = []
        union_mask = 0
        """
        Hace una unión con los dominios de las celdas, por ejemplo:
        celda A = posibles {1,3,7}
        celda B = posibles {2,3}
        celda C = posibles {4,7,9}
        Es decir que todos los valores posibles son: {1,2,3,4,7,9}
        Con esto se revisa cada combinación posible de la celda
        """
        for cell in cells:
            union_mask |= dom[cell]

        #Filtrar combos válidos
        for cm in combos:
            #deja únicamente aquellas que todavía son compatibles con los dominios actuales de las celdas
            #Por ejemplo si ninguna celda puede ser 5 u 8 entonces se descarta cualquier combinación que los incluya
            if (cm & ~union_mask) != 0:
                continue
            ok = True
            b = cm
            """
            Hay que tener en cuenta que el primer if descarta las combinaciones que incluyan alguno de los posibles valores de las celdas
            esten ahí, pero no todas
            En este while se recorre bit por bit los dígitos Cada bit representa un número para formar la suma por ejemplo (1+3+7)
            Este while verifica que cada dígito de la combinación tenga por lo menos una celda donde podría ir
            """
            while b:
                lsb = (b & -b)
                b -= lsb
                #Este id determina si al menos un valor de los bits puede tomar la celda
                #Si entra al if es porque NO se puede tomar ningún valor
                #Si NO entra es porque SÍ entra es porque almenos una celda puede tomar ese valor 
                if not any(dom[cell] & lsb for cell in cells):
                    ok = False
                    break
            #Si ok estrue, se agrega a la lista valid
            if ok:
                valid.append(cm)
        #Si la lista valid está vacío es porque no hay combos validos
        if not valid:
            if VERBOSE: log(f"[CAGE FAIL] Cage {cage['id']} has no valid combos")
            return False

        # allowed_per_cell por restricción de combinaciones
        allowed = {cell: 0 for cell in cells}

        #De los valores que son validos revisar cada uno de sus digitos
        #Y por cada digito verificar cuál de ellos puede tomar una celda
        """
        Por ejemplo si la suma da 10 y esta es la lista valid: {1,9}, {2,8}, {3,7}, {4,6}
        Y revisa cada uno si está en el dominio actual de la lista
        """
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
            #Aquí se hace una interesección entre dodom[cell](Los dominios de la celda)
            #Y de allowed[cell] lo que la celda permite
            new = dom[cell] & allowed[cell]
            if new != dom[cell]:
                #Si entró al if, es porque hubo cambios en el dominio
                if VERBOSE:
                    log(f"[CAGE REDUCE] {coord_to_cell(cell)} "
                        f"{digits_from_mask(dom[cell])} → {digits_from_mask(new)}")

                changes.append((cell, dom[cell]))
                dom[cell] = new
                #Si entra al if es porque el dominio de la celda está vacío
                if new == 0:
                    if VERBOSE: log(f"[FAIL] Domain of {coord_to_cell(cell)} became EMPTY")
                    return False
                #Cuenta los bitds
                if count_bits(new) == 1:
                    singleton = new
                    for p in PEERS[cell]:
                        #Recordar que eliminate elimina el valor de un dominio, pero también busca que los vecinos lo hagan
                        #Es decir que si se va a poner o eliminar un valor, deben cumplir la restricción de fila, columna y subcuadro 3x3
                        if not eliminate(dom, p, singleton, changes):
                            #Si entró al if es porque hay contradicción lógica, entonces nada que hacer
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
    #Toma el dominio y los convierte en digitos y se asigna a vals como la lista de dominios de una celda
    #específica
    vals = digits_from_mask(dom[var])
    impacts = []
    for v in vals:
        #Recordar que mask for digit convierte la lista de digitos a bits
        vm = mask_for_digit(v)
        cnt = 0
        #PEERS[var] accede a las celdas vecionas, columna, fila y subcuadro 3x3
        #p es cada una de esas celdas
        for p in PEERS[var]:
            #Este if verifica si el dominio de la celda 
            if dom[p] & vm:
                #cnt es un contador que verifica el impacto
                cnt += 1
        #Se define impacto a la cantidad de vecinos que quieren usar ese mismo valor
        #Por lo tanto la lista queda como una tupla del valor que se le quiere asignar junto con su impacto
        impacts.append((cnt, v))
    #Y esto solo ordena de menor a mayor impacto
    impacts.sort()
    ordered = [v for _,v in impacts]
    if VERBOSE:
        log(f"[ORDER] {coord_to_cell(var)} order {ordered}")
    return ordered

def backtrack(dom, depth=0):
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
    #var es la celda con el dominio más pequeño, devuelve la coordenada con el dominio más pequeño posible
    #Si (2,3) tiene como dominio {1,3,4,5} y select_unassigned_variable devuelve {1,5} es porque es lo más pequeño que puede ser
    var = select_unassigned_variable(dom)
    if var is None:
        return False

    if VERBOSE:
        log(f"{'  '*depth}[BRANCH] Try variable {coord_to_cell(var)} with domain {digits_from_mask(dom[var])}")
    #Este for va a iterar una cantidad equivalente a los valores del dominio de una celda
    for v in order_values(dom, var):
        vm = mask_for_digit(v)
        changes = []
        if VERBOSE:
            log(f"{'  '*depth}[TRY] {coord_to_cell(var)} = {v}")
        #Basicmente asigna un valor del dominio en una celda
        if not assign(dom, var, vm, changes):
            #Si entró es porque retorna un false
            if VERBOSE: log(f"{'  '*depth}[FAIL-ASSIGN] {coord_to_cell(var)} = {v}")
            #Reversed es una forma de iteración inversa
            for c,prev in reversed(changes):
                dom[c] = prev
            continue

        if not prune_by_cage(dom, changes):
            if VERBOSE: log(f"{'  '*depth}[FAIL-PRUNE] after assigning {coord_to_cell(var)} = {v}")
            #Iteración inversa
            for c,prev in reversed(changes):
                dom[c] = prev
            continue
        #Si llegó hasta aquí fue porque se pudo asignar un valor a la celda actual sin contradicciones y aplicas todas las sumas
        #Entonces se avanza para resolver el resto del tablero
        if backtrack(dom, depth+1):
            return True
        # undo
        if VERBOSE: log(f"{'  '*depth}[BACKTRACK] undo {coord_to_cell(var)} = {v}")
        for c,prev in reversed(changes):
            dom[c] = prev
    return False

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