# Agent Cell

可并行运行的 LLM 交互执行体。

---

## 快速开始

```python
from agent_cell import AgentUnit, IOSchema, ExecutionConfig, RuntimeInput, VariableDef, InputVarType, OutputVarType

schema = IOSchema(
    name="翻译助手",
    input_variables=[
        VariableDef(type=InputVarType.ORIGINAL_TEXT.value, index=0),
    ],
    output_variables=[
        VariableDef(type=OutputVarType.ORIGINAL_TEXT.value, index=0),
        VariableDef(type=OutputVarType.COMPLETION_SIGNAL.value, index=1),
        VariableDef(type=OutputVarType.COMPLETION_TEXT.value, index=2),
        VariableDef(type=OutputVarType.ERROR_SIGNAL.value, index=3),
        VariableDef(type=OutputVarType.ERROR_CODE.value, index=4),
    ],
)

config = ExecutionConfig(
    prompt="你是一个翻译助手，把用户输入翻译成英文",
    model_name="deepseek-chat",
    base_url="https://api.deepseek.com",
    api_key="your-api-key",
    temperature=0.3,
)

agent = AgentUnit(schema, config)
output = agent.run(RuntimeInput(input_texts=["你好世界"], labels=["待翻译文本"]))
# LLM 实际收到：
#   system: "你是一个翻译助手，把用户输入翻译成英文"
#   user:   "【待翻译文本】\n你好世界"

print(output.output_variables[0])  # "Hello World"
print(output.output_variables[4])  # "0000"（正常）

# 旁入口：像聊天一样继续
reply = agent.follow_up("再翻一句Hello")
print(reply)  # "你好"

# 获取完整上下文
ctx = agent.get_context()
```

---

## 核心概念

### 三个角色

| 角色 | 类 | 作用 |
|------|-----|------|
| 定义变量 A | `IOSchema` | 声明入口和出口的类型与数量 |
| 定义变量 B | `ExecutionConfig` | 配置模型、提示词、工具、温度等 |
| 运行时输入 | `RuntimeInput` | 传入实际数据 + 标签 |

### 入口类型

| 类型 | 数据的 `type` 字段 | 说明 |
|------|-------------------|------|
| `original_text` | `"original_text"` | 文字输入 |
| `original_image` | `"original_image"` | 图片输入 |

`RuntimeInput.labels` 携带标签，Cell 以 `【标签】` 格式嵌入内容前发送：

```python
RuntimeInput(input_texts=["3.14", "sin(3.14)"], labels=["输入数值", "期望结果"])
# LLM 收到：【输入数值】\n3.14\n【期望结果】\nsin(3.14)
```

### 出口类型及名称

名称由 Cell 自动生成，格式：`{cell名}_{类型简写}_{序号}`。

| 类型 | 示例名称 | 值 |
|------|---------|-----|
| `original_text` | `翻译助手_text_0` | LLM 文字回复 |
| `tool_result` | `翻译助手_tool_0` | 工具调用记录（调用段落 + 回复段落） |
| `completion_signal` | `翻译助手_完成` | `True` / `False` |
| `completion_text` | `翻译助手_完成文本` | `"翻译助手执行完成"` 或 `""` |
| `error_signal` | `翻译助手_出错` | `True` / `False` |
| `error_code` | `翻译助手_错误码` | 4 位二进制字符串 |

> **规则**：出口必须含 `completion_signal`、`completion_text`、`error_signal`、`error_code`，排在最后。`error_signal = True` 时 `text_*` 全部为空、`tool_*` 全部为 `None`。

### 错误码

所有非 `completed` 状态均视为错误，`error_signal = True`。

| 状态 | 错误码 | 含义 |
|------|:--:|------|
| `completed` | `0000` | 正常结束 |
| `error` | `0001` | HTTP 异常 |
| `error` | `0010` | 网络异常 |
| `error` | `0011` | 请求异常 |
| `truncated` | `0100` | 循环达上限被截断 |
| `error` | `0101` | Token 超限 |

---

## 接口

| 方法 | 说明 |
|------|------|
| `agent.run(runtime_input) → RuntimeOutput` | 执行一次完整流程 |
| `agent.follow_up(text) → str` | 继续对话，返回 LLM 文字回复 |
| `agent.get_context() → list[dict]` | 获取完整对话上下文 |

### RuntimeOutput

```python
output = agent.run(...)
output.output_names      # ["翻译助手_text_0", "翻译助手_完成", "翻译助手_完成文本", "翻译助手_出错", "翻译助手_错误码"]
output.output_variables   # ["Hello World", True, "翻译助手执行完成", False, "0000"]
output.execution_status   # ExecutionStatus.COMPLETED
output.stats.total_tokens # int
```

### 并行

每个实例完全独立，创建多个即可并行。

---

## 工具与 MCP

### 内置工具

| 工具 | 功能 |
|------|------|
| `file_reader` | 读取文件内容 |
| `file_writer` | 写入文本到文件 |
| `file_deleter` | 删除文件 |
| `search_tool` | 搜索（占位） |

文件操作自动限制在 `cell_dir` 内。

### MCP 服务

```python
config = ExecutionConfig(mcp_servers=["weather", "filesystem"])
```

LLM 通过 `mcp_call` 工具调用服务，`server` 参数区分不同服务。

---

## 项目结构

```
agent_cell/
├── __init__.py
├── types.py             # 数据结构
├── agent_unit.py        # Agent 核心
├── llm_client.py        # LLM 调用、工具分发、循环控制
├── stats.py             # Token 统计
├── tools/
│   ├── file_reader.py
│   ├── file_writer.py
│   ├── file_deleter.py
│   └── search_tool.py
├── mcp/
│   └── mcp_handler.py
└── prompts/
    └── schema_generator.md
```

---

## 配置项

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `prompt` | str | `""` | 系统提示词 |
| `model_name` | str | `""` | 模型名称 |
| `base_url` | str | `""` | API 地址 |
| `api_key` | str | `""` | API 密钥 |
| `temperature` | float | `0.7` | 模型温度 |
| `max_loop_iterations` | int | `10` | 最大工具调用轮次 |
| `max_context_length` | int | `8192` | 上下文 token 上限 |
| `tools` | list[str] | `[]` | 启用的工具（白名单，空 = 不启用） |
| `mcp_servers` | list[str] | `[]` | 启用的 MCP 服务（白名单，空 = 不启用） |
| `cell_dir` | str | `""` | 工作目录 |
