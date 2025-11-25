import json
import logging
import sys
from itertools import combinations

# ------------------------------------------------------
# CONFIGURACIÓN DEL LOG
# ------------------------------------------------------
logging.basicConfig(
    filename="killer_solver.log",
    filemode="w",
    level=logging.DEBUG,
    format="%(message)s"
)

def log(msg):
    print(msg)
    logging.debug(msg)

# ------------------------------------------------------
# CLASE DEL SOLVER CSP
# ------------------------------------------------------
class KillerSudokuCSP:
    def __init__(self, cages):
        self.cages = cages

        # Variables: celdas A1..I9 -> coordenadas (fila, col)
        self.cells = [(r, c) for r in range(9) for c in range(9)]

        # Dominios: inicialmente 1..9
        self.domains = {cell: set(range(1, 10)) for cell in self.cells}

        # Asignaciones
        self.assignments = {}

        # Mapa celda -> jaula
        self.cage_map = {}
        for cage in cages:
            for (row, col) in cage["cells"]:
                self.cage_map[(row, col)] = cage

    # --------------------------------------------------
    # Restricción: no duplicados en fila/columna/subcuadro
    # --------------------------------------------------
    def is_valid_standard(self, cell, value):

        row, col = cell

        # Fila
        for c in range(9):
            if (row, c) in self.assignments and self.assignments[(row, c)] == value:
                return False

        # Columna
        for r in range(9):
            if (r, col) in self.assignments and self.assignments[(r, col)] == value:
                return False

        # Subcuadro
        br = (row // 3) * 3
        bc = (col // 3) * 3

        for r in range(br, br + 3):
            for c in range(bc, bc + 3):
                if (r, c) in self.assignments and self.assignments[(r, c)] == value:
                    return False

        return True

    # --------------------------------------------------
    # Restricción killer: suma de la jaula
    # --------------------------------------------------
    def is_valid_cage(self, cell, value):

        cage = self.cage_map[cell]
        cage_cells = cage["cells"]
        target_sum = cage["sum"]

        used_values = []
        empty = 0

        for rc in cage_cells:
            if rc in self.assignments:
                used_values.append(self.assignments[rc])
            else:
                empty += 1

        # No repetir números dentro de la jaula
        if value in used_values:
            return False

        # Suma actual + nuevo valor
        current_sum = sum(used_values) + value

        # Si no es la última celda de la jaula
        if empty > 1:
            if current_sum >= target_sum:
                return False
        else:
            # Última celda → debe coincidir exactamente
            if current_sum != target_sum:
                return False

        return True

    # --------------------------------------------------
    # Chequea si un valor es válido
    # --------------------------------------------------
    def is_valid(self, cell, value):
        return self.is_valid_standard(cell, value) and self.is_valid_cage(cell, value)

    # --------------------------------------------------
    # Heurística MRV
    # --------------------------------------------------
    def select_unassigned_cell(self):
        unassigned = [c for c in self.cells if c not in self.assignments]
        return min(unassigned, key=lambda c: len(self.domains[c]))

    # --------------------------------------------------
    # Orden de valores LCV
    # --------------------------------------------------
    def order_domain_values(self, cell):
        return sorted(list(self.domains[cell]), key=lambda v: self.count_conflicts(cell, v))

    def count_conflicts(self, cell, value):
        row, col = cell
        count = 0
        for c in range(9):
            if value in self.domains[(row, c)]:
                count += 1
        for r in range(9):
            if value in self.domains[(r, col)]:
                count += 1
        return count

    # --------------------------------------------------
    # Propagación: forward checking
    # --------------------------------------------------
    def forward_check(self, cell, value, removed):
        row, col = cell

        # vecinos de fila/columna/subcuadro
        neighbors = set()

        for c in range(9):
            neighbors.add((row, c))
        for r in range(9):
            neighbors.add((r, col))

        br = (row // 3) * 3
        bc = (col // 3) * 3

        for r in range(br, br + 3):
            for c in range(bc, bc + 3):
                neighbors.add((r, c))

        neighbors.discard(cell)

        for n in neighbors:
            if n in self.assignments:
                continue
            if value in self.domains[n]:
                removed[n].add(value)
                self.domains[n].remove(value)
                if len(self.domains[n]) == 0:
                    return False

        return True

    # --------------------------------------------------
    # Backtracking
    # --------------------------------------------------
    def backtrack(self):

        if len(self.assignments) == 81:
            return True

        cell = self.select_unassigned_cell()
        row, col = cell
        log(f"Seleccionando celda {cell}, dominio={self.domains[cell]}")

        for value in self.order_domain_values(cell):

            if self.is_valid(cell, value):
                log(f"Intentando asignar {value} a {cell}")

                self.assignments[cell] = value
                removed = {c: set() for c in self.cells}

                if self.forward_check(cell, value, removed):
                    if self.backtrack():
                        return True

                # deshacer propagación
                del self.assignments[cell]
                for c in removed:
                    self.domains[c].update(removed[c])

                log(f"Deshaciendo asignación de {value} a {cell}")

        return False

    # --------------------------------------------------
    # Solve
    # --------------------------------------------------
    def solve(self):
        ok = self.backtrack()
        if ok:
            board = [[self.assignments[(r, c)] for c in range(9)] for r in range(9)]
            return board
        else:
            return None

# ------------------------------------------------------
# MAIN
# ------------------------------------------------------
if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Uso: python killer_solver.py puzzle.json")
        exit()

    puzzle_file = sys.argv[1]

    with open(puzzle_file, "r", encoding="utf-8") as f:
        cages = json.load(f)

    solver = KillerSudokuCSP(cages)
    solution = solver.solve()

    if solution:
        log("\n=== SOLUCIÓN ENCONTRADA ===")
        for row in solution:
            log(str(row))

        with open("solution.json", "w", encoding="utf-8") as f:
            json.dump(solution, f, indent=2)

        with open("solution.txt", "w", encoding="utf-8") as f:
            for row in solution:
                f.write(" ".join(str(x) for x in row) + "\n")

        print("Listo: solución generada en solution.json & solution.txt")

    else:
        print("No tiene solución.")
        log("NO SE ENCONTRÓ SOLUCIÓN")
