# Wind Resource Assessment Skill for Claude Code

测风塔风资源评估 Claude Code Skill — 从测风数据读取到完整评估报告的一站式工具。

## 功能

- 读取 Windographer (.windog)、CSV (.csv/.txt)、NRG SymphoniePRO (.rld) 格式的测风数据
- 自动执行数据质量控制、风速/风向统计、风切变/湍流分析
- Weibull 分布拟合、Gumbel 极值风速推算
- 生成 Markdown 报告 + PNG 图表 + Word 文档

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

> .rld 格式需额外安装 [SymphoniePRO Desktop](https://www.nrgsystems.com/support/product-support/software/symphoniepro-desktop-application)

### 运行分析

```bash
# .windog 文件
python skills/wind-resource/scripts/main.py "data.windog" --project-name "某风电项目" --mast-id 001

# CSV 文件
python skills/wind-resource/scripts/main.py "data.csv" --project-name "某风电项目"

# NRG .rld 目录（加密数据）
python skills/wind-resource/scripts/main.py "7152/" --project-name "孟家坪7152" --encryption-pass "your_password"
```

### 生成 Word 报告

```bash
python skills/wind-resource/scripts/generate_word_report.py
```

修改脚本中的 `CHARTS_*` 路径和 `data_*` 字典以匹配你的项目数据。

## 作为 Claude Code Skill 使用

将 `skills/` 目录复制到 `~/.claude/skills/`：

```bash
cp -r skills/wind-resource ~/.claude/skills/
```

然后在 Claude Code 中使用 `/wind-resource` 触发。

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `data_file` | 数据文件/目录路径 | 必填 |
| `--project-name` | 项目名称 | 文件名 |
| `--mast-id` | 测风塔编号 | 自动检测 |
| `--start-date` | 数据起始日期 | 2025-01-01 |
| `--elevation` | 海拔高度(m) | 0 |
| `--output-dir` | 输出目录 | 当前目录 |
| `--encryption-pass` | .rld 加密密码 | - |
| `--client-id` | NRG Cloud API 客户端ID | - |
| `--client-secret` | NRG Cloud API 客户端密钥 | - |

## 评估依据

- GB/T 18710-2002 《风电场风能资源评估方法》
- GB/T 18709-2002 《风电场风能资源测量方法》
- IEC 61400-12-1:2017 《风能发电系统 功率特性测量》
- IEC 61400-1:2019 《风能发电系统 设计要求》

## 项目结构

```
wind-resource-skill/
├── README.md
├── CLAUDE.md
├── requirements.txt
├── .gitignore
└── skills/
    └── wind-resource/
        ├── skill.md                    # Skill 定义文件
        └── scripts/
            ├── main.py                 # CLI 入口
            ├── windog_reader.py        # 数据读取（.windog/.csv/.rld）
            ├── wind_analysis.py        # 核心分析引擎
            ├── chart_generator.py      # 图表生成
            ├── report_generator.py     # Markdown 报告
            └── generate_word_report.py # Word 报告
```

## License

MIT
