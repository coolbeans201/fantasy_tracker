"""One-off: copy NFL pages into app/pages/nfl/ and patch sport scope."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app" / "pages"
DST = SRC / "nfl"

patches = {
    "2_Player_Profile.py": [
        ('"""Player Profile page', '"""NFL Player Profile page'),
        ("from app.components import (\n", "from app.sport_context import init_sport_page\nfrom app.components import (\n"),
        ('st.set_page_config(page_title=page_title_suffix("Player Profile"), layout="wide")\n\n_query_season',
         'st.set_page_config(page_title=page_title_suffix("NFL Player Profile"), layout="wide")\ninit_sport_page("nfl")\n\n_query_season'),
        ("controls = render_sidebar(\n", 'controls = render_sidebar(\n    sport="nfl",\n'),
    ],
    "3_Compare.py": [
        ('"""Compare Players page."""', '"""NFL Compare Players page."""'),
        ("from app.components import fuzzy_player_select", "from app.sport_context import init_sport_page\nfrom app.components import fuzzy_player_select"),
        ('st.set_page_config(page_title=page_title_suffix("Compare Players"), layout="wide")\n\ncontrols = render_sidebar()',
         'st.set_page_config(page_title=page_title_suffix("NFL Compare Players"), layout="wide")\ninit_sport_page("nfl")\n\ncontrols = render_sidebar(sport="nfl")'),
    ],
}

DST.mkdir(parents=True, exist_ok=True)
for name, reps in patches.items():
    text = (SRC / name).read_text(encoding="utf-8")
    for old, new in reps:
        text = text.replace(old, new, 1)
    (DST / name).write_text(text, encoding="utf-8")
    print("wrote", DST / name)
