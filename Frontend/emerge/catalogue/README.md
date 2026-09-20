# Simulation database

Rebuild with `python coupler_catalogue.py` from the EMerge directory. No EM runs are performed. The generated SQLite file is excluded from Git; all source matrices are committed. `catalogue_ids.json` preserves IDs and `run_timestamps.json` preserves original configuration timestamps across checkouts. The DB contains redesign attempts (including the incomplete port-mode run), straight controls, all legacy NPZ files, complete complex S matrices where present, port impedances, parameters and source hashes. Paths are relative to `Frontend/emerge`.

`simulations`: geometry in mm, status, sampling provenance, mesh sizes and scalar metrics. `config_json` retains every original parameter including lower-stack and solver settings. Historical parameters are parsed only when encoded explicitly; unknown values are NULL. `samples`: complex S entries, frequency in Hz, 1-based ports, modal or 50-ohm reference. `port_references`: complex modal impedances. `artifacts`: file provenance and SHA-256. `comparison`: convenient view.

All scalar results use 50 ohm and 5.7–5.9 GHz; centre is the stored sample nearest 5.8 GHz. One-sample Dmin is not broadband. Fitted legacy curves must not be ranked as equally validated against direct new samples. Stages explain groups of experiments; they do not imply a deterministic parent-child optimization or measured gradients.

```sql
SELECT * FROM comparison WHERE stage = 'final';
SELECT id,label,length_mm,gap_mm,d_min_db FROM comparison
WHERE status='completed' AND sampling='direct'
  AND edge_mesh_mm=0.04 AND band_samples>=3 ORDER BY d_min_db DESC;
SELECT frequency_hz,real,imag FROM samples
WHERE simulation_id=(SELECT id FROM simulations WHERE alias='final51')
  AND reference='50ohm' AND output_port=4 AND input_port=1
ORDER BY frequency_hz;
SELECT id,alias,config_json FROM simulations WHERE symmetry='symmetric';
```
