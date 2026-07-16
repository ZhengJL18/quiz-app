"""SM-2 spaced repetition algorithm implementation."""

from typing import TypedDict


class SM2Result(TypedDict):
    interval_days: float
    ease_factor: float
    review_count: int


def sm2_calculate(
    quality: int,
    interval_days: float,
    ease_factor: float,
    review_count: int,
) -> SM2Result:
    """Compute the next SM-2 scheduling parameters.

    Args:
        quality:       User recall quality 0-5 (0=complete forget, 5=perfect)
        interval_days: Current interval in days
        ease_factor:   Current ease factor (default 2.5)
        review_count:  Number of times the card has been reviewed

    Returns:
        dict with updated interval_days, ease_factor, review_count
    """
    quality = max(0, min(5, quality))

    if quality < 3:
        # Failed recall — reset interval, decrease ease factor
        interval = 1.0
        ease_factor = max(ease_factor - 0.2, 1.3)
    else:
        # Successful recall
        if review_count == 0:
            interval = 1.0
        elif review_count == 1:
            interval = 6.0
        else:
            interval = interval_days * ease_factor

        ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        ease_factor = max(ease_factor, 1.3)

    review_count += 1

    return {
        "interval_days": round(interval, 2),
        "ease_factor": round(ease_factor, 2),
        "review_count": review_count,
    }
