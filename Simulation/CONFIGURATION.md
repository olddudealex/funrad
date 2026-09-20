# ToyRadar executable configuration

`configs/FunRad.RevA.toyradar` is the machine-readable working configuration for FunRad Rev.A. It is loaded by the GUI and by the headless calculator.

The file separates four concepts:

- `blocks`: hardware/model instances, part numbers, parameters, and decision status;
- `connections`: typed signal-path connections between stable block IDs;
- `scenarios`: target and operating-point overrides that do not change the hardware definition;
- `analyses`: calculation conventions such as the minimum SNR.

## Base values and GUI scenarios

The GUI and headless report generator use the same merge rule:

```text
effective block parameters = base blocks[].params + selected scenario overrides
```

The GUI scenario selector changes only effective parameter values; the block
topology and layout remain shared. With **Base configuration** selected,
parameter edits update `blocks[].params`. With a named scenario selected,
parameter edits update that scenario's `overrides` instead.

**Add scenario** creates a named scenario. When another scenario is active,
its overrides can be copied as the starting point; selecting Base creates an
empty scenario. **Delete scenario** removes the active named scenario after
confirmation and is disabled for Base. Pinned plots remain attached to the
same stable block ID and are recalculated when the scenario changes.

An overridden field is marked with `*` in the property panel. **Reset** removes
that individual override and reveals the base value. **Promote block overrides
to base** deliberately moves all overrides for the selected block into the base
configuration. Saving always preserves the canonical base values and scenario
overrides rather than flattening the selected scenario into the base.

Scenarios cannot change topology. Hardware variants with different blocks or
connections belong in separate `.toyradar` configuration files.

Derived values are never written back into the input configuration. They are generated as:

- `generated/FunRad.RevA.results.json` for tools and regression tests;
- `generated/FunRad.RevA.results.md` as the default Markdown report.

An explicit output path can additionally place or update a report in the Obsidian vault.

## Environment

Use the simulator-local environment for every command:

```powershell
Simulation\.venv\Scripts\python.exe -m pip install -r Simulation\requirements.txt
```

## Validate

```powershell
Simulation\.venv\Scripts\python.exe Simulation\main.py validate Simulation\configs\FunRad.RevA.toyradar
```

Validation checks schema version, registered block types, known and required parameters, value types and ranges, port names and domains, duplicate destinations, missing required inputs, cycles, scenario overrides, and analysis settings.

Unversioned files are passed through an explicit legacy migration. Known obsolete parameters are converted with warnings. Current versioned files reject unknown parameters instead of silently ignoring them.

## Calculate and generate reports

```powershell
Simulation\.venv\Scripts\python.exe Simulation\main.py calculate Simulation\configs\FunRad.RevA.toyradar
```

When an output argument is omitted, its report is written to the simulator's
`generated` subfolder. The configuration filename determines the report name.
This location does not depend on the current working directory.

Use `--json-output` or `--markdown-output` to override either destination, for
example to update the Obsidian report:

```powershell
Simulation\.venv\Scripts\python.exe Simulation\main.py calculate Simulation\configs\FunRad.RevA.toyradar `
  --markdown-output "Notes\FunRad\Generated\FunRad Rev.A Results.md"
```

The JSON result includes the engine version and SHA-256 hash of the complete input configuration. If the hash changes, the old report is stale.

## Parameter definitions

Every block exposes `ParameterSpec` metadata derived from its parameter declaration: label, Python type, engineering unit, valid choices, and numeric limits. The GUI and strict validator use the same metadata.

Configuration keys retain explicit engineering-unit suffixes such as `gain_db`, `bandwidth_mhz`, and `distance_m`. This keeps version 1 compatible with existing simulator code while preventing unit ambiguity. A future schema migration may introduce generic quantity objects if unit conversion becomes necessary.

Per-design decision information belongs in `parameter_metadata`:

```json
"parameter_metadata": {
  "nf_db": {
    "status": "chosen",
    "note": "Value at 5.8 GHz",
    "source": "QPL9504 datasheet"
  }
}
```

Allowed statuses are `chosen`, `working`, `provisional`, `open`, and `measured`.

## Structural and semantic schemas

`configs/toyradar.schema.json` defines the portable JSON structure. `config.py` performs the stricter semantic validation that depends on registered Python block definitions and port metadata.
