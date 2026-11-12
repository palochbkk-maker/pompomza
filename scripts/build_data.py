#!/usr/bin/env python3
"""Download map.sql for each server in config/servers.json and write data/<server>.json.
Local test:  python scripts/build_data.py --file map.sql --server ts21.x2.asia.travian.com
"""
import argparse, json, re, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROW = re.compile(r"INSERT INTO `x_world` VALUES \((.*)\);\s*$")
TOKEN = re.compile(r"""\s*(?:'((?:[^'\\]|\\.|'')*)'|"((?:[^"\\]|\\.)*)"|([^,]+?))\s*(?:,|$)""")

def unq(s):
    return s.replace("\\'", "'").replace("''", "'").replace('\\\\', '\\')

def parse_row(body):
    out = []
    pos = 0
    while pos < len(body):
        m = TOKEN.match(body, pos)
        if not m or m.end() == pos:
            break
        if m.group(1) is not None: out.append(unq(m.group(1)))
        elif m.group(2) is not None: out.append(m.group(2))
        else: out.append(m.group(3).strip())
        pos = m.end()
    return out

def convert(text, server):
    players, alliances, villages = {}, {}, []
    for line in text.splitlines():
        m = ROW.match(line.strip())
        if not m: continue
        f = parse_row(m.group(1))
        if len(f) < 11: continue
        _id, x, y, tribe, vid, vname, uid, pname, aid, atag, pop = f[:11]
        capital = len(f) > 12 and f[12].upper() == "TRUE"
        uid, aid = int(uid), int(aid)
        if int(tribe) == 5 or uid == 1:      # Natars
            continue
        players[uid] = [uid, pname, aid, int(tribe)]
        if aid: alliances[aid] = atag
        villages.append([vname, uid, int(x), int(y), int(pop), 1 if capital else 0])
    return {
        "server": server,
        "updated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "alliances": {str(k): v for k, v in sorted(alliances.items())},
        "players": sorted(players.values(), key=lambda p: p[1].lower()),
        "villages": villages,
    }

def download(server):
    req = urllib.request.Request(f"https://{server}/map.sql", headers={"User-Agent": "artifact-planner/1.0 (daily snapshot)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode("utf-8", "replace")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file"); ap.add_argument("--server")
    a = ap.parse_args()
    (ROOT / "data").mkdir(exist_ok=True)
    if a.file:
        servers = [a.server or "local"]
        texts = {servers[0]: Path(a.file).read_text(encoding="utf-8", errors="replace")}
    else:
        servers = [s["id"] for s in json.loads((ROOT / "config/servers.json").read_text())]
        texts = {}
    failed = 0
    for s in servers:
        try:
            text = texts.get(s) or download(s)
            data = convert(text, s)
            if not data["villages"]: raise ValueError("no villages parsed")
            (ROOT / "data" / f"{s}.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            print(f"{s}: {len(data['villages'])} villages, {len(data['players'])} players")
        except Exception as e:      # keep yesterday's file if today's download fails
            failed += 1; print(f"{s}: FAILED ({e})", file=sys.stderr)
        time.sleep(2)
    sys.exit(1 if failed == len(servers) else 0)

if __name__ == "__main__":
    main()
