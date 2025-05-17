from decimal import Decimal


def align_to_step(
    value: float,
    step: float,
    *,
    round_down: bool = True,
) -> float:
    """Приводим value к шагу step.  round_down=True → в меньшую сторону."""
    d_val = Decimal(str(value))
    d_step = Decimal(str(step))
    if round_down:
        return float((d_val // d_step) * d_step)
    # округление вверх (Buy=False → Sell)
    return float(((d_val + d_step - Decimal("1e-12")) // d_step) * d_step)
