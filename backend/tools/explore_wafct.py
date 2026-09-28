from __future__ import annotations

import sys
from pathlib import Path

import openpyxl


WORKBOOK = Path(__file__).parents[1] / "data" / "reference" / "WAFCT_2019.xlsx"
SHEET = "05 NV_sum_57 (per 100g EP)"


def main(keywords: list[str]) -> None:
    workbook = openpyxl.load_workbook(WORKBOOK, read_only=True, data_only=True)
    worksheet = workbook[SHEET]
    rows = [
        row
        for row in worksheet.iter_rows(min_row=5, values_only=True)
        if isinstance(row[0], str) and "_" in row[0] and row[1]
    ]

    for keyword in keywords:
        matches = [
            (row[0], row[1])
            for row in rows
            if keyword.casefold() in str(row[1]).casefold()
        ]
        print(f"\n### {keyword} ({len(matches)})")
        for code, name in matches[:40]:
            print(f"{code} | {name}")


if __name__ == "__main__":
    main(sys.argv[1:])
