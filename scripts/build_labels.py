#!/usr/bin/env python3
"""Собирает labels_2024.csv: позитивы из СМИ/сводок + негативы (все остальные НП).

Методика и ограничения: docs/data/flood-labels-methodology.md.
Строки positives со source=ПРОВЕРИТЬ в разметку не попадают (пока не подтверждены).

Использование:
    python3 scripts/build_labels.py \
        data/raw/labels_positives.csv data/raw/settlements_kz-sev.csv data/raw/labels_2024.csv
"""
import csv
import sys


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    positives_csv, settlements_csv, output_csv = sys.argv[1:4]

    with open(positives_csv, encoding="utf-8") as f:
        positives_rows = list(csv.DictReader(f))
    confirmed = {r["name"].strip() for r in positives_rows if r["source"].strip() != "ПРОВЕРИТЬ"}
    pending = {r["name"].strip() for r in positives_rows if r["source"].strip() == "ПРОВЕРИТЬ"}

    with open(settlements_csv, encoding="utf-8") as f:
        settlement_names = [row["name"] for row in csv.DictReader(f)]
    known = set(settlement_names)

    unmatched = sorted(confirmed - known)
    if unmatched:
        print("ВНИМАНИЕ — позитивы без совпадения в списке НП (проверьте написание):")
        for name in unmatched:
            print(f"  - {name}")

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "flooded"])
        seen = set()
        rows_written = 0
        for name in settlement_names:
            if name in seen:
                continue  # тёзки получают одну строку — train.py мёржит по имени
            seen.add(name)
            if name in pending:
                continue  # неподтверждённые исключаем и из 0, и из 1
            writer.writerow([name, 1 if name in confirmed else 0])
            rows_written += 1

    matched = len(confirmed & known)
    print(f"Позитивов: {matched} сматчено / {len(confirmed)} подтверждённых "
          f"(+{len(pending)} ждут проверки); всего строк: {rows_written} → {output_csv}")


if __name__ == "__main__":
    main()
