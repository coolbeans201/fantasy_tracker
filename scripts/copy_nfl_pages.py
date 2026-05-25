import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
src = root / "app" / "pages"
dst = src / "nfl"
dst.mkdir(parents=True, exist_ok=True)
for name in ("2_Player_Profile.py", "3_Compare.py"):
    shutil.copy2(src / name, dst / name)
    print("copied", name)
