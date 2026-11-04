"""Check repeated disk-backed complex factorizations against dense solves.

From Frontend/emerge: python -m tests.pardiso_ooc
Requires the same MKL/PARDISO runtime as the 3-D simulations.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import numpy as np
from scipy.sparse import csr_matrix
from emerge._emerge.solver import AutomaticRoutine
from simulation.memory import configure_pardiso_ooc


def main():
    parent = Path(__file__).resolve().parents[1]/'catalogue'
    with TemporaryDirectory(prefix='ooc-test-', dir=parent) as directory:
        assert Path(directory).resolve().is_relative_to(parent.resolve())
        backend = configure_pardiso_ooc(AutomaticRoutine(), directory, 128)
        a = csr_matrix(np.array([[5+1j, 1, 0], [1.2, 4+2j, 1], [0, 1, 3-.5j]], complex))
        b = np.array([1, 2, 3], complex)
        try:
            interface = backend.solver
            assert interface.symbolic(a) == 0
            for matrix in [a, a*.9+csr_matrix(np.eye(3)), a*1.1]:
                assert interface.numeric(matrix) == 0
                x, error = interface.solve(matrix, b)
                assert error == 0
                assert np.linalg.norm(matrix@x-b) < 1e-10
                assert np.allclose(x, np.linalg.solve(matrix.toarray(), b), atol=1e-10)
            assert interface.IPARM[0] == 1 and interface.IPARM[59] == 2
        finally:
            backend.reset()
    print('PASS: one analysis and three disk-backed numeric solves agree with dense reference.')


if __name__ == '__main__':
    main()
