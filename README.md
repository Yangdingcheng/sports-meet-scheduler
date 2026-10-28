# 运动会编排与成绩处理 🏅

校运会全流程工具：赛前把**报名名单**一键编成**秩序册**（分组道次表），
赛后把**成绩名单**一键算出**名次、团体总分榜、获奖名单**，还能自动标记**破纪录**。
纯 Python 标准库，零依赖，离线可用。

## 快速开始

```bash
python meet_scheduler.py --demo                       # 全流程演示（编排 + 成绩处理）
python meet_scheduler.py schedule 报名.csv --lanes 8 --seed 42
python meet_scheduler.py results 成绩.csv --records 纪录.json
python run_tests.py                                   # 15 项自检
```

## 编排（schedule）

报名 CSV 列：`姓名，班级，性别，组别，项目`（一人一行一个项目）。

- 按（组别 × 性别 × 项目）自动分组，径赛每组不超过道数（默认 8 道），田赛按序号轮次
- **同班打散**：轮转取人，尽量避免同班扎堆同组同道
- **种子可复现**：`--seed` 固定后编排结果稳定，打印出来核对不怕每次不一样
- 输出 `meet_schedule.md`：带成绩/名次空栏的秩序册，可直接打印当检录与记录表

## 成绩处理（results）

成绩 CSV 列：`姓名，班级，性别，组别，项目，成绩`（径赛写秒或 `4:05` 都认，田赛写数值）。

- **自动排名**：径赛时间小者优、田赛数值大者优；同成绩**并列同名次**，后续名次跳号（1,2,2,4 竞赛排名）
- **团体总分**：默认前六名按 7/5/4/3/2/1 计分（`--points` 可改，如只取前三 `--points 5,3,1`），
  同时统计各班金银铜，输出总分榜 `standings.md`
- **破纪录检测**：给一份纪录 JSON（键为 `组别|性别|项目`，含 value 与 holder），
  成绩册里自动 🎉 标出新纪录及原纪录保持者
- 输出：`rankings.md` 成绩册、`standings.md` 团体总分榜、`awards.csv` 获奖名单（可直接拿去印奖状/广播稿）

`data/` 里有配套示例：`sample_entries.csv`（36 条报名）、`sample_results.csv`（对应成绩）、
`records_sample.json`（示例校纪录）—— `--demo` 用的就是这套数据。

## License

MIT
