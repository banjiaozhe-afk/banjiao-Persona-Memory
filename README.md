# Persona Memory

一个本地运行的 Python 人格与长期记忆库：把稳定人格、当前状态、对话摘要、相关记忆和最近对话分层组装为有长度上限的模型上下文。

## 功能

- JSON 人格配置与字段校验。
- SQLite 长期记忆新增、查询、更正、删除和持久化。
- 按主体隔离记忆；未指定主体时只检索 `global` 记忆。
- 词法相关度、重要性、新近度、可信度和主体匹配综合排序。
- 跨全局/主体记忆内容去重。
- 对常见密码、密钥、令牌和身份证号写法执行写入拦截。
- 将记忆、摘要、历史和当前消息标记为不可信资料，降低提示词覆盖风险。
- 按字符预算依次裁减低分记忆、较旧对话、摘要和状态；核心人格与当前消息过大时明确报错。
- 命令行和 Python API；运行时仅使用 Python 标准库。

## 环境与安装

需要 Python 3.11 或更高版本。本项目已在 Python 3.13.14 上实测，不需要 GPU 或模型服务；安装构建依赖时需要网络，运行时已安装的项目不需要网络。

先获取源码：

```powershell
git clone https://github.com/banjiaozhe-afk/banjiao-Persona-Memory.git
cd banjiao-Persona-Memory
```

在 Windows PowerShell 的项目根目录执行：

```powershell
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --proxy "" -e .
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

editable 安装只安装当前项目，没有第三方运行依赖。后续命令中的 `python` 均可替换为 `.venv` 中的解释器；也可以激活虚拟环境后直接运行 `persona-memory`。

## 立即运行

不写入数据库的隔离示例：

```powershell
& .\.venv\Scripts\python.exe -m persona_memory demo
```

输出是 JSON，包含 `prompt` 和 `characters`、`used_memory_ids`、`dropped_turns` 等元数据。`prompt` 中应能看到“小织”人格、恐怖游戏偏好和“未经信任的参考资料”边界。

校验人格文件：

```powershell
& .\.venv\Scripts\python.exe -m persona_memory validate
```

## 记忆管理

以下示例默认使用 `output/memories.db` 和 `config/persona.json`；数据库目录会自动创建，数据库文件被 Git 忽略。

```powershell
$pm = ".\.venv\Scripts\python.exe"

# 明确写入一条观众偏好
& $pm -m persona_memory add "喜欢合作解谜游戏" --subject "viewer:001" --category preference --importance 0.8 --source "chat:123"

# 只检索该观众与全局记忆
& $pm -m persona_memory search "今晚玩解谜游戏吗" --subject "viewer:001"

# 列出、纠正、删除
& $pm -m persona_memory list --subject "viewer:001"
& $pm -m persona_memory update 1 --content "现在更喜欢合作建造游戏"
& $pm -m persona_memory delete 1
```

删除是永久操作。`update` 和 `delete` 对不存在的 ID 会返回退出码 2，不会静默成功。

## 组装模型上下文

```powershell
& $pm -m persona_memory build "推荐一个解谜游戏" `
  --subject "viewer:001" `
  --state '{"scene":"game_selection"}' `
  --summary "本场正在讨论下一场游戏。" `
  --turn "user:上一场结束了" `
  --turn "assistant:接下来想玩什么类型？" `
  --max-chars 6000 --max-memories 5 --max-turns 8
```

输出的 `prompt` 可交给上层应用所选 LLM。`--max-memories 0` 可完全关闭长期记忆注入。这里限制的是**字符数而不是模型 token 数**；接入具体模型时，上层应按该模型的 tokenizer 另做 token 预算。

未指定 `--subject` 时不会检索任何观众私有记忆，只检索 `global`，避免把其他观众的信息带入当前对话。

## 作为其他 Python 项目的模块

在目标项目的虚拟环境中直接安装这个仓库：

```powershell
python -m pip install --proxy "" "git+https://github.com/banjiaozhe-afk/banjiao-Persona-Memory.git"
```

然后按下文的 Python API 创建并复用 `SQLiteMemoryStore`、`MemoryRetriever` 和 `ContextBuilder`。主项目需要负责调用 LLM、保存原始对话、生成摘要，以及决定哪些候选事实值得写入长期记忆；本包不会自动执行这些动作。

建议用稳定用户 ID 构造 `subject`，例如 `viewer:001`。共同事件使用 `global`，观众私有信息使用各自的主体 ID。程序退出时关闭存储连接。

## Python API

```python
from persona_memory import (
    MemoryRetriever,
    SQLiteMemoryStore,
    Turn,
    load_persona,
)
from persona_memory.context import ContextBuilder

persona = load_persona("config/persona.json")
with SQLiteMemoryStore("output/memories.db") as store:
    store.add(
        "喜欢恐怖游戏，但不喜欢频繁跳吓",
        subject="viewer:001",
        category="preference",
        importance=0.8,
        source="chat:123",
    )
    memories = MemoryRetriever(store).search(
        "今晚玩恐怖游戏吗", subject="viewer:001"
    )
    context = ContextBuilder().build(
        persona=persona,
        current_message="今晚玩恐怖游戏吗",
        memories=memories,
        turns=[Turn("user", "上一场直播结束了")],
        summary="正在选择今晚的游戏。",
        state={"scene": "game_selection"},
    )
    print(context.prompt)
    print(context.metadata())
```

## 检索与预算口径

词法检索将英文/数字词和中文二元字组作为匹配单元，不是语义向量。综合分数权重为：相关度 0.65、重要性 0.15、新近度 0.10、可信度 0.05、主体匹配 0.05；没有词汇重叠的记忆不会被召回。每次检索最多扫描最新 10000 条候选记录。

上下文超限时按以下顺序裁剪：

1. 排名最低的长期记忆；
2. 最旧的历史对话；
3. 较早对话摘要；
4. 当前状态。

核心人格和当前消息不静默截断，预算不足会抛出 `ContextBudgetError`。

## 目录结构

| 路径 | 内容 |
|---|---|
| `src/persona_memory/models.py` | 人格、记忆、对话和结果数据模型 |
| `src/persona_memory/persona.py` | 人格文件加载与校验 |
| `src/persona_memory/store.py` | SQLite 持久化与 CRUD |
| `src/persona_memory/retrieval.py` | 主体隔离、相关度排序与去重 |
| `src/persona_memory/context.py` | 分层提示词和字符预算 |
| `src/persona_memory/security.py` | 敏感内容写入拦截 |
| `src/persona_memory/cli.py` | 命令行入口 |
| `config/persona.json` | 可修改的示例人格 |
| `tests/` | 单元和命令行流程测试 |
| `docs/决策记录.md` | 技术选择及代价 |

## 验证

```powershell
& .\.venv\Scripts\python.exe -m compileall -q src tests
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试覆盖人格错误、CRUD、持久化、重复记忆、敏感信息、主体隔离、检索去重、预算裁剪、提示词边界、CLI 正常流程与错误退出码。

## 已知限制

- 不包含 LLM 调用、自动记忆抽取、自动摘要、语音、Live2D、OBS 或直播平台接入。
- 词法检索不能理解充分改写后的同义表达；需要语义召回时应替换检索器，而不是把全部记忆注入上下文。
- 敏感信息规则是保守的常见格式拦截，不等同于完整的数据防泄漏系统。
- SQLite 适合本地单用户场景；多实例高并发写入需要独立存储层与并发验证。
