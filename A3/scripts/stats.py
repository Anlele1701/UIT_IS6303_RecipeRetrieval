"""Small statistics helpers for A3 reports (A1's significance.py covers paired bootstrap)."""

import math

Z95 = 1.959963984540054


def wilson(successes: int, n: int, z: float = Z95) -> tuple[float, float] | None:
    """Wilson score interval for a proportion; None when n is 0."""
    if n == 0:
        return None
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def rate(successes: int, n: int) -> dict:
    """A proportion with its Wilson 95% interval, as stored in report JSON."""
    ci = wilson(successes, n)
    return {"k": successes, "n": n, "value": round(successes / n, 4) if n else None,
            "ci95": [round(ci[0], 4), round(ci[1], 4)] if ci else None}
