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
xhs_{关键词}_{max_items}_{时间戳}.jsonl
```

示例：

```text
xhs_网球_15_20260512_200406.jsonl
```

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

