import difflib


def exact_match(predicted: str, expected: str) -> bool:
    return predicted.strip() == expected.strip()


def edit_ratio_vs_expected(predicted: str, expected: str) -> float:
    return 1.0 - difflib.SequenceMatcher(None, predicted, expected).ratio()
