# MyScraper

基于 Playwright 的小红书关键词爬取脚本。  
支持命令行传参：关键词、最大抓取数量、是否无头模式。

## 1. 环境准备

1. 安装 Python（建议 3.10+）
2. 安装 `uv`
3. 在项目根目录执行依赖安装：

```bash
uv sync
```

## 2. 运行方式

### 默认运行（使用代码内默认参数）

```bash
uv run python main.py
```

### 指定关键词和最大数量

```bash
uv run python main.py --key_word 网球 --max_items 5
```

### 无头模式运行

```bash
uv run python main.py --key_word 网球 --max_items 5 --headless True
```

## 3. 参数说明

- `--key_word`：搜索关键词（字符串）默认值：羽毛球鞋
- `--max_items`：最大爬取数量（整数）默认值：30
- `--headless`：是否无头模式（布尔值，`True/False`）默认值：False

查看帮助：

```bash
uv run python main.py -h
```

## 4. 输出结果

- 爬取结果保存到 `data/` 目录
- 文件名格式：

```text
xhs_{时间戳}_{关键词}_{max_items}.jsonl
```

示例：

```text
xhs_20260512_200406_网球_15.jsonl
```

### 数据格式（JSONL）

- 文件为 `jsonl` 格式：**每一行是 1 条完整笔记 JSON**
- 顶层是“笔记对象”，内含 `comment_list`（评论列表），评论内含 `reply_list`（回复列表）
- 所有计数字段当前都是字符串（例如 `"123"`、`"1.2万"`、`""`），AI 处理前建议做数值归一化

### 完整结构（用于后续 AI 处理）

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

#### A. 笔记级字段（每行 1 条）

- `index`：`int`，当前文件内的顺序编号（从 1 开始）
- `id`：`str`，笔记路径 ID（示例：`/explore/...`）
- `title`：`str`，笔记标题；可能为空字符串
- `author`：`str`，笔记作者昵称；可能为空字符串
- `description`：`str`，笔记正文文本（纯文本拼接）
- `tag_description`：`str`，标签文本（以空格拼接）；可能为空字符串
- `time_location`：`str`，发布时间+地点原始文本；可能为空字符串
- `like_count`：`str`，笔记点赞数（原始展示值）
- `collect_count`：`str`，笔记收藏数（原始展示值）
- `comment_count`：`str`，笔记评论数（原始展示值）
- `comment_list`：`list[dict]`，评论列表（见下）

#### B. 评论级字段（`comment_list[*]`）

- `note_id`：`str`，所属笔记 ID（与顶层 `id` 对齐）
- `index`：`int`，评论在该笔记下的顺序编号（从 1 开始）
- `comment_id`：`str`，评论 ID
- `comment_author`：`str`，评论作者昵称；可能为空字符串
- `comment_content`：`str`，评论文本；可能为空字符串
- `comment_like_count`：`str`，评论点赞数（原始展示值）
- `comment_reply_count`：`str`，评论回复数（原始展示值）
- `reply_list`：`list[dict]`，该评论下的回复列表（见下）

#### C. 回复级字段（`comment_list[*].reply_list[*]`）

- `comment_id`：`str`，所属评论 ID（与父评论 `comment_id` 对齐）
- `index`：`int`，回复在该评论下的顺序编号（从 1 开始）
- `reply_id`：`str`，回复 ID
- `reply_author`：`str`，回复作者昵称；可能为空字符串
- `reply_content`：`str`，回复文本；可能为空字符串
- `reply_like_count`：`str`，回复点赞数（原始展示值）

### AI 预处理建议（推荐）

- 将 `like_count / collect_count / comment_count / comment_like_count / comment_reply_count / reply_like_count` 统一转为数值字段（处理 `万/千` 等中文单位）
- 补充派生字段：
  - `description_len`（正文长度）
  - `tag_list`（把 `tag_description` 拆分为数组）
  - `comment_total`（`len(comment_list)`）
  - `reply_total`（所有评论下回复总数）
- 保留原始字段 + 新增规范字段并存，便于回溯与模型迭代
- 对空字符串字段统一做空值策略（`"" -> null` 或保留空串，二选一并全流程一致）

## 5. 登录说明

- 首次运行可能需要短信验证码登录
- 登录成功后会保存登录态到 `state.json`
- 后续运行会尝试复用本地登录态

## 6. 调试模式

可开启 Playwright 调试环境变量：

```bash
PWDEBUG=1 uv run python main.py --key_word 网球 --max_items 5
```

## 7. 常见问题

- 参数无效：先用 `-h` 查看参数名是否正确（例如 `--max_items`，不是 `--max_item`）
- 命令行出现 `bash: [200~$: command not found`：通常是终端粘贴了控制字符，手动重敲命令即可
- `--help` 没触发：确认文件已保存、参数里的 `-` 是英文半角减号

