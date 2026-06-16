#!/usr/bin/env python3
"""Export test result logs to CSV for Excel analysis."""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from tkinter import Tk, filedialog, messagebox

LOG_DIR = Path("tests/logs")


def parse_jsonl(file_path: Path) -> list[dict]:
    """Parse JSONL file and return list of entries."""
    entries = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def flatten_for_csv(entry: dict) -> dict:
    """Extract key fields for CSV export."""
    return {
        "timestamp": entry.get("timestamp", ""),
        "run_id": entry.get("run_id", ""),
        "case": entry.get("case", ""),
        "model": entry.get("model", ""),
        "use_few_shot": entry.get("use_few_shot", ""),
        "source_mode": entry.get("source_mode", ""),
        "page_finder_strategy": entry.get("page_finder_strategy", ""),
        "page_selection_method": entry.get("page_selection_method", ""),
        "selected_pages": ",".join(str(p) for p in entry.get("selected_pages", []) or []),
        "passed": entry.get("passed", ""),
        "pdf_extraction_ms": entry.get("pdf_extraction_ms", ""),
        "duration_ms": entry.get("duration_ms", ""),
        "few_shot_setup_ms": entry.get("few_shot_setup_ms", ""),
        "total_duration_ms": entry.get("total_duration_ms", ""),
        "input_tokens": entry.get("input_tokens", ""),
        "output_tokens": entry.get("output_tokens", ""),
        "error": entry.get("error", ""),
    }


def select_logs_gui() -> list[Path]:
    """File picker to select JSONL log files."""
    root = Tk()
    root.withdraw()

    if not LOG_DIR.exists():
        messagebox.showerror("Error", f"Log directory not found: {LOG_DIR}")
        return []

    selected = filedialog.askopenfilenames(
        title="Select test result logs to export",
        initialdir=LOG_DIR,
        filetypes=[
            ("Test logs", "*.jsonl"),
            ("Results logs", "*_results.jsonl"),
            ("Failures logs", "*_failures.jsonl"),
            ("All files", "*")
        ],
    )

    root.destroy()
    return [Path(f) for f in selected]


def main():
    """Export selected logs to CSV."""
    print("Test Results Export Tool\n")

    # Select log files
    selected_logs = select_logs_gui()

    if not selected_logs:
        print("No files selected.")
        return 1

    print(f"Selected {len(selected_logs)} file(s)")

    # Parse entries
    all_entries = []
    for log_file in selected_logs:
        entries = parse_jsonl(log_file)
        all_entries.extend(entries)
        print(f"  ✓ {len(entries)} entries from {log_file.name}")

    if not all_entries:
        print("No entries found.")
        return 1

    print(f"\nTotal: {len(all_entries)} test results")

    # Select output location
    root = Tk()
    root.withdraw()

    output_dir = filedialog.askdirectory(
        title="Save CSV file to...",
        initialdir=Path.cwd(),
    )
    root.destroy()

    if not output_dir:
        print("Cancelled.")
        return 1

    # Export to CSV
    output_path = Path(output_dir) / f"test_results_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"

    flattened = [flatten_for_csv(e) for e in all_entries]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=flattened[0].keys())
        writer.writeheader()
        writer.writerows(flattened)

    print(f"\n✓ Exported to: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
