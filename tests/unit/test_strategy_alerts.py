"""Unit tests for the GĐ 6 grade-change alerts (pure parts)."""

from __future__ import annotations

from datetime import date

from src.quant.strategy.alerts import GradeChange, build_change_email


def _change(
    symbol: str,
    old: str | None,
    new: str | None,
    *,
    strategy: str = "mid",
    score: float | None = 72.5,
) -> GradeChange:
    return GradeChange(
        symbol=symbol,
        strategy=strategy,
        previous_grade=old,
        new_grade=new,
        previous_date=date(2026, 10, 2),
        new_date=date(2026, 10, 3),
        overall_score=score,
    )


class TestGradeChange:
    def test_direction_up(self) -> None:
        assert _change("FPT", "C", "B").direction == "UP"

    def test_direction_down(self) -> None:
        assert _change("FPT", "B", "D").direction == "DOWN"

    def test_direction_new_when_either_side_missing(self) -> None:
        assert _change("FPT", None, "B").direction == "NEW"
        assert _change("FPT", "C", None).direction == "NEW"

    def test_subject_reads_as_a_sentence(self) -> None:
        assert _change("FPT", "C", "B").subject() == "FPT (mid): C → B (UP)"


class TestBuildChangeEmail:
    def test_lists_every_change_with_disclaimer(self) -> None:
        html = build_change_email(
            [_change("FPT", "C", "B"), _change("HPG", "B", "A", strategy="long", score=88.0)]
        )
        assert "FPT" in html
        assert "HPG" in html
        assert "long" in html
        assert "Số mã đổi grade: <b>2</b>" in html
        assert "tham khảo" in html  # §3 disclaimer always present

    def test_empty_changes_render_an_honest_table(self) -> None:
        html = build_change_email([], as_of=date(2026, 10, 3))
        assert "Không có thay đổi grade" in html
        assert "2026-10-03" in html

    def test_none_score_renders_blank_not_zero(self) -> None:
        html = build_change_email([_change("FPT", "C", "B", score=None)])
        assert ">0.0<" not in html

    def test_symbol_text_is_escaped(self) -> None:
        """A symbol is vendor data — never trusted as raw HTML."""
        html = build_change_email([_change("A<script>", "C", "B")])
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_no_changes_means_no_alert_line(self) -> None:
        assert build_change_email([], as_of=date(2026, 10, 3)).count("<tr>") >= 2
