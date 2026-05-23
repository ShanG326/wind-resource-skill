---
name: wind-resource
description: 风资源评估报告生成 — 读取测风塔数据(.windog/.csv/.rld)，执行完整风资源分析，生成Markdown报告+图表+Word文档
triggers:
  - 风资源评估
  - 测风数据分析
  - 风资源报告
  - wind resource assessment
  - 测风塔
---

# 风资源评估技能

## 概述

读取测风塔观测数据，自动完成风资源评估全流程：数据读取 → 质量控制 → 统计分析 → 图表生成 → 报告输出（Markdown + Word）。

## 支持的数据格式

| 格式 | 说明 | 依赖 |
|------|------|------|
| `.windog` | Windographer 4.x 专有格式（12字节头+zlib压缩） | 无 |
| `.csv` / `.txt` | 逗号/Tab分隔文本 | 无 |
| `.rld` | NRG SymphoniePRO 原始数据 | nrgpy + SymphoniePRO Desktop |

## 使用方法

### 基本用法

```
/wind-resource <数据文件路径> [--project-name 项目名] [--mast-id 测风塔编号]
                                [--start-date 起始日期] [--elevation 海拔]
                                [--output-dir 输出目录]
```

### NRG .rld 加密数据

```
/wind-resource <rld目录> --encryption-pass 密码 --project-name 项目名
```

### 示例

```bash
# .windog 文件
python scripts/main.py "1373原始数据.windog" --project-name "方山县50MW风电项目" --mast-id 1373

# CSV 文件
python scripts/main.py "测风数据.csv" --project-name "某风电项目"

# NRG .rld 目录（加密）
python scripts/main.py "7152/" --project-name "孟家坪7152" --encryption-pass "Xx250120"
```

## 分析内容

1. **数据质量控制** — 完整率统计、异常值检测
2. **风速统计** — 平均/最大风速、风功率密度、Weibull拟合
3. **风向分析** — 16方位风玫瑰图、主导风向/风能方向
4. **风切变分析** — 各层风切变指数α、幂律拟合
5. **湍流强度** — 平均TI、TI@15m/s、IEC分类
6. **空气密度** — 基于温度气压计算
7. **极端风速** — Gumbel极值分布推算50年一遇风速
8. **综合评价** — 风资源等级评定

## 输出文件

| 文件 | 说明 |
|------|------|
| `{项目名}_风资源评估报告.md` | Markdown格式报告 |
| `{项目名}_分析数据.json` | 完整分析数据 |
| `{项目名}_wind_report_charts/` | 所有图表（PNG） |
| `{项目名}_风资源评估报告.docx` | Word格式报告（可选） |

## 生成Word报告

当用户要求Word格式时，运行：

```bash
python scripts/generate_word_report.py
```

需修改脚本中的 `CHARTS_*` 路径指向对应的图表目录，并填入分析数据。

## 依赖安装

```bash
pip install pandas numpy scipy matplotlib python-docx
# .rld 格式额外需要：
pip install nrgpy
# 并安装 SymphoniePRO Desktop: https://www.nrgsystems.com/support/product-support/software/symphoniepro-desktop-application
```

## 评估标准

- GB/T 18710-2002 风电场风能资源评估方法
- IEC 61400-12-1:2017 功率特性测量
- IEC 61400-1:2019 设计要求

## 注意事项

- 测风数据不足1年时，极端风速估算不确定性较大，报告中会标注
- .rld格式仅支持Windows（需SymphoniePRO Desktop）
- 空气密度由温度+气压计算；若无则由海拔估算；若均无则取标准值1.225 kg/m³
- hPa气压单位会自动转换为kPa以保持一致性