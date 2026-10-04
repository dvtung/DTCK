"""Unit tests for the multi-strategy scoring module (GĐ 1).

Covers: config loading/validation (YAML ↔ code sync, anti-drift), profile
score aggregation (renormalization + Σcontribution == 1), grade rules with
trend confirmation, red-flag evaluation against configured thresholds, and
the persistence contract (new tables + ``published_at`` on the model).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.quant.strategy import (
    DISCLAIMER,
    GROUPS,
    PROFILES,
    StrategyConfigError,
    evaluate_redflags,
    load_redflag_thresholds,
    load_strategy_config,
    score_profile,
    weights_for,
)
from src.quant.strategy.recommend import build_recommendation
from src.quant.strategy.redflags import RedFlagInputs
from src.quant.strategy.scoring import ProfileScore

CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "strategy_weights.yaml"
RED_FLAG_PATH = Path(__file__).resolve().parents[2] / "configs" / "redflag_thresholds.yaml"


class TestConfig:
    def test_weights_match_yaml_file(self) -> None:
        """``configs/strategy_weights.yaml`` must stay in sync with the loader."""
        cfg = load_strategy_config(str(CONFIG_PATH))
        assert cfg.version == "strategy_v1.0"
        assert set(cfg.profiles) == set(PROFILES)
        for profile in PROFILES:
            assert set(cfg.profiles[profile]) == set(GROUPS)

    @pytest.mark.parametrize("profile", PROFILES)
    def test_profile_weights_sum_to_one(self, profile: str) -> None:
        cfg = load_strategy_config(str(CONFIG_PATH))
        assert abs(sum(cfg.profiles[profile].values()) - 1.0) < 1e-9

    def test_short_profile_baseline_weights(self) -> None:
        """The agreed short-term baseline (40/25/10/5/5/15/0) must not drift."""
        w = weights_for("short", load_strategy_config(str(CONFIG_PATH)))
        assert w["technical"] == pytest.approx(0.40)
        assert w["moneyflow"] == pytest.approx(0.25)
        assert w["macro"] == pytest.approx(0.15)
        assert w["governance"] == 0.0

    def test_unknown_profile_raises(self) -> None:
        with pytest.raises(KeyError):
            weights_for("swing", load_strategy_config(str(CONFIG_PATH)))

    def test_invalid_weights_rejected(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "version: x\nprofiles:\n"
            + "".join(f"  {p}:\n    technical: 0.9\n    growth: 0.9\n" for p in PROFILES)
            + "grades:\n  A: 80\n  B: 65\n  C: 50\n",
            encoding="utf-8",
        )
        with pytest.raises(StrategyConfigError):
            load_strategy_config.__wrapped__(str(bad))  # type: ignore[attr-defined]


class TestScoring:
    def test_full_coverage_weighted_average(self) -> None:
        cfg = load_strategy_config(str(CONFIG_PATH))
        groups = {g: 80.0 for g in GROUPS}
        result = score_profile(groups, "mid", weights=cfg.profiles["mid"])
        assert result.overall_score == pytest.approx(80.0)
        assert result.confidence > 0.5
        assert not result.missing_groups

    def test_missing_group_renormalizes_and_keeps_sum(self) -> None:
        """A missing group must not zero the score; weights renormalize."""
        cfg = load_strategy_config(str(CONFIG_PATH))
        groups = {"technical": 60.0, "growth": None, "quality": 90.0}
        result = score_profile(groups, "long", weights=cfg.profiles["long"])
        assert result.overall_score is not None
        # Σ weighted == overall and Σ share == 1 (documented §12 contract).
        total = sum(c.weighted_score for c in result.contributions)
        assert total == pytest.approx(result.overall_score, abs=1e-9)
        share = sum(c.contribution_pct or 0.0 for c in result.contributions)
        assert share == pytest.approx(1.0, abs=1e-9)
        assert "growth" in result.missing_groups

    def test_zero_weight_group_is_neither_scored_nor_missing(self) -> None:
        """governance has weight 0 in short/mid → excluded from both sides."""
        cfg = load_strategy_config(str(CONFIG_PATH))
        groups = {"governance": 100.0, "technical": 50.0}
        result = score_profile(groups, "short", weights=cfg.profiles["short"])
        assert "governance" not in [c.group for c in result.contributions]
        assert "governance" not in result.missing_groups

    def test_all_missing_yields_none_not_zero(self) -> None:
        cfg = load_strategy_config(str(CONFIG_PATH))
        result = score_profile({g: None for g in GROUPS}, "mid", weights=cfg.profiles["mid"])
        assert result.overall_score is None
        assert result.confidence == 0.0

    def test_unknown_group_key_rejected(self) -> None:
        with pytest.raises(KeyError):
            score_profile({"bogus": 50.0}, "mid")


class TestRecommendation:
    def _score(self, profile: str, value: float) -> ProfileScore:
        cfg = load_strategy_config(str(CONFIG_PATH))
        return score_profile({g: value for g in GROUPS}, profile, weights=cfg.profiles[profile])

    def test_grade_thresholds(self) -> None:
        assert build_recommendation(self._score("mid", 85.0)).grade == "A"
        assert build_recommendation(self._score("mid", 70.0)).grade == "B"
        assert build_recommendation(self._score("mid", 55.0)).grade == "C"
        assert build_recommendation(self._score("mid", 40.0)).grade == "D"

    def test_short_requires_trend_confirmation(self) -> None:
        score = self._score("short", 90.0)
        assert build_recommendation(score).grade == "C"  # no trend evidence → capped
        assert build_recommendation(score, trend_confirmed=None).grade == "C"
        assert build_recommendation(score, trend_confirmed=True).grade == "A"

    def test_long_profile_never_needs_trend(self) -> None:
        assert build_recommendation(self._score("long", 90.0)).grade == "A"

    def test_none_score_yields_no_grade(self) -> None:
        cfg = load_strategy_config(str(CONFIG_PATH))
        result = score_profile({g: None for g in GROUPS}, "mid", weights=cfg.profiles["mid"])
        rec = build_recommendation(result)
        assert rec.grade is None
        assert rec.risks

    def test_explanation_and_disclaimer_present(self) -> None:
        rec = build_recommendation(self._score("mid", 75.0))
        assert rec.reasons  # top contributing groups explained
        assert rec.disclaimer == DISCLAIMER
        payload = rec.as_dict()
        assert set(payload) == {
            "profile",
            "grade",
            "overall_score",
            "confidence",
            "reasons",
            "risks",
            "disclaimer",
        }


class TestRedFlags:
    def test_thresholds_load(self) -> None:
        t = load_redflag_thresholds(str(RED_FLAG_PATH))
        assert t.version == "redflag_v1.0"
        assert t.min_avg_value_20d_vnd == 1_000_000_000
        assert t.industry_debt_to_equity["banking"] is None

    def test_low_liquidity_flagged(self) -> None:
        t = load_redflag_thresholds(str(RED_FLAG_PATH))
        result = evaluate_redflags(RedFlagInputs(avg_value_20d_vnd=100.0), t)
        assert [f.code for f in result.flags] == ["low_liquidity"]
        assert result.flags[0].threshold == t.min_avg_value_20d_vnd

    def test_healthy_stock_no_flags(self) -> None:
        t = load_redflag_thresholds(str(RED_FLAG_PATH))
        result = evaluate_redflags(
            RedFlagInputs(
                avg_value_20d_vnd=50_000_000_000.0,
                consecutive_loss_years=0,
                operating_cash_flow_negative=False,
                debt_to_equity=1.0,
                trading_status="NORMAL",
                audit_opinion="UNQUALIFIED",
            ),
            t,
        )
        assert result.flags == ()
        assert result.unchecked == ()

    def test_none_inputs_reported_not_flagged(self) -> None:
        """No data → no flag; the caller is told what could not be checked."""
        result = evaluate_redflags(RedFlagInputs())
        assert result.flags == ()
        assert "avg_value_20d_vnd" in result.unchecked
        assert "audit_opinion" in result.unchecked

    def test_industry_override_exempt_banking(self) -> None:
        t = load_redflag_thresholds(str(RED_FLAG_PATH))
        result = evaluate_redflags(RedFlagInputs(debt_to_equity=50.0, industry="banking"), t)
        assert [f.code for f in result.flags] == []
        assert "debt_to_equity" not in result.unchecked  # exemption, not missing data

    def test_high_leverage_flagged_for_general_industry(self) -> None:
        t = load_redflag_thresholds(str(RED_FLAG_PATH))
        result = evaluate_redflags(RedFlagInputs(debt_to_equity=3.0), t)
        assert [f.code for f in result.flags] == ["high_leverage"]

    def test_trading_and_audit_statuses_flagged(self) -> None:
        result = evaluate_redflags(
            RedFlagInputs(trading_status="CONTROL", audit_opinion="QUALIFIED")
        )
        codes = [f.code for f in result.flags]
        assert "trading_control" in codes
        assert "audit_qualified" in codes

    def test_loss_negative_ocf_requires_both(self) -> None:
        t = load_redflag_thresholds(str(RED_FLAG_PATH))
        losses_only = evaluate_redflags(
            RedFlagInputs(consecutive_loss_years=3, operating_cash_flow_negative=False), t
        )
        assert [f.code for f in losses_only.flags] == []
        both = evaluate_redflags(
            RedFlagInputs(consecutive_loss_years=3, operating_cash_flow_negative=True), t
        )
        assert [f.code for f in both.flags] == ["loss_negative_ocf"]


class TestPersistenceContract:
    def test_new_tables_registered_on_metadata(self) -> None:
        from src.common.models import Base

        assert "strategy_scores" in Base.metadata.tables
        assert "strategy_recommendations" in Base.metadata.tables

    def test_strategy_scores_partition_column_in_pk(self) -> None:
        """TimescaleDB requires trade_date in every unique index/PK."""
        from src.common.models import Base

        pk = {c.name for c in Base.metadata.tables["strategy_scores"].primary_key.columns}
        assert {"stock_id", "trade_date", "strategy"} <= pk

    def test_group_columns_match_config_groups(self) -> None:
        """Every score group must have a persistence column and vice versa."""
        from src.common.models import Base
        from src.quant.strategy.groups import GROUP_COLUMNS

        cols = Base.metadata.tables["strategy_scores"].columns
        for group, column in GROUP_COLUMNS.items():
            assert group in GROUPS
            assert column in cols, f"{column} missing from strategy_scores"
        for group in GROUPS:
            assert GROUP_COLUMNS[group] in cols

    def test_financial_statements_has_published_at(self) -> None:
        from src.common.models import Base

        cols = Base.metadata.tables["financial_statements"].columns
        assert "published_at" in cols
        assert cols["published_at"].nullable

    def test_migration_revision_chain(self) -> None:
        import importlib.util
        import types

        path = (
            Path(__file__).resolve().parents[2]
            / "database"
            / "migrations"
            / "versions"
            / "0005_strategy_scoring.py"
        )
        spec = importlib.util.spec_from_file_location("dtck_m0005", path)
        assert spec is not None and spec.loader is not None
        module = types.ModuleType(spec.name)
        spec.loader.exec_module(module)
        assert module.revision == "0005_strategy_scoring"
        assert module.down_revision == "0004_email_schedule_noon"
        assert set(module.HYPERTABLES) == {"strategy_scores"}
