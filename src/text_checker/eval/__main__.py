import argparse
import sys
from collections import defaultdict
from pathlib import Path

import httpx

from .runner import DEFAULT_DATASET, call_service, load_dataset
from .scoring import edit_ratio_vs_expected, exact_match


def main() -> int:
    parser = argparse.ArgumentParser(prog="text_checker.eval")
    parser.add_argument("--service-url", default="http://localhost:8080")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    rows = load_dataset(args.dataset)
    print(f"Evaluating {len(rows)} rows against {args.service_url}")

    by_mode: dict[str, list[tuple[bool, float, bool]]] = defaultdict(list)
    errors = 0
    for row in rows:
        try:
            resp = call_service(
                args.service_url, row.input, row.mode, args.api_key, args.model
            )
        except httpx.HTTPError as e:
            print(f"  {row.id} ERROR: {e}")
            errors += 1
            continue
        predicted = resp["corrected_text"]
        em = exact_match(predicted, row.expected)
        er = edit_ratio_vs_expected(predicted, row.expected)
        flagged = bool(resp.get("flagged"))
        by_mode[row.mode].append((em, er, flagged))

    print()
    print(f"{'mode':<14} {'n':>3} {'exact':>7} {'avg_edit':>9} {'flagged':>8}")
    print("-" * 50)
    total_n = total_em = total_flag = 0
    total_er = 0.0
    for mode in sorted(by_mode):
        results = by_mode[mode]
        n = len(results)
        em_n = sum(1 for em, _, _ in results if em)
        avg_er = sum(er for _, er, _ in results) / n
        flag_n = sum(1 for _, _, f in results if f)
        print(f"{mode:<14} {n:>3} {em_n / n:>6.0%} {avg_er:>9.3f} {flag_n:>8}")
        total_n += n
        total_em += em_n
        total_er += sum(er for _, er, _ in results)
        total_flag += flag_n
    if total_n:
        print("-" * 50)
        print(
            f"{'overall':<14} {total_n:>3} {total_em / total_n:>6.0%} "
            f"{total_er / total_n:>9.3f} {total_flag:>8}"
        )
    if errors:
        print(f"\n{errors} row(s) errored — see above")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
