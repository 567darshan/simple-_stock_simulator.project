# fix_portfolios.py
# Safe script to remove BOM from portfolio JSON files and ensure initial_cash exists.
# Usage: python fix_portfolios.py

import pathlib, json, shutil
DATA_DIR = pathlib.Path(r"C:\simple_stock_simulator.project\data")

files = sorted(DATA_DIR.glob("portfolio_*.json"))
print(f"Found {len(files)} portfolio files in {DATA_DIR}")

for p in files:
    try:
        # backup first
        bak = p.with_suffix(p.suffix + ".bak")
        shutil.copy2(p, bak)
        print(f"  backed up {p.name} -> {bak.name}")

        # read with utf-8-sig (handles BOM)
        s = p.read_text(encoding="utf-8-sig")
        data = json.loads(s) if s.strip() else {}

        # ensure initial_cash exists and is numeric
        if "initial_cash" not in data or not isinstance(data.get("initial_cash"), (int, float)):
            data["initial_cash"] = 10000.0

        # write back as utf-8 without BOM
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  rewrote {p.name} (initial_cash={data['initial_cash']})")
    except Exception as e:
        print(f"  failed {p.name}: {e}")

print("Done.")
