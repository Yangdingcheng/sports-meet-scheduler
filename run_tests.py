#!/usr/bin/env python3
"""运动会编排与成绩处理（独立版）测试：python run_tests.py"""

import os
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from meet_scheduler import (build_schedule, check_records, load_csv,
                            parse_result_value, rank_all, rank_event,
                            sample_entries, schedule_markdown, team_standings)

PASS = []
def check(name, cond):
    PASS.append((name, bool(cond)))
    print(("✅" if cond else "❌"), name)
    assert cond, name

# ---------- 编排（回归） ----------
entries = sample_entries()
sched = build_schedule(entries, lanes=8, seed=42)
total = sum(len(h["slots"]) for hs in sched.values() for h in hs)
check("编排-人数守恒", total == len(entries))
check("编排-可复现", schedule_markdown(sched) == schedule_markdown(build_schedule(entries, lanes=8, seed=42)))

# ---------- 成绩解析 ----------
check("成绩-秒", parse_result_value("13.25") == 13.25)
check("成绩-分秒", parse_result_value("4:05") == 245)
check("成绩-空", parse_result_value("") is None)

# ---------- 排名 ----------
rows = [{"姓名": "A", "班级": "一班", "成绩": "13.5"},
        {"姓名": "B", "班级": "二班", "成绩": "13.2"},
        {"姓名": "C", "班级": "一班", "成绩": "13.5"},
        {"姓名": "D", "班级": "三班", "成绩": "14.0"}]
ranked = rank_event(rows, "100米")
by_name = {r["姓名"]: r["rank"] for r in ranked}
check("排名-径赛升序", by_name["B"] == 1)
check("排名-并列同名次", by_name["A"] == 2 and by_name["C"] == 2)
check("排名-并列后跳号", by_name["D"] == 4)
field = rank_event([{"姓名": "X", "班级": "一班", "成绩": "180"},
                    {"姓名": "Y", "班级": "二班", "成绩": "195"}], "立定跳远")
check("排名-田赛降序", field[0]["姓名"] == "Y")

# ---------- 团体总分 ----------
all_ranked = rank_all([dict(r, 组别="甲组", 性别="男", 项目="100米") for r in rows])
standings = team_standings(all_ranked)
points = {t["class"]: t["points"] for t in standings}
check("团体分-冠军班5分制校验", points["二班"] == 7 and points["一班"] == 5 + 5 and points["三班"] == 3)

# ---------- 破纪录 ----------
records = {"甲组|男|100米": {"value": 13.30, "holder": "旧纪录"}}
broken = check_records(all_ranked, records)
check("破纪录-检出", "甲组|男|100米" in broken and broken["甲组|男|100米"]["holder"] == "B")
records2 = {"甲组|男|100米": {"value": 13.00, "holder": "旧纪录"}}
check("破纪录-未破不报", check_records(all_ranked, records2) == {})

# ---------- 演示数据闭环 ----------
results = load_csv(os.path.join(BASE, "data", "sample_results.csv"))
demo_ranked = rank_all(results)
demo_standings = team_standings(demo_ranked)
check("演示数据-四项目全 ranked", len(demo_ranked) == 4)
check("演示数据-三班都有分", len(demo_standings) == 3 and all(t["points"] > 0 for t in demo_standings))

r = subprocess.run([sys.executable, os.path.join(BASE, "meet_scheduler.py"), "--demo",
                    ], capture_output=True, text=True, cwd=BASE)
check("CLI演示全流程", r.returncode == 0 and "团体总分榜" in r.stdout)

print(f"\n全部 {len(PASS)} 项测试通过 ✅" if all(c for _, c in PASS) else "\n存在失败 ❌")
