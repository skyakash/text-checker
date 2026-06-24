import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

DEFAULT_DATASET = Path("tests/eval/data/golden.jsonl")


@dataclass
class EvalRow:
    id: str
    mode: str
    input: str
    expected: str


def load_dataset(path: Path) -> list[EvalRow]:
    rows: list[EvalRow] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            rows.append(EvalRow(id=obj["id"], mode=obj["mode"], input=obj["input"], expected=obj["expected"]))
    return rows


def call_service(
    service_url: str,
    text: str,
    mode: str,
    api_key: str | None = None,
    model: str | None = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    headers = {"content-type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    payload: dict[str, Any] = {"text": text, "mode": mode}
    if model:
        payload["model"] = model
    r = httpx.post(
        f"{service_url.rstrip('/')}/v1/correct",
        json=payload,
        headers=headers,
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()
