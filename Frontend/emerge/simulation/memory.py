"""Optional PARDISO disk-backed factors for RAM-limited workstations.

Only linear-solver storage changes; geometry, basis and precision are retained.
Intel reference: https://www.intel.com/content/www/us/en/developer/articles/training/how-to-use-ooc-pardiso.html
"""
import ctypes
import os
from pathlib import Path
from enum import Enum
import numpy as np
from emerge._emerge.solve_interfaces.pardiso_interface import PardisoInterface


class FactorPhase(Enum):
    NUMERIC = 22


class DiskBackedPardisoInterface(PardisoInterface):
    def numeric(self, matrix):
        # EMerge 2.8.9 uses phase 12 here, repeating symbolic analysis on an
        # existing disk-backed handle. Phase 22 reuses the analysed pattern.
        self._configure(matrix)
        unused_rhs = np.zeros((matrix.shape[0], 1), dtype=matrix.dtype)
        _, error = self._call_solver(matrix, unused_rhs, phase=FactorPhase.NUMERIC)
        return error


def configure_pardiso_ooc(routine, directory, memory_mb):
    from emerge._emerge.solver import EMSolver
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    os.environ['MKL_PARDISO_OOC_PATH'] = str(directory)
    os.environ['MKL_PARDISO_OOC_MAX_CORE_SIZE'] = str(int(memory_mb))
    os.environ['MKL_PARDISO_OOC_MAX_SWAP_SIZE'] = '0'
    backend = routine.solvers[EMSolver.PARDISO]
    backend.solver = DiskBackedPardisoInterface()
    backend.initialized = True
    backend.fact_symb = False
    interface = backend.solver
    # Load MKL's defaults before overriding iparm[59]. iparm[0]=0 would
    # otherwise request defaults and ignore this explicit OOC choice.
    init = interface.libmkl.pardisoinit
    init.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int32), ctypes.c_void_p]
    init.restype = None
    matrix_type = ctypes.c_int32(3)  # EMerge's complex structurally symmetric system.
    init(interface.PT.ctypes.data, ctypes.byref(matrix_type), interface.IPARM.ctypes.data)
    interface.IPARM[0] = 1
    interface.IPARM[59] = 2
    return backend
