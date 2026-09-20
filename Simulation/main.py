import argparse
import sys
import os
from pathlib import Path

# Ensure the Simulation directory is on the path so relative imports work
sys.path.insert(0, os.path.dirname(__file__))

SIMULATION_DIR = Path(__file__).resolve().parent
DEFAULT_REPORT_DIR = SIMULATION_DIR / "generated"


def default_report_path(config_path: str | Path, report_suffix: str) -> Path:
    """Return a report path without treating dots in the config stem as suffixes."""
    return DEFAULT_REPORT_DIR / f"{Path(config_path).stem}{report_suffix}"

def _setup_font() -> None:
    """Load Consolas for the whole UI.

    DPG 2.x builds the glyph atlas automatically from all characters present
    in the loaded TTF file — no explicit range hints are needed or supported.
    Consolas is designed for screen rendering at small sizes and ships with
    Windows. It covers the Unicode symbols used in block model descriptions
    (±, ², ½, µ, ·, ×, −, ≤, ≥, ≈, →, √, —, λ, π, τ, Ω).
    Subscript digits (₀–₉) are not in common system fonts; use plain digits.
    """
    import dearpygui.dearpygui as dpg
    font_path = r"C:\Windows\Fonts\consola.ttf"
    if not os.path.exists(font_path):
        return   # fall back to DPG default if the font file is missing
    with dpg.font_registry():
        with dpg.font(font_path, 14) as courier:
            pass
    dpg.bind_font(courier)


def run_gui() -> None:
    import dearpygui.dearpygui as dpg
    from app import App

    dpg.create_context()
    _setup_font()
    dpg.create_viewport(
        title="ToyRadar / FMCW Radar Simulator",
        width=1400, height=900,
        min_width=900, min_height=600,
    )
    dpg.setup_dearpygui()

    app = App()
    app.build()

    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()


def validate_command(config_path: str) -> int:
    from config import load_configuration

    document, warnings = load_configuration(config_path, require_connected=True)
    for warning in warnings:
        print(f"WARNING: {warning}")
    design = document.get("design", {})
    print(
        f"Valid configuration: {design.get('name', 'Unnamed')} "
        f"{design.get('revision', '')} ({len(document['blocks'])} blocks, "
        f"{len(document['connections'])} connections, {len(document.get('scenarios', []))} scenarios)"
    )
    return 0


def calculate_command(config_path: str, json_output: str | None,
                      markdown_output: str | None) -> int:
    from config import load_configuration
    from reporting import calculate_document, write_markdown_report, write_results_json

    document, warnings = load_configuration(config_path, require_connected=True)
    results = calculate_document(document, warnings)
    json_destination = (
        Path(json_output)
        if json_output
        else default_report_path(config_path, ".results.json")
    )
    markdown_destination = (
        Path(markdown_output)
        if markdown_output
        else default_report_path(config_path, ".results.md")
    )
    write_results_json(results, json_destination)
    write_markdown_report(document, results, markdown_destination)
    print(f"Wrote {json_destination}")
    print(f"Wrote {markdown_destination}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ToyRadar FMCW simulator")
    subparsers = parser.add_subparsers(dest="command")

    validate_parser = subparsers.add_parser("validate", help="validate a .toyradar file")
    validate_parser.add_argument("configuration")

    calculate_parser = subparsers.add_parser(
        "calculate", help="run all scenarios and generate JSON and Markdown reports"
    )
    calculate_parser.add_argument("configuration")
    calculate_parser.add_argument("--json-output")
    calculate_parser.add_argument("--markdown-output")

    args = parser.parse_args(argv)
    if args.command == "validate":
        return validate_command(args.configuration)
    if args.command == "calculate":
        return calculate_command(
            args.configuration, args.json_output, args.markdown_output
        )
    run_gui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
