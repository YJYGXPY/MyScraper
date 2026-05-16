# MyScraper

基于 Playwright 的小红书关键词爬虫，支持自动抓取笔记、评论与回复，并在抓取完成后自动调用大模型生成分析报告。

当前流程：
- `main.py`：执行爬取 + 调用 `brain.analyze_data(...)` 分析
- `scrape.py`：负责登录、搜索、抓取、落盘 `jsonl`
- `brain.py`：读取 `jsonl` 全量数据，要求 LLM 严格输出 JSON，再渲染为 Markdown

## 1. 环境准备

1. 安装 Python（建议 3.10+）
2. 安装 `uv`
3. 在项目根目录安装依赖：

```bash
uv sync
```

## 2. 配置 `.env`（LLM）

请在项目根目录创建 `.env` 并配置 LLM 连接信息：

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://your-llm-compatible-endpoint/v1
LLM_MODEL=your_model_name
```

说明：
- `brain.py` 会从 `.env` 读取以上 3 个 LLM 变量
- 任一变量缺失会抛错并提示检查 `.env`

## 3. 运行方式（推荐）

默认执行完整流程：先派生关键词，再并行爬取，最后合并并分析。

使用位置参数传入“探索方向”：

```bash
uv run python main.py 游戏赛道
```

如果不传参数，会使用内置默认关键词（`羽毛球鞋`）：

```bash
uv run python main.py
```

查看参数帮助：

```bash
uv run python main.py -h
```

## 4. 参数说明

CLI 当前只保留一个参数：

- `key_word`（位置参数）：用户想探索的方向（关键词字符串）

其余运行配置为脚本内部常量（`main.py`）：

- `MAX_ITEMS`：每个关键词最大爬取数量（默认 `30`）
- `HEADLESS`：是否无头模式（默认 `False`）
- `MAX_CONCURRENCY`：并行抓取关键词上限（默认 `2`）

## 5. 输出目录与文件

### 5.1 爬取数据（`data/`）

- 输出目录：`data/`
- 关键词抓取采用并行执行（受 `MAX_CONCURRENCY` 限制）
- 文件名格式：

```text
xhs_{时间戳}_{关键词}_{max_items}.jsonl
```

示例：

```text
xhs_20260512_200406_网球_15.jsonl
```

如果派生出多个关键词，`main.py` 会在爬取后自动合并为一个文件：

```text
xhs_{时间戳}_{原始关键词}_{max_items}_merged.jsonl
```

### 5.2 检查点（`data/checkpoints/`）

为支持中断恢复，抓取过程会持续写入检查点：

- 输出目录：`data/checkpoints/`
- 文件名格式：

```text
{keyword_hash}.run_state.json
```

检查点中包含运行状态、已抓取进度、失败重试队列等信息。
### 5.3 分析结果（`future/`）

`main.py` 在爬取完成后会自动调用 `brain.analyze_data(saved_path)`，并将分析结果写入 `future/`：

- 原始结构化结果：`analysis_{data_stem}_{时间戳}.raw.json`
- 可读报告：`analysis_{data_stem}_{时间戳}.md`

## 6. 数据格式（JSONL）

- 文件为 `jsonl` 格式：每一行是 1 条完整笔记 JSON
- 顶层是笔记对象，内含 `comment_list`
- 评论对象内含 `reply_list`
- 计数字段当前为字符串（如 `"123"`、`"1.2万"`、`""`）

### 完整结构（用于 AI 分析）

```json
{
  "index": 1,
  "id": "/explore/xxxxxxxxxxxxxxxx",
  "title": "笔记标题",
  "author": "作者昵称",
  "description": "正文文本",
  "tag_description": "#标签1 #标签2",
  "time_location": "2026-05-12 广东",
  "like_count": "123",
  "collect_count": "45",
  "comment_count": "67",
  "comment_list": [
    {
      "note_id": "/explore/xxxxxxxxxxxxxxxx",
      "index": 1,
      "comment_id": "comment_xxx",
      "comment_author": "评论作者",
      "comment_content": "评论内容",
      "comment_like_count": "3",
      "comment_reply_count": "2",
      "reply_list": [
        {
          "comment_id": "comment_xxx",
          "index": 1,
          "reply_id": "reply_xxx",
          "reply_author": "回复作者",
          "reply_content": "回复内容",
          "reply_like_count": "1"
        }
      ]
    }
  ]
}
```

### 字段字典（含类型）

#### A. 笔记级字段

- `index`：`int`，文件内顺序编号（从 1 开始）
- `id`：`str`，笔记路径 ID（如 `/explore/...`）
- `title`：`str`，笔记标题，可能为空
- `author`：`str`，作者昵称，可能为空
- `description`：`str`，正文文本
- `tag_description`：`str`，标签文本，可能为空
- `time_location`：`str`，发布时间+地点原始文本，可能为空
- `like_count`：`str`，点赞数原始展示值
- `collect_count`：`str`，收藏数原始展示值
- `comment_count`：`str`，评论数原始展示值
- `comment_list`：`list[dict]`，评论列表

#### B. 评论级字段（`comment_list[*]`）

- `note_id`：`str`，所属笔记 ID
- `index`：`int`，评论顺序编号（从 1 开始）
- `comment_id`：`str`，评论 ID
- `comment_author`：`str`，评论作者昵称，可能为空
- `comment_content`：`str`，评论文本，可能为空
- `comment_like_count`：`str`，评论点赞数原始展示值
- `comment_reply_count`：`str`，评论回复数原始展示值
- `reply_list`：`list[dict]`，回复列表

#### C. 回复级字段（`comment_list[*].reply_list[*]`）

- `comment_id`：`str`，所属评论 ID
- `index`：`int`，回复顺序编号（从 1 开始）
- `reply_id`：`str`，回复 ID
- `reply_author`：`str`，回复作者昵称，可能为空
- `reply_content`：`str`，回复文本，可能为空
- `reply_like_count`：`str`，回复点赞数原始展示值

## 7. AI 分析机制（`brain.py`）

`brain.analyze_data(data_path)` 的行为：

1. 读取 `data_path` 指向的 `jsonl`（全量记录）
2. 读取 `README.md` 作为规则上下文
3. 构造提示词，要求模型只输出合法 JSON（固定 schema）
4. 校验 JSON 解析失败时自动重试
5. 结果补充 `meta` 后保存为：
   - `future/*.raw.json`
   - `future/*.md`

提示：
- 由于当前传入的是全量记录，数据很大时可能触发模型上下文限制

## 8. 登录说明

- 首次运行可能需要短信验证码登录
- 登录成功后会保存登录态到 `state.json`
- 后续运行会复用本地登录态（若有效）

## 9. 并行与失败处理说明

- `main.py` 会先通过 `brain.generate_keywords(...)` 派生关键词列表
- 第二步对关键词并行抓取（并发上限由 `MAX_CONCURRENCY` 控制）
- 单个关键词抓取失败时会记录并跳过，不会直接终止全部任务
- 若全部关键词都失败，流程会抛错并停止（不进入合并和分析）

## 10. 调试说明

可开启 Playwright 调试环境变量：

```bash
PWDEBUG=1 uv run python main.py 网球
```

## 11. 常见问题

- 参数无效：先用 `-h` 检查参数说明（当前仅支持位置参数 `key_word`）
- 终端出现 `bash: [200~$: command not found`：通常是粘贴了控制字符，手动重敲命令
- LLM 报配置缺失：检查 `.env` 是否包含 `LLM_API_KEY / LLM_BASE_URL / LLM_MODEL`
- 输出为空或 JSON 解析失败：检查模型是否遵守“仅输出 JSON”约束，必要时更换模型或缩小输入规模

## 12. 独立调用分析（可选）

如果只想对已存在的 `jsonl` 文件做分析，可在 Python 中直接调用：

```python
import brain
result_path = brain.analyze_data("data/your_file.jsonl")
print(result_path)
```

## 13. 版本控制说明

以下本地产物默认不会提交到 Git：
- `data/`
- `future/`
- `state.json`
- `.env`
