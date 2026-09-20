# Historical helpers

These files are retained for provenance, not used by the current report pipeline. They were moved out of the working directory during the September 2026 cleanup. Some contain original absolute paths or assume their former location; they are archival source snapshots, not supported entry points.

- `README.md`: original workflow narrative, including obsolete setup and shielding statements. Use the parent README for current facts.
- `audit_results.py`, `cap_opt.py`, `coupled_theory.py`: historical audit, circuit search and analytic calculations.
- `figs.py`, `figs_comb.py`, `render_em.py`: superseded report renderers.
- `probe_api.py`: original API exploration.
- `redesign_batch.py`: old queue worker; no active queue is retained.
- `unused_configs/`: proposals without matching saved simulation results, plus the old queue. These are not additional completed experiments.

The current driver still imports `../coupler_sim.py`; it must remain in the active directory. `../redesign_figures.py` and `../figs_2d.py` also remain because the current documents use some of their illustrations.
