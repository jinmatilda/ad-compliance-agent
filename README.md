# 广告宣传材料合规检查助手

一个可部署到 Streamlit Community Cloud 的中文广告发布前初筛 Agent。支持输入文字、海报图片和活动页截图；图片由 Tesseract OCR 提取原文，并由火山方舟多模态模型补充视觉与语义审查。系统使用题目给定的 A-01～A-10 规则进行确定性检查。结果只作第一轮提示，不构成法律意见。

## 支持的输入与输出

- 输入：最多 10,000 字文本；最多 5 张 PNG/JPEG，每张不超过 10 MB；可填写补充证据说明。
- 输出：风险内容原文、风险类型、对应规则、风险等级、修改建议、是否需要人工审核、置信度、原因和来源。
- 展示：带等级颜色和筛选排序的页面表格、逐条详情，以及 JSON、Markdown、可编辑 Word 下载。
- 历史：当前浏览器会话保存最近 10 次检查，可从侧栏回看；容器重启或会话失效后清空。
- A-06 始终拦截并转人工；A-09 始终要求核验真实性和授权；A-10 触发后不得显示无风险结论。

## 本地启动

系统需安装 Tesseract 及中文语言包。macOS 可通过 Homebrew 安装 `tesseract` 和中文语言数据；Debian/Ubuntu 使用 `sudo apt install tesseract-ocr tesseract-ocr-chi-sim`。

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

也可以运行 `./run.sh`，Mac Finder 中可双击 `run.command`。默认打开 http://localhost:8501。

本地语义审查需创建不会提交到 Git 的 `.streamlit/secrets.toml`：

```toml
ARK_API_KEY = "你的火山方舟 API Key"
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
ARK_MODEL = "doubao-seed-2-0-lite-260215"
```

可从 `.streamlit/secrets.toml.example` 复制。没有 Key 时，确定性规则仍运行，A-05、A-07、A-09 会明确降级为人工审核。

## Streamlit Community Cloud 部署

需要自己的 GitHub 账号、Streamlit Community Cloud 账号和火山方舟 API Key。

1. 在 GitHub 新建仓库，把本目录代码提交并推送；确认 `.streamlit/secrets.toml` 没有进入提交。
2. 使用 GitHub 账号登录 [share.streamlit.io](https://share.streamlit.io)。
3. 点击 **Create app**，选择 **Yup, I have an app**。
4. 填写 GitHub repository、branch（通常为 `main`）和 Main file path：`app.py`。
5. 打开 **Advanced settings**，在 Secrets 中填写 `ARK_API_KEY`、`ARK_BASE_URL` 和 `ARK_MODEL`，不要把 Key 写进仓库。
6. 在 App URL 中选择尚未被占用的固定子域名。
7. 点击 **Deploy**，等待构建完成；`requirements.txt` 安装 Python 包，`packages.txt` 安装 Tesseract 和中文语言包。
8. 在无登录浏览器窗口上传新图片并检查导出，确认远程访客可用。

部署后的固定地址形式为：[https://你的子域名.streamlit.app/](https://你的子域名.streamlit.app/)。Mac 关机不影响云端应用。免费平台可能休眠，首次打开会有冷启动时间。

## 火山方舟后台操作

1. 登录火山方舟控制台，开通支持视觉理解的模型，例如 Doubao-Seed-2.0-lite。
2. 创建 API Key，并确保账户有可用额度。
3. 从模型详情或 API 示例复制当前完整模型 ID；模型版本更新时，以控制台显示为准。
4. 只把 Key 粘贴到 Streamlit Cloud 的 **Advanced settings → Secrets**。
5. 如需换模型，在 Secrets 设置 `ARK_MODEL`。

Streamlit Secrets 示例：

```toml
ARK_API_KEY = "你的火山方舟 API Key"
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
ARK_MODEL = "控制台显示的完整模型 ID"
```

图片会同时进入两条链路：Tesseract OCR 用于可追溯原文、置信度和 A-10；火山方舟多模态模型读取原图并补充 A-01、A-05、A-07、A-09。模型不能撤销确定性规则命中，也不能在 A-10 证据不足时给出完整合规结论。

## A-01～A-10 演示样例

| 规则 | 建议输入/操作 | 预期重点 |
|---|---|---|
| A-01 | `全网最低价，第一名` | 绝对化表述 |
| A-02 | `用户满意度提升90%` | 缺来源、口径、时间 |
| A-03 | `满100减50` | 缺起止日期 |
| A-04 | `满100减50，活动1月1日至1月2日` | 缺商品、渠道、名额、叠加限制 |
| A-05 | `保证7天美白见效` | 效果承诺，语义审查/人工 |
| A-06 | `治疗失眠，无副作用` | 强制拦截及人工复核 |
| A-07 | `效果碾压所有竞品` | 对比贬损 |
| A-08 | `0元领，仅需运费9.9` | 免费与必要费用共现 |
| A-09 | `权威专家推荐` | 核验真实性与授权，转人工 |
| A-10 | 上传模糊图或取消勾选“完整页面” | 无法判断，要求原文件/完整页面 |

规则来自 `rules.yaml`，确定性逻辑位于 `adcheck/engine.py`，LLM 只补充 A-01/A-05/A-07/A-09，不能撤销规则命中。

演示时建议依次检查风险表格的等级筛选、侧栏历史回看，以及 `合规检查报告_时间戳.docx` 下载。Word 报告包含风险原文、类型、规则、等级、建议和人工审核标记，可继续编辑。

## 临时备用入口

云平台临时故障时，可在本机启动应用后使用已有的 `cloudflared tunnel --url http://localhost:8501` 建立临时 Quick Tunnel。该 URL 会变化且依赖本机在线，只作应急，不是主交付。项目不附带隧道账号、域名或凭据。

## 测试

```bash
python -m unittest discover -s tests -v
```

云部署检查：仓库中没有绝对本地路径、Apple Vision、macOS 专有包或真实密钥。Tesseract 是 `packages.txt` 中唯一系统依赖。
