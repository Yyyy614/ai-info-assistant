"""
开源项目深度分析器
- git clone 仓库
- 读取关键文件
- 调用 DeepSeek API 分析架构 + 提取工作流
- 输出结构化中文文档
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from anthropic import Anthropic

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output" / "deepdive"

# 关键文件模式（按优先级）
KEY_FILES = [
    "README.md", "README.rst", "README",
    "setup.py", "pyproject.toml", "requirements.txt", "Pipfile",
    "package.json", "Cargo.toml", "go.mod",
    "Makefile", "Dockerfile", "docker-compose.yml",
    ".env.example", "config.yaml", "config.example.yaml",
    "main.py", "app.py", "run.py", "cli.py",
    "index.js", "server.js", "main.go",
]

# 忽略的目录
IGNORE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tox",
               "dist", "build", ".eggs", ".mypy_cache", ".pytest_cache"}


def _get_client() -> Anthropic:
    return Anthropic(
        api_key=os.environ.get("ANTHROPIC_AUTH_TOKEN", ""),
        base_url=os.environ.get("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic"),
    )


def _call_ai(prompt: str, max_tokens: int = 8000) -> str | None:
    """调用 DeepSeek API"""
    try:
        client = _get_client()
        model = os.environ.get("ANTHROPIC_MODEL", "deepseek-v4-pro[1m]")
        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        for block in message.content:
            if hasattr(block, "text"):
                return block.text
        # 如果只有 ThinkingBlock（DeepSeek 短响应），取 thinking 内容
        if message.content:
            first = message.content[0]
            if hasattr(first, "thinking"):
                return first.thinking
            return str(first)
        return None
    except Exception as e:
        print(f"  ❌ API调用失败: {e}")
        return None


def _clone_repo(repo_url: str, target_dir: Path) -> bool:
    """Clone 仓库到目标目录"""
    try:
        # 浅克隆，只取最新
        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(target_dir)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            print(f"  ❌ Clone失败: {result.stderr[:200]}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"  ❌ Clone超时，请检查网络或开启VPN")
        return False
    except FileNotFoundError:
        print(f"  ❌ 未找到 git 命令，请确保已安装 Git")
        return False


def _build_dir_tree(root: Path, max_depth: int = 3) -> str:
    """构建目录树字符串"""
    lines = []
    root_name = root.name

    def walk(path: Path, prefix: str = "", depth: int = 0):
        if depth > max_depth:
            return
        entries = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        dirs = [e for e in entries if e.is_dir() and e.name not in IGNORE_DIRS]
        files = [e for e in entries if e.is_file()]

        # 显示目录
        for d in dirs[:-1]:
            lines.append(f"{prefix}├── {d.name}/")
            walk(d, prefix + "│   ", depth + 1)
        if dirs:
            d = dirs[-1]
            # 如果还有文件
            if files or depth == max_depth:
                lines.append(f"{prefix}├── {d.name}/")
                walk(d, prefix + "│   ", depth + 1)
            else:
                lines.append(f"{prefix}└── {d.name}/")
                walk(d, prefix + "    ", depth + 1)

        # 显示文件（只显示关键文件，限制数量）
        important_files = [f for f in files if f.name in KEY_FILES]
        other_files = [f for f in files if f.name not in KEY_FILES]

        display_files = important_files + other_files[:15]  # 最多15个其他文件
        for f in display_files[:-1]:
            lines.append(f"{prefix}├── {f.name}")
        if display_files:
            f = display_files[-1]
            is_last = not dirs
            lines.append(f"{'    ' if not is_last else prefix}└── {f.name}")

    walk(root)
    return "\n".join(lines)


def _read_key_files(root: Path) -> dict[str, str]:
    """读取关键文件内容"""
    contents = {}

    for pattern in KEY_FILES:
        matches = list(root.glob(f"**/{pattern}"))
        for match in matches[:2]:  # 每种最多读2个
            # 限制文件大小
            try:
                text = match.read_text(encoding="utf-8", errors="ignore")
                if len(text) > 8000:
                    text = text[:8000] + "\n... (文件过大，已截断)"
                rel_path = str(match.relative_to(root))
                contents[rel_path] = text
            except Exception:
                continue

    return contents


def _build_analysis_prompt(repo_url: str, dir_tree: str, files: dict[str, str]) -> str:
    """构建分析 prompt"""
    files_text = ""
    for path, content in files.items():
        lang_hint = ""
        if path.endswith(".py"): lang_hint = "python"
        elif path.endswith(".js") or path.endswith(".ts"): lang_hint = "javascript"
        elif path.endswith(".rs"): lang_hint = "rust"
        elif path.endswith(".go"): lang_hint = "go"
        elif path.endswith(".md"): lang_hint = "markdown"
        elif path.endswith(".toml") or path.endswith(".yaml") or path.endswith(".yml"): lang_hint = "config"

        files_text += f"\n### {path}\n```{lang_hint}\n{content}\n```\n"

    return f"""你是一位资深软件架构师和技术文档专家。请深度分析以下开源项目。

## 项目地址
{repo_url}

## 目录结构
{dir_tree}

## 关键文件内容
{files_text}

请返回严格的 JSON 格式（不要 markdown 代码块包裹），包含以下内容：

{{
  "overview": {{
    "name_cn": "项目中文名称",
    "one_liner": "一句话描述（30字以内）",
    "what_is_it": "这个项目是什么，解决了什么问题（100字以内）",
    "tech_stack": ["技术1", "技术2"],
    "license": "许可证类型（如果能看出来）"
  }},
  "architecture": {{
    "diagram": "用 Mermaid flowchart 语法画的架构图（TB方向）",
    "description": "架构说明（200字以内）",
    "core_modules": [
      {{"name": "模块名", "path": "文件路径", "role": "模块职责说明"}}
    ]
  }},
  "workflow": {{
    "steps": [
      {{"step": 1, "title": "步骤标题", "action": "做什么", "command": "命令（如有）", "input": "输入", "output": "输出"}}
    ],
    "typical_usage": "典型使用流程描述（200字以内）"
  }},
  "key_features": ["特性1", "特性2", "特性3"],
  "getting_started": {{
    "prerequisites": ["先决条件1", "先决条件2"],
    "install": "安装命令",
    "quick_start": "快速开始命令或步骤"
  }},
  "code_highlights": [
    {{"file": "文件路径", "what": "这段代码做了什么", "why_interesting": "为什么值得关注"}}
  ],
  "suitable_for": ["适合谁1", "适合谁2"],
  "similar_projects": ["类似项目1", "类似项目2"],
  "pros": ["优点1", "优点2"],
  "cons": ["不足1", "不足2"],
  "verdict": "综合评价（50字以内）"
}}"""


async def analyze_repo(repo_url: str) -> Path | None:
    """
    深度分析一个 GitHub 仓库
    返回生成的报告文件路径
    """
    # 从 URL 提取仓库名
    repo_name = repo_url.rstrip("/").split("/")[-1]
    repo_name = repo_name.replace(".git", "")

    print(f"\n🔬 深度分析: {repo_name}")
    print(f"   {repo_url}")
    print()

    # 1. Clone
    print("[1/4] 克隆仓库...")
    tmp_dir = Path(tempfile.mkdtemp(prefix="ai_assistant_"))
    repo_dir = tmp_dir / repo_name

    if not _clone_repo(repo_url, repo_dir):
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return None
    print(f"  ✅ 已克隆到: {repo_dir}")

    # 2. 收集信息
    print("[2/4] 读取项目结构...")
    dir_tree = _build_dir_tree(repo_dir)
    key_files = _read_key_files(repo_dir)
    print(f"  📂 目录: {len(dir_tree.splitlines())} 行")
    print(f"  📄 关键文件: {len(key_files)} 个")

    # 3. AI 分析
    print("[3/4] DeepSeek 分析中（长上下文，可能需要1-2分钟）...")
    prompt = _build_analysis_prompt(repo_url, dir_tree, key_files)
    # 估算 token 数
    estimated_tokens = len(prompt) // 3  # 粗略：英文1 token ≈ 4 char，中文 ≈ 2 char
    print(f"  📊 分析素材约 {estimated_tokens:,} tokens")

    response = _call_ai(prompt, max_tokens=8000)
    if not response:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return None

    # 解析 JSON
    import json
    try:
        response = response.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[1]
            if response.endswith("```"):
                response = response[:-3]
        analysis = json.loads(response)
    except json.JSONDecodeError as e:
        print(f"  ⚠️ JSON解析失败: {e}，使用原文")
        analysis = {"raw_response": response}

    # 4. 生成报告
    print("[4/4] 生成深度分析报告...")
    report_path = _generate_report(repo_name, repo_url, analysis)

    # 清理
    shutil.rmtree(tmp_dir, ignore_errors=True)
    print(f"  🧹 已清理临时文件")

    return report_path


def _generate_report(repo_name: str, repo_url: str, analysis: dict) -> Path:
    """生成 Markdown 报告"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append(f"# 🔬 深度分析: {analysis.get('overview', {}).get('name_cn', repo_name)}")
    lines.append("")
    lines.append(f"> 📎 [{repo_url}]({repo_url})")
    lines.append(f"> 📅 分析日期: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")

    overview = analysis.get("overview", {})
    if overview:
        lines.append("## 📋 项目概览")
        lines.append("")
        lines.append(f"**{overview.get('one_liner', '')}**")
        lines.append("")
        if overview.get("what_is_it"):
            lines.append(f"{overview['what_is_it']}")
            lines.append("")
        tech_stack = overview.get("tech_stack", [])
        if tech_stack:
            lines.append(f"**技术栈**: {' · '.join(tech_stack)}")
            lines.append("")

    # 架构图
    arch = analysis.get("architecture", {})
    if arch.get("diagram"):
        lines.append("## 🏗️ 架构")
        lines.append("")
        lines.append("```mermaid")
        lines.append(arch["diagram"])
        lines.append("```")
        lines.append("")
    if arch.get("description"):
        lines.append(arch["description"])
        lines.append("")
    if arch.get("core_modules"):
        lines.append("### 核心模块")
        lines.append("")
        for m in arch["core_modules"]:
            lines.append(f"| `{m.get('path', '?')}` | {m.get('name', '?')} | {m.get('role', '?')} |")
        # 重新输出为表格
        lines[-1] = ""  # 移除最后一行，改用表格格式
        lines.append("| 文件 | 模块 | 职责 |")
        lines.append("|------|------|------|")
        for m in arch["core_modules"]:
            lines.append(f"| `{m.get('path', '?')}` | {m.get('name', '?')} | {m.get('role', '?')} |")
        lines.append("")

    # 工作流
    workflow = analysis.get("workflow", {})
    if workflow.get("steps"):
        lines.append("## 🔄 工作流")
        lines.append("")
        for s in workflow["steps"]:
            step_num = s.get("step", "?")
            title = s.get("title", "")
            action = s.get("action", "")
            command = s.get("command", "")
            input_ = s.get("input", "")
            output_ = s.get("output", "")

            lines.append(f"### 步骤 {step_num}: {title}")
            lines.append("")
            lines.append(f"- **操作**: {action}")
            if command:
                lines.append(f"- **命令**: `{command}`")
            if input_:
                lines.append(f"- **输入**: {input_}")
            if output_:
                lines.append(f"- **输出**: {output_}")
            lines.append("")

    if workflow.get("typical_usage"):
        lines.append("### 典型使用流程")
        lines.append("")
        lines.append(workflow["typical_usage"])
        lines.append("")

    # 快速开始
    getting_started = analysis.get("getting_started", {})
    if getting_started:
        lines.append("## 🚀 快速开始")
        lines.append("")
        prereqs = getting_started.get("prerequisites", [])
        if prereqs:
            lines.append("**先决条件**:")
            for p in prereqs:
                lines.append(f"- {p}")
            lines.append("")
        if getting_started.get("install"):
            lines.append(f"**安装**:")
            lines.append(f"```bash")
            lines.append(f"{getting_started['install']}")
            lines.append(f"```")
            lines.append("")
        if getting_started.get("quick_start"):
            lines.append(f"**快速开始**:")
            lines.append(f"```bash")
            lines.append(f"{getting_started['quick_start']}")
            lines.append(f"```")
            lines.append("")

    # 关键特性
    features = analysis.get("key_features", [])
    if features:
        lines.append("## ✨ 关键特性")
        lines.append("")
        for f in features:
            lines.append(f"- {f}")
        lines.append("")

    # 代码亮点
    highlights = analysis.get("code_highlights", [])
    if highlights:
        lines.append("## 💡 代码亮点")
        lines.append("")
        for h in highlights:
            lines.append(f"- **`{h.get('file', '?')}`**: {h.get('what', '')}")
            if h.get("why_interesting"):
                lines.append(f"  > {h['why_interesting']}")
        lines.append("")

    # 评价
    lines.append("## 📊 综合评价")
    lines.append("")

    pros = analysis.get("pros", [])
    cons = analysis.get("cons", [])
    if pros:
        lines.append("**优点**:")
        for p in pros:
            lines.append(f"- ✅ {p}")
        lines.append("")
    if cons:
        lines.append("**不足**:")
        for c in cons:
            lines.append(f"- ⚠️ {c}")
        lines.append("")

    if analysis.get("verdict"):
        lines.append(f"> **结论**: {analysis['verdict']}")
        lines.append("")

    suitable = analysis.get("suitable_for", [])
    if suitable:
        lines.append("**适合人群**: " + " · ".join(suitable))
        lines.append("")

    similar = analysis.get("similar_projects", [])
    if similar:
        lines.append("**类似项目**: " + " · ".join(similar))
        lines.append("")

    lines.append("---")
    lines.append(f"📬 由 AI信息助手 深度分析模块生成")

    file_path = OUTPUT_DIR / f"{repo_name}-{__import__('datetime').datetime.now().strftime('%Y%m%d')}.md"
    file_path.write_text("\n".join(lines), encoding="utf-8")

    return file_path
