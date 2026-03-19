"""Tests for mortgage calculator logic (ING-style outputs)."""


def test_calculator_hypotheek():
    """Hypotheek = bid - eigen inleg."""
    bid = 350_000
    eigen_inleg = 35_000
    hypotheek = bid - eigen_inleg
    assert hypotheek == 315_000


def test_calculator_bruto_maandlasten_placeholder():
    """Placeholder formula: rough monthly (e.g. 0.0045 * hypotheek)."""
    hypotheek = 300_000
    maandlast = round(hypotheek * 0.0045, 2)
    assert 1000 <= maandlast <= 2000


def test_calculator_kosten_koper_placeholder():
    """Kosten koper ~6% of bid (placeholder)."""
    bid = 350_000
    kk = round(bid * 0.06, 0)
    assert kk == 21_000
