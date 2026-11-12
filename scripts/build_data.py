#!/usr/bin/env python3
"""Download map.sql for each server in config/servers.json and write data/<server>.json.
Local test:  python scripts/build_data.py --file map.sql --server ts21.x2.asia.travian.com
"""
import argparse, json, re, sys, time, urllib.error, urllib.request
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

def clean_id(s):
    """Accept 'https://ts5.x1.europe.travian.com/map.sql' or 'ts5.x1.europe.travian.com/' too."""
    s = re.sub(r"^https?://", "", str(s).strip())
    return s.split("/")[0].strip()

def download(server):
    req = urllib.request.Request(f"https://{server}/map.sql", headers={"User-Agent": "artifact-planner/1.0 (daily snapshot)"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} from https://{server}/map.sql - check the server address")
    except Exception as e:
        raise RuntimeError(f"could not download https://{server}/map.sql ({e})")

def load_servers():
    p = ROOT / "config/servers.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"::error::config/servers.json is not valid JSON (line {e.lineno}, column {e.colno}): {e.msg}. Usually a missing or extra comma.")
    if not isinstance(data, list):
        sys.exit("::error::config/servers.json must be a list like [{\"id\":\"ts21.x2.asia.travian.com\",\"label\":\"Asia 21\"}]")
    ids = []
    for s in data:
        sid = clean_id(s.get("id", "") if isinstance(s, dict) else s)
        if sid and sid not in ids: ids.append(sid)
    if not ids:
        sys.exit("::error::config/servers.json has no servers")
    return ids

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file"); ap.add_argument("--server")
    a = ap.parse_args()
    (ROOT / "data").mkdir(exist_ok=True)
    texts = {}
    if a.file:
        servers = [clean_id(a.server or "local")]
        texts[servers[0]] = Path(a.file).read_text(encoding="utf-8", errors="replace")
    else:
        servers = load_servers()
    failed = []
    for s in servers:
        try:
            text = texts.get(s) or download(s)
            data = convert(text, s)
            if not data["villages"]: raise RuntimeError("the file was downloaded but no villages were found in it")
            (ROOT / "data" / f"{s}.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            print(f"{s}: OK - {len(data['villages'])} villages, {len(data['players'])} players")
        except Exception as e:      # keep the previous file for this server
            failed.append(s); print(f"::warning::{s}: FAILED - {e}")
        time.sleep(2)
    if failed and len(failed) == len(servers):
        sys.exit("::error::Every server failed. See the warnings above.")
    print(f"Done: {len(servers)-len(failed)} of {len(servers)} servers updated.")

if __name__ == "__main__":
    main()
