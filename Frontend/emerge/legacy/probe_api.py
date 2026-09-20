#!/usr/bin/env python
"""
Print the EMerge API surface this install actually exposes.

coupler_sim.py is written against the API in the vendor's published
stepped-impedance-filter example.  EMerge moves fast, so run this first and
check the four things the coupler script depends on:

  1.  em.geo.PCB(...)          - constructor arguments, and what .z(i) returns
  2.  the path builder          - .new() signature, and whether .straight() is
                                  the only segment primitive or there is a
                                  native bend / mitre / arc
  3.  modal_port / compile_paths / determine_bounds / generate_pcb
  4.  m.mw.bc.*                 - ModalPort, PEC
      m.mw.run_sweep(...)       - and what the solution object exposes

If anything below disagrees with coupler_sim.py, the fix is almost always a
one-line change in Layout.seg() or in simulate().

    python probe_api.py            # summary
    python probe_api.py --full     # every public member, with docstrings
"""
from __future__ import annotations

import argparse
import inspect
import sys


def sig(obj, name):
    try:
        return f"{name}{inspect.signature(getattr(obj, name))}"
    except (TypeError, ValueError):
        return f"{name}(?)"


def dump(obj, title, full=False, only=None):
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")
    if obj is None:
        print("  <not available>")
        return
    names = [n for n in dir(obj) if not n.startswith("_")]
    if only:
        names = [n for n in names if n in only] or names
    for n in sorted(names):
        try:
            member = getattr(obj, n)
        except Exception as exc:                      # noqa: BLE001
            print(f"  {n}: <error {exc}>")
            continue
        if callable(member):
            print(f"  {sig(obj, n)}")
            if full:
                doc = (inspect.getdoc(member) or "").strip().splitlines()
                for line in doc[:6]:
                    print(f"      | {line}")
        elif full:
            print(f"  {n} = {member!r}"[:160])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()

    import emerge as em
    print(f"emerge  {getattr(em, '__version__', '?')}   from {em.__file__}")
    print(f"python  {sys.version.split()[0]}")

    dump(em, "emerge top level", args.full)
    dump(getattr(em, "geo", None), "emerge.geo", args.full)

    PCB = getattr(getattr(em, "geo", None), "PCB", None)
    if PCB is not None:
        print(f"\n  em.geo.PCB{inspect.signature(PCB.__init__)}")
        dump(PCB, "em.geo.PCB methods", args.full,
             only={"new", "z", "modal_port", "lumped_port", "compile_paths",
                   "determine_bounds", "generate_pcb", "load", "store",
                   "polygon", "add_polygon", "via", "layer"})

    # --- the path builder: build a throwaway board and inspect what new() returns
    try:
        mat = em.Material(er=4.4, tand=0.02)
        lo = em.geo.PCB(0.2104, unit=1e-3, material=mat, layers=2)
        print(f"\n  z(i) for i in 0..3: "
              f"{[getattr(lo, 'z', lambda i: None)(i) for i in range(4)]}")
        path = lo.new(0, 0, 0.371, (1, 0), z=lo.z(1))
        dump(type(path), f"path object returned by .new()  ->  {type(path).__name__}",
             args.full)
        print("\n  LOOK FOR: bend / turn / arc / mitre / taper / to / goto / polygon")
    except Exception as exc:                          # noqa: BLE001
        print(f"\n  could not build a probe PCB: {type(exc).__name__}: {exc}")

    # --- simulation side
    try:
        m = em.Simulation("probe")
        dump(m, "em.Simulation instance", args.full,
             only={"commit_geometry", "generate_mesh", "mw", "mesher", "display"})
        dump(getattr(m, "mw", None), "m.mw", args.full,
             only={"set_resolution", "set_frequency_range", "run_sweep", "bc"})
        dump(getattr(getattr(m, "mw", None), "bc", None), "m.mw.bc", args.full)
        dump(getattr(m, "mesher", None), "m.mesher", args.full,
             only={"set_boundary_size", "set_face_size", "set_domain_size"})
    except Exception as exc:                          # noqa: BLE001
        print(f"\n  could not build a probe Simulation: {type(exc).__name__}: {exc}")

    print("\nDone.  Paste this output back if the coupler script needs adjusting.")


if __name__ == "__main__":
    main()
