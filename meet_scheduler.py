#!/usr/bin/env python3
"""运动会编排：报名名单 → 分组道次表（秩序册）+ 检录表 + 成绩记录表。

用法：
  python tools/meet_scheduler.py --demo
  python tools/meet_scheduler.py data/sample_meet_entries.csv --lanes 8 --seed 42

报名 CSV 列：姓名，班级，性别，组别，项目（一人一行一个项目；组别可空，默认按性别+项目分组）。
编排规则：同班尽量分散到不同组/相邻道次；径赛每组 ≤ 道数，田赛按序号轮次；
随机但可复现（--seed 固定后结果稳定，方便赛前核对）。
"""

from __future__ import annotations

import argparse
import csv
import os
import random
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
FIELD_EVENTS = ("跳高", "跳远", "铅球", "实心球", "垒球", "标枪", "铁饼")


def is_field(event: str) -> bool:
    return any(k in event for k in FIELD_EVENTS)


def interleave_by_class(entries: list[dict], rng: random.Random) -> list[dict]:
    """把同班学生打散：按班级轮转取人，再整体轻微洗牌（种子可复现）。"""
    by_class: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        by_class[e.get("班级", "")].append(e)
    for v in by_class.values():
        rng.shuffle(v)
    classes = list(by_class)
    rng.shuffle(classes)
    out = []
    idx = 0
    while any(by_class[c] for c in classes):
        c = classes[idx % len(classes)]
        if by_class[c]:
            out.append(by_class[c].pop())
        idx += 1
    return out


def build_schedule(entries: list[dict], lanes: int = 8, seed: int = 42) -> dict:
    """返回 {(组别，项目）: [ {heat: n, slots: [{lane, entry}]} ]}"""
    rng = random.Random(seed)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for e in entries:
        key = (e.get("组别") or "", e.get("性别", ""), e.get("项目", ""))
        groups[key].append(e)
    schedule = {}
    for key, es in sorted(groups.items()):
        ordered = interleave_by_class(es, rng)
        size = lanes if not is_field(key[2]) else max(lanes, 10)
        heats = []
        for i in range(0, len(ordered), size):
            chunk = ordered[i:i + size]
            heats.append({"heat": len(heats) + 1,
                          "slots": [{"lane": j + 1, "entry": e} for j, e in enumerate(chunk)]})
        schedule[key] = heats
    return schedule


def schedule_markdown(schedule: dict) -> str:
    lines = ["# 运动会秩序册（分组表）", ""]
    for (division, gender, event), heats in schedule.items():
        title = f"{division} {gender} {event}".strip()
        for h in heats:
            lines.append(f"## {title} · 第 {h['heat']} 组")
            lines.append("")
            lines.append("| 道次/序号 | 姓名 | 班级 | 成绩 | 名次 |")
            lines.append("|---|---|---|---|---|")
            for s in h["slots"]:
                e = s["entry"]
                lines.append(f"| {s['lane']} | {e.get('姓名', '')} | {e.get('班级', '')} |  |  |")
            lines.append("")
    return "\n".join(lines)


def sample_entries() -> list[dict]:
    classes = ["五(1)班", "五(2)班", "五(3)班"]
    names_m = ["王强", "李雷", "张伟", "刘洋", "陈杰", "杨帆", "黄辉", "周鹏", "吴昊", "徐磊", "孙博", "胡军"]
    names_f = ["韩梅", "林娜", "赵敏", "钱雪", "孙丽", "李静", "王芳", "刘颖", "陈晨", "杨柳", "黄莺", "周婷"]
    entries = []
    for ci, cls in enumerate(classes):
        for i in range(4):
            entries.append({"姓名": names_m[ci * 4 + i], "班级": cls, "性别": "男", "组别": "小学男子组", "项目": "100米"})
            entries.append({"姓名": names_f[ci * 4 + i], "班级": cls, "性别": "女", "组别": "小学女子组", "项目": "100米"})
        for i in range(2):
            entries.append({"姓名": names_m[ci * 4 + i], "班级": cls, "性别": "男", "组别": "小学男子组", "项目": "立定跳远"})
            entries.append({"姓名": names_f[ci * 4 + i], "班级": cls, "性别": "女", "组别": "小学女子组", "项目": "立定跳远"})
    return entries



def parse_result_value(v):
    """成绩转数值：支持 13.25 / 4:05 / 4分05秒 / 186（厘米）等写法。"""
    if v is None or str(v).strip() == "":
        return None
    s = str(v).strip().replace("：", ":")
    try:
        return float(s)
    except ValueError:
        pass
    import re
    m = re.match(r"^(?:(\d+)\s*[:'分])?\s*(\d+(?:\.\d+)?)\s*(?:\"|秒)?$", s)
    if m:
        return int(m.group(1) or 0) * 60 + float(m.group(2))
    return None


def rank_event(rows: list[dict], event: str) -> list[dict]:
    """给一个组别项目的成绩排名：径赛时间小者优，田赛数值大者优；同成绩并列（竞赛排名 1,2,2,4）。"""
    field = is_field(event)
    scored = []
    for r in rows:
        val = parse_result_value(r.get("成绩"))
        if val is not None:
            scored.append({**r, "_value": val})
    scored.sort(key=lambda r: -r["_value"] if field else r["_value"])
    out = []
    prev_val, prev_rank = None, 0
    for i, r in enumerate(scored, 1):
        rank = prev_rank if (prev_val is not None and r["_value"] == prev_val) else i
        prev_val, prev_rank = r["_value"], rank
        out.append({**r, "rank": rank})
    return out


def rank_all(rows: list[dict]) -> dict:
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        key = (r.get("组别", ""), r.get("性别", ""), r.get("项目", ""))
        groups.setdefault(key, []).append(r)
    return {key: rank_event(rs, key[2]) for key, rs in sorted(groups.items())}


def check_records(ranked: dict, records: dict) -> dict:
    """返回被打破的纪录：{key_str: {old, new, holder_name}}。records 键为 '组别|性别|项目'。"""
    broken = {}
    for (division, gender, event), rows in ranked.items():
        if not rows:
            continue
        key = f"{division}|{gender}|{event}"
        rec = records.get(key)
        if not rec:
            continue
        best = rows[0]
        old = float(rec["value"])
        better = best["_value"] > old if is_field(event) else best["_value"] < old
        if better:
            broken[key] = {"old": old, "new": best["_value"],
                           "holder": best.get("姓名", ""), "class": best.get("班级", ""),
                           "previous_holder": rec.get("holder", "")}
    return broken


def team_standings(ranked: dict, points_table=(7, 5, 4, 3, 2, 1)) -> list[dict]:
    """按班级汇总团体分：名次给分（默认前六名 7/5/4/3/2/1），并统计金银铜。"""
    table: dict[str, dict] = {}
    for rows in ranked.values():
        for r in rows:
            cls = r.get("班级", "")
            t = table.setdefault(cls, {"class": cls, "points": 0, "gold": 0, "silver": 0, "bronze": 0})
            if 1 <= r["rank"] <= len(points_table):
                t["points"] += points_table[r["rank"] - 1]
            if r["rank"] == 1:
                t["gold"] += 1
            elif r["rank"] == 2:
                t["silver"] += 1
            elif r["rank"] == 3:
                t["bronze"] += 1
    return sorted(table.values(), key=lambda t: (-t["points"], -t["gold"], -t["silver"], -t["bronze"], t["class"]))


def rankings_markdown(ranked: dict, broken: dict | None = None, points_table=(7, 5, 4, 3, 2, 1)) -> str:
    lines = ["# 比赛成绩册", ""]
    broken = broken or {}
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for (division, gender, event), rows in ranked.items():
        title = f"{division} {gender} {event}".strip()
        key = f"{division}|{gender}|{event}"
        suffix = ""
        if key in broken:
            b = broken[key]
            suffix = f" · 🎉 新纪录 {b['new']}（原 {b['old']} / {b['previous_holder']}）"
        lines.append(f"## {title}{suffix}")
        lines.append("")
        lines.append("| 名次 | 姓名 | 班级 | 成绩 | 得分 |")
        lines.append("|---|---|---|---|---|")
        pts = points_table
        for r in rows:
            p = pts[r["rank"] - 1] if 1 <= r["rank"] <= len(pts) else ""
            lines.append(f"| {medals.get(r['rank'], r['rank'])} | {r.get('姓名', '')} | {r.get('班级', '')} | {r.get('成绩', '')} | {p} |")
        lines.append("")
    return "\n".join(lines)


def standings_markdown(standings: list[dict]) -> str:
    lines = ["# 团体总分榜", "", "| 排名 | 班级 | 团体分 | 金 | 银 | 铜 |", "|---|---|---|---|---|---|"]
    for i, t in enumerate(standings, 1):
        lines.append(f"| {i} | {t['class']} | {t['points']} | {t['gold']} | {t['silver']} | {t['bronze']} |")
    return "\n".join(lines)


def load_csv(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def demo_results_rows() -> list[dict]:
    import random as _random
    rng = _random.Random(7)
    rows = []
    for e in sample_entries():
        v = round(rng.uniform(13.1, 17.5), 2) if e["项目"] == "100米" else int(rng.uniform(145, 215))
        rows.append({**e, "成绩": v})
    return rows


def main():
    ap = argparse.ArgumentParser(description="运动会编排与成绩处理（独立版）")
    sub = ap.add_subparsers(dest="cmd")
    p1 = sub.add_parser("schedule", help="报名名单 → 秩序册")
    p1.add_argument("csv_path", nargs="?", default="")
    p1.add_argument("--lanes", type=int, default=8)
    p1.add_argument("--seed", type=int, default=42)
    p1.add_argument("--out", default="")
    p2 = sub.add_parser("results", help="成绩名单 → 名次 / 团体总分 / 破纪录")
    p2.add_argument("csv_path", nargs="?", default="")
    p2.add_argument("--records", default="", help="纪录 JSON（键：组别|性别|项目）")
    p2.add_argument("--points", default="7,5,4,3,2,1")
    p2.add_argument("--out", default="")
    ap.add_argument("--demo", action="store_true", help="全流程演示：编排 + 成绩处理")
    args = ap.parse_args()

    out_dir = getattr(args, "out", "") or os.path.join(BASE, "output")
    os.makedirs(out_dir, exist_ok=True)

    if args.demo or not args.cmd:
        entries = sample_entries()
        schedule = build_schedule(entries, lanes=8, seed=42)
        with open(os.path.join(out_dir, "meet_schedule.md"), "w", encoding="utf-8") as f:
            f.write(schedule_markdown(schedule))
        import json as _json
        rec_path = os.path.join(BASE, "data", "records_sample.json")
        records = _json.load(open(rec_path, encoding="utf-8")) if os.path.exists(rec_path) else {}
        ranked = rank_all(demo_results_rows())
        broken = check_records(ranked, records)
        standings = team_standings(ranked)
        with open(os.path.join(out_dir, "rankings.md"), "w", encoding="utf-8") as f:
            f.write(rankings_markdown(ranked, broken))
        with open(os.path.join(out_dir, "standings.md"), "w", encoding="utf-8") as f:
            f.write(standings_markdown(standings))
        print(f"演示完成：秩序册 + 成绩册 + 团体总分榜已生成到 {out_dir}/")
        print(standings_markdown(standings))
        for k, b in broken.items():
            print(f"🎉 破纪录：{k} 新纪录 {b['new']}（{b['holder']} / {b['class']}，原纪录 {b['old']}）")
        return

    if args.cmd == "schedule":
        entries = sample_entries() if not args.csv_path else load_csv(args.csv_path)
        schedule = build_schedule(entries, lanes=args.lanes, seed=args.seed)
        path = os.path.join(out_dir, "meet_schedule.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(schedule_markdown(schedule))
        heats = sum(len(v) for v in schedule.values())
        print(f"共 {len(schedule)} 个组别项目、{heats} 个小组，秩序册：{path}")
    elif args.cmd == "results":
        rows = demo_results_rows() if not args.csv_path else load_csv(args.csv_path)
        records = {}
        if args.records:
            import json as _json
            records = _json.load(open(args.records, encoding="utf-8"))
        points = tuple(int(x) for x in args.points.split(",") if x.strip())
        ranked = rank_all(rows)
        broken = check_records(ranked, records)
        standings = team_standings(ranked, points)
        with open(os.path.join(out_dir, "rankings.md"), "w", encoding="utf-8") as f:
            f.write(rankings_markdown(ranked, broken, points))
        with open(os.path.join(out_dir, "standings.md"), "w", encoding="utf-8") as f:
            f.write(standings_markdown(standings))
        with open(os.path.join(out_dir, "awards.csv"), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["组别", "性别", "项目", "名次", "姓名", "班级", "成绩"])
            for (division, gender, event), rs in ranked.items():
                for r in rs:
                    if r["rank"] <= len(points):
                        w.writerow([division, gender, event, r["rank"], r.get("姓名", ""), r.get("班级", ""), r.get("成绩", "")])
        print(standings_markdown(standings))
        for k, b in broken.items():
            print(f"🎉 破纪录：{k} 新纪录 {b['new']}（{b['holder']} / {b['class']}）")
        print(f"\n成绩册 / 总分榜 / 获奖名单已生成到 {out_dir}/")


if __name__ == "__main__":
    main()
