"""Circuit-level compensation sweep: load an uncompensated 4-port with a
capacitor across each end and find the value that maximises directivity.

Equivalent to dropping the .s4p into a QUCS S-parameter block and putting a
C from port1-port3 and port2-port4, but scriptable.

The caps land exactly on the port reference planes, so WHERE the ports are
decides what the answer means.  Run this on `..._nocomb_atcomb_pw1.1.npz`,
whose ports sit on the comb planes: the capacitance that comes out is then the
comb's own capacitance and is directly comparable with the etched comb.  Run it
on the full-feed `..._nocomb.npz` instead and the ports are ~2.6 mm outside the
comb, so the answer is an equivalent end capacitance that the comb cannot be
sized against.
"""
import sys
import numpy as np

BAND = (5.7e9, 5.9e9)


def load(npz):
    d = np.load(npz)
    f = d["f"]
    S = d["Smat"]                      # port-referenced, (nF,4,4)
    Z0 = np.real(np.asarray(d["Z0"]))
    if Z0.ndim == 2:                        # (nF, 4), one per port -- keep them
        z0 = Z0                             # separate; they are not identical
    else:                                   # in the de-embedded model
        z0 = np.full((f.size, 4), float(Z0))
    return f, S, z0


def add_caps(S, f, z0, C):
    """Shunt C between ports 1-3 and 2-4 (0-indexed 0-2 and 1-3).

    z0 is per-port and per-frequency, so the S<->Y conversion carries a
    diag(sqrt(z)) on each side rather than a single scalar.  With four equal
    port impedances this collapses to the textbook scalar form.
    """
    I = np.eye(4)
    out = np.empty_like(S)
    for k in range(S.shape[0]):
        Sk = S[k]
        rz = np.sqrt(z0[k])                       # (4,)
        Y = (np.linalg.inv(I + Sk) @ (I - Sk)) / np.outer(rz, rz)
        y = 2j * np.pi * f[k] * C
        for i, j in ((0, 2), (1, 3)):
            Y[i, i] += y; Y[j, j] += y; Y[i, j] -= y; Y[j, i] -= y
        Yn = Y * np.outer(rz, rz)
        out[k] = np.linalg.inv(I + Yn) @ (I - Yn)
    return out


def metrics(f, S):
    db = lambda x: 20 * np.log10(np.abs(x) + 1e-30)
    inb = (f >= BAND[0]) & (f <= BAND[1])
    i58 = int(np.argmin(np.abs(f - 5.8e9)))
    D = db(S[:, 2, 0]) - db(S[:, 3, 0])
    return dict(S11=db(S[:, 0, 0])[i58], S21=db(S[:, 1, 0])[i58],
                S31=db(S[:, 2, 0])[i58], S41=db(S[:, 3, 0])[i58],
                D58=D[i58], Dworst=float(D[inb].min()),
                S31w=float(db(S[:, 2, 0])[inb].min()))


if __name__ == "__main__":
    f, S, z0 = load(sys.argv[1])
    print(f"reference impedance {z0.mean():.2f} ohm\n")
    m = metrics(f, S)
    print(f"{'C (pF)':>8} {'S11':>7} {'S31':>7} {'S21':>7} {'S41':>7} "
          f"{'D@5.8':>7} {'Dworst':>7}")
    print(f"{'0 (bare)':>8} {m['S11']:7.2f} {m['S31']:7.2f} {m['S21']:7.3f} "
          f"{m['S41']:7.2f} {m['D58']:7.2f} {m['Dworst']:7.2f}")
    best = (None, -99)
    for C in np.arange(0.005, 0.121, 0.005) * 1e-12:
        m = metrics(f, add_caps(S, f, z0, C))
        if m["Dworst"] > best[1]:
            best = (C, m["Dworst"])
        print(f"{C*1e12:8.3f} {m['S11']:7.2f} {m['S31']:7.2f} {m['S21']:7.3f} "
              f"{m['S41']:7.2f} {m['D58']:7.2f} {m['Dworst']:7.2f}")
    # refine
    lo, hi = best[0] - 5e-15, best[0] + 5e-15
    for C in np.linspace(lo, hi, 11):
        m = metrics(f, add_caps(S, f, z0, C))
        if m["Dworst"] > best[1]:
            best = (C, m["Dworst"])
    m = metrics(f, add_caps(S, f, z0, best[0]))
    print(f"\nOPTIMUM  C = {best[0]*1e12:.4f} pF per end -> Dworst {best[1]:.2f} dB, "
          f"S31 {m['S31']:.2f}, S11 {m['S11']:.2f}, S21 {m['S21']:.3f}")
    for tgt in (20.0, 15.0, 12.0):
        ok = [C for C in np.arange(0.002, 0.200, 0.002) * 1e-12
              if metrics(f, add_caps(S, f, z0, C))["Dworst"] >= tgt]
        if ok:
            print(f"  >= {tgt:4.1f} dB window: {min(ok)*1e12:.3f} .. {max(ok)*1e12:.3f} pF")
