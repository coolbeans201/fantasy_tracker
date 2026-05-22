"""Best week from weekly fantasy points (uses sidebar scoring preset)."""

from __future__ import annotations

import pandas as pd

from src.scoring.calc import DISPLAY_PRESETS, resolve_preset


def best_week_by_season(weekly_df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per season: best week number and FP from weekly ``fantasy_points``.

    Expects ``entity_weekly`` / ``entity_all_weekly`` output (FP already preset-scoped).
    """
    if weekly_df.empty or "season" not in weekly_df.columns:
        return pd.DataFrame(columns=["season", "best_week", "best_week_fp"])

    fp_col = "fantasy_points"
    if fp_col not in weekly_df.columns:
        return pd.DataFrame(columns=["season", "best_week", "best_week_fp"])

    rows: list[dict] = []
    for season, grp in weekly_df.groupby("season"):
        fp = pd.to_numeric(grp[fp_col], errors="coerce")
        if fp.isna().all():
            continue
        idx = fp.idxmax()
        if pd.isna(idx):
            continue
        row = grp.loc[idx]
        rows.append(
            {
                "season": int(season),
                "best_week": int(row["week"]),
                "best_week_fp": float(row[fp_col]),
            }
        )
    return pd.DataFrame(rows)


def preset_best_week_label(preset_display: str, *, dst: bool = False, kicker: bool = False) -> str:
    if dst:
        return "ESPN D/ST"
    if kicker:
        return "ESPN Kicker"
    key = resolve_preset(preset_display)
    for label, k in DISPLAY_PRESETS.items():
        if k == key:
            return label
    return preset_display


def overlay_preset_best_week(
    seasons_df: pd.DataFrame,
    weekly_df: pd.DataFrame,
    preset_display: str,
    *,
    dst: bool = False,
) -> pd.DataFrame:
    """Replace ingest-time best_week columns with preset-aligned weekly peaks."""
    out = seasons_df.copy()
    best = best_week_by_season(weekly_df)
    if best.empty:
        return out

    out = out.drop(columns=["best_week", "best_week_fp", "best_week_scoring"], errors="ignore")
    out = out.merge(best, on="season", how="left")

    def _scoring_key(row: pd.Series) -> str:
        if dst:
            return "dst"
        pos = str(row.get("position", "")).upper()
        if pos == "K":
            return "kicker"
        return resolve_preset(preset_display)

    if not out.empty:
        out["best_week_scoring"] = out.apply(_scoring_key, axis=1)
    return out
