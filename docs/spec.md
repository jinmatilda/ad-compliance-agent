# 03｜广告宣传材料合规检查助手：架构设计 Spec

状态：2026-09-13 经用户授权，以本版本覆盖旧 FastAPI/Apple Vision/Codex CLI/固定隧道架构。

## 1. 目标与非目标

实现 Streamlit 单页广告初筛 Agent，部署到用户自己的 Streamlit Community Cloud。输入中文文本、海报图片、活动页截图；图片由 Tesseract OCR。输出风险内容原文、风险类型、对应规则、风险等级、修改建议、是否人工审核，并增加置信度、判定状态、原因和来源。页面提供表格、详情、JSON/Markdown 导出。

不做法律结论、法规库、特殊行业专项审核、证据真伪认证、PDF/视频/网页抓取、业务账号审批、自动发布、历史持久化或独立广告批处理。临时隧道不是主交付。

## 2. 当前系统与建议结构

本项目原来只有 `docs/plan.md`、`docs/spec.md`、`docs/tickets.md`，没有实现。旧 Spec 所述 FastAPI、Vision 和 Codex CLI 尚未实现。新系统结构：

```text
app.py                         # Streamlit 入口
adcheck/models.py              # Finding、Report
adcheck/rules.py               # YAML 严格加载
adcheck/engine.py              # 确定性规则及混合编排
adcheck/semantic.py            # OpenAI Responses 语义审查
adcheck/ocr.py                 # Tesseract OCR 与质量信号
adcheck/exporters.py           # JSON/Markdown
rules.yaml                     # A-01～A-10 配置
requirements.txt               # 云端 Python 依赖
packages.txt                   # Debian Tesseract 包
.streamlit/config.toml         # Streamlit 配置
.streamlit/secrets.toml.example# 无真实 Key 模板
tests/test_rules.py            # 外部行为测试
run.sh / run.command           # 本地入口
```

数据流：用户输入 → Streamlit 会话内读取 → 图片字节交 Tesseract → 合并正文/OCR/补充说明 → 确定性规则 → 可选 OpenAI 语义检查 → 去重与处置 → 页面/导出。应用不保存数据库或服务器历史；Streamlit 会话刷新后结果可能丢失。

运行：`pip install -r requirements.txt && streamlit run app.py`。测试：`python -m unittest discover -s tests -v`。

## 3. 需求追踪

| ID | 需求 | 设计 | 验证 |
|---|---|---|---|
| REQ-001 | Streamlit 单页及云部署 | `app.py`、依赖文件 | 本地 HTTP、云手工部署 |
| REQ-002～008 | 完整输出、结论、人工、置信度、来源、声明 | `Finding`/`Report` | 字段及导出测试 |
| REQ-009 | A-01 | 词库/正则并允许 LLM 补充 | `全网最低价，第一名` |
| REQ-010 | A-02 | 数字附近检查来源/口径/时间 | `满意度提升90%` |
| REQ-011 | A-03 | 优惠出现时要求两个日期 | `满100减50` |
| REQ-012 | A-04 | 商品/渠道/名额/叠加条件 | 带日期但缺限制 |
| REQ-013 | A-05 | 本地候选 + LLM；缺 Key 转人工 | 效果承诺样例 |
| REQ-014 | A-06 | 精确词库，强制高风险拦截 | `治疗…无副作用` |
| REQ-015 | A-07 | 对比候选 + LLM | `碾压所有竞品` |
| REQ-016 | A-08 | 免费词与押金/运费/续费等共现 | `0元领，仅需运费9.9` |
| REQ-017 | A-09 | 背书候选 + LLM，仅要求材料并转人工 | `专家推荐` |
| REQ-018 | A-10 | OCR 置信度、清晰度、空结果、完整性 | 模糊图/不完整勾选 |
| REQ-019～021 | LLM 结构化、不可撤销规则、失败降级 | `semantic.py`/`engine.py` | 无 Key 与异常测试 |
| REQ-022～026 | 文本、最多5图、大小/字符限制、OCR校对、补证 | Streamlit 输入区 | UI/边界验证 |
| REQ-027～032 | 风险合并、等级、结论与双导出一致 | Report/exporters | 单元测试 |
| REQ-033～040 | 页面输入、提示、表格、详情、规则区、下载 | `app.py` | HTTP/App 冒烟与手测 |
| REQ-041～045 | 十规则、正常/边界/异常/回归样例 | `tests/`、README | unittest |
| REQ-046～050 | Linux 依赖、Tesseract、Secrets、忽略密钥 | 部署文件 | 安装与静态扫描 |
| REQ-051～053 | README、固定 URL 流程、备用隧道 | README | 文档核对 |

## 4. 详细设计

### 4.1 规则库

`rules.yaml` 每条包含 `rule_id`、`name`、`level`、`matcher`、`suggestion`、`manual`。加载器拒绝字段缺失、重复 ID 或非完整 A-01～A-10 集合。匹配实现保留在 Python，YAML 是可审计业务配置，不能由 LLM 自由创造规则。

### 4.2 文本与 OCR

正文、OCR 结果、补充证据合并检查，同时保留 OCR 原文。`pytesseract.image_to_data` 返回词块和置信度；中文优先 `chi_sim+eng`，中文包异常时尝试英文并触发 A-10。Pillow 和边缘方差/对比度提供可解释的模糊信号。没有文字、平均置信度低于 60、低清晰度、OCR 异常、超限图片或用户标记页面不完整均产生 A-10。A-10 不会输出通过结论。

OCR 成功不证明截图完整或披露显著；用户可复制识别文字到正文修正后重审。

### 4.3 确定性与 LLM 衔接

引擎先执行确定性规则并保存结果，再调用 OpenAI Responses API。语义层只允许返回 A-01/A-05/A-07/A-09，quote 必须逐字存在于输入，输出采用 JSON Schema。语义结果只新增发现，不能删除 A-06 或其他规则发现。

Key 由页面用 `st.secrets["OPENAI_API_KEY"]` 读取，可选 `OPENAI_MODEL` 默认 `gpt-4.1-mini`。缺 Key、额度/网络/格式错误时状态为“降级”，保留已有发现，并分别为 A-05/A-07/A-09 增加“无法判断、需人工审核”项。页面必须显示降级提示。

### 4.4 风险和人工策略

A-06 固定高风险、结论“拦截并人工复核”。A-08 明确隐藏必要费用及明确 A-05/A-07 可为高风险；其他必要披露缺失为中风险。置信度为高/中/低的依据强度描述，不是概率。所有发现和待核实项人工审核；A-09 永远人工核验真实性与授权；A-10/语义降级永远不能判“未发现题设规则风险”。

### 4.5 输出 Schema

```json
{
  "结论": "拦截并人工复核|需人工审核|未发现题设规则风险",
  "检查时间": "ISO-8601",
  "语义审查状态": "完成|降级",
  "语义审查说明": "string",
  "OCR平均置信度": 0,
  "OCR文字": "string",
  "风险项": [{
    "风险内容原文": "string", "风险类型": "string", "对应规则": "A-01",
    "规则名称": "string", "风险等级": "高|中|低", "修改建议": "string",
    "是否需要人工审核": true, "置信度": "高|中|低",
    "判定状态": "明确风险|待核实|无法判断", "原因": "string", "来源": "string"
  }],
  "声明": "string"
}
```

### 4.6 页面与流程

侧栏展示十规则；主区依次为正文、补证、多图上传、完整性勾选和检查按钮；结果区展示总结、语义状态、OCR 文本、表格、逐条详情及两个下载按钮。无输入、图数/体积/字符超限给出可操作错误。失败不会伪造识别文字或合规结论。

### 4.7 部署与 Secrets

仓库根目录包含 `app.py`、`requirements.txt`、`packages.txt`。Streamlit Cloud 构建 Linux 容器，后者安装：

```text
tesseract-ocr
tesseract-ocr-chi-sim
```

本地 `.streamlit/secrets.toml` 及 Streamlit Cloud Advanced settings 使用：

```toml
OPENAI_API_KEY = "sk-..."
OPENAI_MODEL = "gpt-4.1-mini"
```

模板文件名为 `.streamlit/secrets.toml.example`，不含真实 Key；`.gitignore` 排除真实文件。主 URL 为用户选择的 `https://<subdomain>.streamlit.app/`。代码不得包含绝对桌面路径、Apple Vision、macOS API、本机 Codex CLI或隧道凭据。

## 5. 测试与验收

已经从当前项目确认的命令：`python -m unittest discover -s tests -v`、`streamlit run app.py`、`curl -I http://localhost:8501`。建议但需用户部署后验证：从无登录远程浏览器打开固定 Streamlit URL、提交文字与图片、下载两种报告。

单元测试至少覆盖十条规则、A-06 优先结论、A-09 人工、A-10 不通过、无 Key 降级、字段和导出。OCR 集成需确认 `tesseract --version`、`tesseract --list-langs` 包含 `chi_sim`。线上验收必须由用户配置账号/Key 后完成，不能用本地 200 冒充线上成功。

## 6. 实现约束

- 只作第一轮合规提示，不接真实法律结论。
- A-09 不由 Agent 判断真实性/授权，必须人工。
- A-10 证据不足不得判合规。
- 不提交真实 Key，不记录用户材料，不引入 macOS 专有包。
- 页面/JSON/Markdown来自同一对象；LLM 不能撤销确定性命中。
- 云端免费资源、冷启动、OCR 与模型误差必须如实披露。

## 7. 风险与待确认项

非阻塞风险：Tesseract 对艺术字/低清图片可能漏识别；模糊与完整性检测是启发式；LLM API 需要用户额度；免费 Streamlit 应用可能休眠；固定子域名需未被占用。默认处理均为展示具体不确定原因并转人工。阻塞性设计问题为零；实际永久 URL 仍需用户手动拥有 GitHub 仓库、登录 Streamlit、填写 Secrets 并点击 Deploy。
