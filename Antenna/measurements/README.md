# S1P File Plotter

Simple Python project to plot S-parameter files using scikit-rf and matplotlib.

## Files

- `plot_s1p.py` - Main script that plots all S1P files in the directory
- `requirements.txt` - Python dependencies
- `venv/` - Virtual environment (created)

## S1P Files

The following S1P files will be plotted:
- SN00001_2026-02-07_22-19-09.s1p
- SN00002_2026-02-07_22-24-50.s1p
- SN00003_2026-02-07_22-26-34.s1p

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

## Dependencies

- scikit-rf: RF/microwave engineering toolkit
- matplotlib: Plotting library
- numpy: Numerical computing library
