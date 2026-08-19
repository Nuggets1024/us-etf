#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""刷新 index.html 内嵌快照 EMBEDDED_DATA（需先起 serve.py）
用法: python refresh_embedded.py [代理端口]   默认 8937
"""
import json
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8937
PROXY = f"http://127.0.0.1:{PORT}"
HTML = Path(__file__).resolve().parent / "index.html"


def get(url):
    with urllib.request.urlopen(url, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    html = HTML.read_text(encoding="utf-8")
    m = re.search(r"const EMBEDDED_DATA = (\[.*?\]);", html, re.S)
    if not m:
        print("EMBEDDED_DATA not found", flush=True)
        sys.exit(1)
    data = json.loads(m.group(1))

    secids = ",".join(f'{e["market"]}.{e["code"]}' for e in data)
    fields = "f2,f3,f6,f12,f14,f15,f16,f17,f18,f24"
    q = get(f"{PROXY}/api/quote?secids={secids}&fields={fields}")
    diff = {d["f12"]: d for d in (q.get("data") or {}).get("diff") or []}
    print("quote diff:", len(diff), "/", len(data), flush=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for i, e in enumerate(data):
        d = diff.get(e["code"])
        if d:
            for fld, key in (("f2", "latestPrice"), ("f3", "changePct"),
                             ("f6", "todayTurnover"), ("f15", "high"),
                             ("f16", "low"), ("f18", "prevClose")):
                v = d.get(fld)
                if v not in (None, "-"):
                    e[key] = round(v / 1e8, 2) if fld == "f6" else v
        try:
            nv = get(f"{PROXY}/api/nav?fundCode={e['code']}&pageIndex=1&pageSize=1")
            ls = (nv.get("Data") or {}).get("LSJZList") or []
            if ls:
                e["navLatest"] = float(ls[0]["DWJZ"])
                e["navLatestDate"] = ls[0]["FSRQ"]
        except Exception as ex:  # noqa: BLE001
            print(f"navLatest fail {e['code']}: {ex}", flush=True)
        off = d.get("f24") if d else None
        if off not in (None, "-", 0, "0"):
            e["iopvPrem"] = float(off)
        else:
            e.pop("iopvPrem", None)
        # 溢价 = 实时价 vs 页面快照净值（与参考站口径一致，净值不随行情更新）
        if e.get("nav") and e.get("latestPrice"):
            e["premium"] = round((e["latestPrice"] - e["nav"]) / e["nav"] * 10000) / 100
        if e.get("nav") and e.get("latestPrice") and e.get("size"):
            e["marketValue"] = round(e["size"] * e["latestPrice"] / e["nav"], 2)
        e["updateTime"] = now
        if i % 4 == 0:
            print(f"  {i+1}/{len(data)} {e['code']} price={e.get('latestPrice')} nav={e.get('nav')} prem={e.get('premium')}", flush=True)

    html2 = (html[:m.start()] + "const EMBEDDED_DATA = " +
             json.dumps(data, ensure_ascii=False) + ";" + html[m.end():])
    HTML.write_text(html2, encoding="utf-8")
    print("OK updated", len(data), "items @", now, flush=True)


if __name__ == "__main__":
    main()
