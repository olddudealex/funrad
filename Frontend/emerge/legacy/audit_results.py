"""Audit saved sweeps without running EMerge. Writes a comparison CSV.

Saved curves are fitted samples, not independent EM solves. No geometry or
simulation result is changed. Uses only NumPy and the Python standard library.
"""
from pathlib import Path
import csv
import numpy as np

HERE = Path(__file__).resolve().parent


def metrics(f, s):
    band = (f >= 5.7e9) & (f <= 5.9e9)
    i = np.argmin(abs(f - 5.8e9))
    db = 20 * np.log10(np.maximum(abs(s), 1e-30))
    d = db[:, 2, 0] - db[:, 3, 0]
    return dict(S11_center=db[i, 0, 0], S21_center=db[i, 1, 0],
                S31_center=db[i, 2, 0], S41_center=db[i, 3, 0],
                D_min=d[band].min(), coupling_min=db[band, 2, 0].min(),
                coupling_max=db[band, 2, 0].max(),
                RL_min=-db[band, 0, 0].max(),
                reciprocity_max=np.max(abs(s[band] - s[band].transpose(0, 2, 1))),
                singular_value_max=np.linalg.svd(s[band], compute_uv=False).max())


def renormalize_real(s, z):
    """Independent real-reference S -> Y -> 50-ohm S conversion."""
    identity = np.eye(4)
    root = np.sqrt(z)
    y = np.linalg.solve(identity + s, identity - s) / (root[:, :, None] * root[:, None, :])
    return np.linalg.solve(identity + 50 * y, identity - 50 * y)


if __name__ == '__main__':
    rows = []
    for path in sorted((HERE / 'results').glob('*.npz')):
        with np.load(path) as data:
            if not {'Smat', 'Smat50', 'Z0'} <= set(data.files):
                continue
            z = np.broadcast_to(data['Z0'], (len(data['f']), 4))
            error = np.max(abs(renormalize_real(data['Smat'], z) - data['Smat50']))
            for reference, key in [('port', 'Smat'), ('50ohm', 'Smat50')]:
                rows.append(dict(file=path.name, reference=reference,
                                 Z0_min=z.min(), Z0_max=z.max(),
                                 renormalization_error=error,
                                 **metrics(data['f'], data[key])))
    dest = HERE / 'results' / 'audit_summary.csv'
    with dest.open('w', newline='', encoding='utf-8') as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    selected = {'sparams_opt_nocomb.npz', 'sparams_opt_comb3.npz',
                'sparams_opt_comb3_w0.37s0.11o0.27y1j0.9.npz',
                'sparams_opt_comb3_w0.38s0.11o0.27y1j0.9.npz',
                'sparams_opt_comb3_sym_w0.38s0.11o0.27y1.4j0.9b90.npz',
                'sparams_opt_nocomb_atcomb.npz'}
    for row in rows:
        if row['file'] in selected:
            print(row['file'], row['reference'])
            print(' '.join(f'{key}={value:.4f}' for key, value in row.items()
                           if isinstance(value, (float, np.floating))))
    print(f'Wrote {len(rows)} rows to {dest}')
