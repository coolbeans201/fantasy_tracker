from app.sport_compare_page import render_sport_compare_page

render_sport_compare_page(
    "mlb",
    label="MLB",
    caption="Compare **hitters to hitters** or **pitchers to pitchers** only. "
    "Two-way players (e.g. Ohtani) show **hitting or pitching** stats for the cohort you pick—not both.",
    use_search_pickers=True,
)
