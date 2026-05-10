# Antenna Measurement Tools

Python scripts for plotting S-parameter files and comparing simulated vs measured antenna directivity patterns.

## Files

- `plot_s1p.py` — Plots all S1P files in the directory (S11 magnitude and phase)
- `compare_directivity.py` — Compares directivity from two simulations and measured gain patterns; outputs interactive HTML and PNG
- `plot_gain_vs_angle.py` — Plots the measured gain pattern at multiple frequencies on the same Cartesian and polar axes; annotates beam peak angle and HPBW for each frequency
- `directivity_measurements.db` — SQLite database of antenna gain measurements written by the servo controller
- `requirements.txt` — Python dependencies
- `venv/` — Virtual environment

## Setup

Virtual environment is already created and dependencies are installed.

To activate the virtual environment:

**Windows (Command Prompt):**
```
venv\Scripts\activate.bat
```

**Windows (PowerShell):**
```
venv\Scripts\Activate.ps1
```

**Linux/Mac:**
```
source venv/bin/activate
```

## Usage

Run the plotting script:

```bash
venv\Scripts\python.exe plot_s1p.py
```

Or if venv is activated:

```bash
python plot_s1p.py
```

The script will:
1. Load all S1P files from the current directory
2. Plot S11 magnitude (in dB) and phase (in degrees)
3. Save the plot as `s1p_plot.png`
4. Display the plot in a window

### compare_directivity.py

Compares two simulation directivity files (OpenEMS and Emerge) against measured antenna gain patterns from the SQLite database. Produces four subplots: Cartesian and polar for both E-plane and H-plane.

```bash
venv\Scripts\python.exe compare_directivity.py
```

Outputs `directivity_comparison.html` (interactive, opens automatically in browser) and `directivity_comparison.png`.

Key config constants at the top of the file:

| Constant | Description |
|---|---|
| `SIM1_FILE` / `SIM2_FILE` | Paths to simulation directivity `.txt` files |
| `SIM1_LABEL` / `SIM2_LABEL` | Legend labels |
| `SIM1_EH_SWAPPED` / `SIM2_EH_SWAPPED` | Swap E/H plane columns if the simulator output them in the wrong order |
| `SIM1_MIRRORED` / `SIM2_MIRRORED` / `MEAS_MIRRORED` | Flip the angular axis left↔right (use when the data was captured rotating in the opposite direction) |
| `DB_FILE` | Path to the SQLite measurement database |
| `DISTANCE_CM` | Antenna separation in cm (used for Friis FSPL calculation) |
| `EPLANE_TEST_RANK` / `HPLANE_TEST_RANK` | Which DB test to use per plane: `0` = latest, `1` = second-to-latest, … |
| `POLAR_DYNAMIC_RANGE_DB` | Radial axis range of the polar subplots (dB below peak) |

### plot_gain_vs_angle.py

Plots the measured gain pattern at multiple frequencies on the same Cartesian and polar axes. Automatically computes and annotates the beam peak angle and HPBW (−3 dB beamwidth) for each frequency.

```bash
venv\Scripts\python.exe plot_gain_vs_angle.py
```

Outputs `gain_vs_angle.html` and `gain_vs_angle.png`.

| Constant | Description |
|---|---|
| `DB_FILE` | Path to the SQLite measurement database |
| `TEST_RANK` | Which test to use: `0` = latest, `1` = second-to-latest, … |
| `PLANE_LABEL` | Label shown in the plot title (e.g. `"E-plane"`) |
| `DISTANCE_CM` | Antenna separation in cm |
| `FREQUENCIES_GHZ` | List of up to 3 frequencies to overlay |
| `MEAS_MIRRORED` | Flip angular axis if the measurement was taken in the wrong rotation direction |
| `POLAR_DYNAMIC_RANGE_DB` | Radial axis range of the polar subplot |

## Dependencies

- scikit-rf: RF/microwave engineering toolkit
- matplotlib: Plotting library
- numpy: Numerical computing library
- plotly: Interactive plotting (for compare_directivity.py)
- kaleido: Static image export (for compare_directivity.py)
