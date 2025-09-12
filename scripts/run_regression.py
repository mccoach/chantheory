# scripts/run_regression.py
# ==============================
# 说明：快速对拍脚本
# - 模式：
#   * save  : 调用 /api/candles 保存 actual 为 golden（首次生成）
#   * diff  : 调用 /api/candles 保存 actual，与 golden 对比差异摘要
#   * update: 将 last actual 覆盖 golden（人工确认差异后）
# - 摘要差异：行数变化、首尾时间、source、价格/量均值/标准差
# ==============================

import argparse
import os
import json
import time
import yaml
import requests
from statistics import mean, pstdev

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GOLDEN_DIR = os.path.join(BASE, "var", "golden")
ACTUAL_DIR = os.path.join(BASE, "var", "actual")
os.makedirs(GOLDEN_DIR, exist_ok=True)
os.makedirs(ACTUAL_DIR, exist_ok=True)

def _fname(case):
    """构造文件名：code_freq_start_end.json"""
    def clean(s): return str(s).replace(":","").replace(" ","_")
    return f"{case['code']}_{case['freq']}_{clean(case['start'])}_{clean(case['end'])}.json"

def _get(server, case):
    """调用后端 /api/candles。"""
    url = f"{server}/api/candles"
    params = dict(case)
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    return r.json()

def _save(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _summary(payload):
    """提取摘要统计：rows/start/end/source/价格量均值/方差。"""
    meta = payload.get("meta") or {}
    candles = payload.get("candles") or []
    prices = [c["c"] for c in candles if isinstance(c.get("c"), (int,float))]
    vols = [c["v"] for c in candles if isinstance(c.get("v"), (int,float))]
    def stat(arr):
        if not arr: return {"mean": None, "std": None}
        return {"mean": round(mean(arr), 6), "std": round(pstdev(arr), 6)}
    return {
        "rows": meta.get("rows"),
        "start": meta.get("start"),
        "end": meta.get("end"),
        "source": meta.get("source"),
        "price": stat(prices),
        "vol": stat(vols),
    }

def _diff_summary(a, b):
    """摘要差异对比（字典）"""
    out = {}
    keys = ["rows","start","end","source"]
    for k in keys:
        if a.get(k) != b.get(k):
            out[k] = {"golden": a.get(k), "actual": b.get(k)}
    for k in ["price","vol"]:
        if a[k]["mean"] != b[k]["mean"] or a[k]["std"] != b[k]["std"]:
            out[k] = {"golden": a[k], "actual": b[k]}
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["save","diff","update"], required=True, help="save/diff/update golden")
    ap.add_argument("--server", default="http://localhost:8000", help="backend server origin")
    ap.add_argument("--cases", default=os.path.join(os.path.dirname(__file__), "cases.yaml"))
    args = ap.parse_args()

    with open(args.cases, "r", encoding="utf-8") as f:
        cases = yaml.safe_load(f).get("cases") or []

    if args.mode == "save":
        # 首次生成 golden
        for c in cases:
            payload = _get(args.server, c)
            name = _fname(c)
            _save(os.path.join(GOLDEN_DIR, name), payload)
            print(f"[save] golden -> {name}")
        return

    if args.mode == "diff":
        # 生成 actual 并对比 golden
        for c in cases:
            payload = _get(args.server, c)
            name = _fname(c)
            act_path = os.path.join(ACTUAL_DIR, name)
            _save(act_path, payload)
            gold_path = os.path.join(GOLDEN_DIR, name)
            if not os.path.exists(gold_path):
                print(f"[diff] missing golden: {name}")
                continue
            gold = _load(gold_path)
            da = _summary(payload)
            dg = _summary(gold)
            diff = _diff_summary(dg, da)
            if diff:
                print(f"[diff] {name}: DIFF -> {json.dumps(diff, ensure_ascii=False)}")
            else:
                print(f"[diff] {name}: OK")
        return

    if args.mode == "update":
        # 用 actual 覆盖 golden（人工确认后）
        for c in cases:
            name = _fname(c)
            act_path = os.path.join(ACTUAL_DIR, name)
            gold_path = os.path.join(GOLDEN_DIR, name)
            if os.path.exists(act_path):
                os.replace(act_path, gold_path)
                print(f"[update] golden <- {name}")
            else:
                print(f"[update] skip (no actual): {name}")

if __name__ == "__main__":
    main()
