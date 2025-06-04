import pytest

from utils.prepare_instruments import align_to_step


@pytest.mark.parametrize(
    "value, step, round_down, expected",
    [
        # Integer step, round down
        (5.67, 1, True, 5),
        (5.00, 1, True, 5),
        (5.00, 1, False, 5),  # exact multiple
        # Integer step, round up
        (5.01, 1, False, 6),
        (6.99, 1, False, 7),
        # Float step = 0.1
        (5.67, 0.1, True, 5.6),
        (5.60, 0.1, True, 5.6),
        (5.60, 0.1, False, 5.6),  # exact multiple
        (5.61, 0.1, False, 5.7),
        # Float step = 0.001
        (123.4567, 0.001, True, 123.456),
        (123.4560, 0.001, True, 123.456),
        (123.4560, 0.001, False, 123.456),
        (123.4567, 0.001, False, 123.457),
        # Float step = 0.25
        (1.10, 0.25, True, 1.00),
        (1.00, 0.25, True, 1.00),
        (1.00, 0.25, False, 1.00),
        (1.10, 0.25, False, 1.25),
        # Large values
        (1000000.1234, 0.01, True, 1000000.12),
        (1000000.1200, 0.01, False, 1000000.12),
        (1000000.1299, 0.01, False, 1000000.13),
        # Step > value
        (0.5, 1.0, True, 0.0),
        (0.5, 1.0, False, 1.0),
    ],
)
def test_align_to_step(
    value,
    step,
    round_down,
    expected,
):
    result = align_to_step(
        value,
        step,
        round_down=round_down,
    )
    # Используем pytest.approx, для сравнения двух float, если нужна небольшая погрешность
    assert result == pytest.approx(expected, rel=1e-8)
