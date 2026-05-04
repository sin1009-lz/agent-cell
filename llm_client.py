"""LLM调用客户端 —— 封装模型API调用、循环控制与截断处理"""

import json
import base64
import urllib.request
import urllib.error
import os
from .types import ExecutionConfig, RuntimeInput, ExecutionStatus, ToolCallRecord, InputVarType
from .stats import StatsCollector


TOOL_DEFINITIONS = {
    "file_reader": {
        "type": "function",
        "function": {
            "name": "file_reader",
            "description": "读取指定文件的内容，返回文件全部文本",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "要读取的文件路径"}
                },
                "required": ["file_path"]
            }
        }
    },
    "file_writer": {
        "type": "function",
        "function": {
            "name": "file_writer",
            "description": "将文本内容写入指定文件，自动创建父目录",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "要写入的文件路径"},
                    "content": {"type": "string", "description": "要写入的文本内容"}
                },
                "required": ["file_path", "content"]
            }
        }
    },
    "file_deleter": {
        "type": "function",
        "function": {
            "name": "file_deleter",
            "description": "删除指定的文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "要删除的文件路径"}
                },
                "required": ["file_path"]
            }
        }
    },
    "search_tool": {
        "type": "function",
        "function": {
            "name": "search_tool",
            "description": "执行搜索查询，返回搜索结果",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索查询内容"}
                },
                "required": ["query"]
            }
        }
    },
    "mcp_call": {
        "type": "function",
        "function": {
            "name": "mcp_call",
            "description": "调用MCP服务的方法",
            "parameters": {
                "type": "object",
                "properties": {
                    "server": {"type": "string", "description": "MCP服务名称"},
                    "method": {"type": "string", "description": "要调用的方法名"},
                    "params": {"type": "object", "description": "方法参数，JSON对象"}
                },
                "required": ["server", "method"]
            }
        }
    }
}


def _ensure_in_cell_dir(file_path: str, cell_dir: str) -> str:
    """确保文件路径在cell_dir范围内，返回规范化后的路径"""
    if not cell_dir:
        return os.path.abspath(file_path)
    cell_dir = os.path.abspath(cell_dir)
    abs_path = os.path.abspath(file_path)
    if not abs_path.lower().startswith(cell_dir.lower()):
        abs_path = os.path.join(cell_dir, os.path.basename(file_path) or "untitled")
    return abs_path


def _execute_tool(tool_name: str, arguments: dict, cell_dir: str) -> str:
    """执行工具调用，返回结果文本"""
    try:
        if tool_name == "file_reader":
            file_path = _ensure_in_cell_dir(arguments.get("file_path", ""), cell_dir)
            from .tools.file_reader import file_reader
            result, _ = file_reader(file_path)
            return result

        elif tool_name == "file_writer":
            file_path = _ensure_in_cell_dir(arguments.get("file_path", ""), cell_dir)
            content = arguments.get("content", "")
            from .tools.file_writer import file_writer
            result, _ = file_writer(file_path, content)
            return result

        elif tool_name == "file_deleter":
            file_path = _ensure_in_cell_dir(arguments.get("file_path", ""), cell_dir)
            from .tools.file_deleter import file_deleter
            result, _ = file_deleter(file_path)
            return result

        elif tool_name == "search_tool":
            query = arguments.get("query", "")
            from .tools.search_tool import search_tool
            result, _ = search_tool(query)
            return result

        elif tool_name == "mcp_call":
            server = arguments.get("server", "")
            method = arguments.get("method", "")
            params = arguments.get("params", {})
            from .mcp.mcp_handler import MCPHandler
            handler = MCPHandler(server)
            result, _ = handler.call(method, params)
            return json.dumps(result, ensure_ascii=False)

        else:
            return f"错误：未知工具 —— {tool_name}"
    except Exception as e:
        return f"错误：工具执行异常 —— {e}"


class LLMClient:
    """LLM调用客户端 —— 保持对话上下文，支持首次运行和后续继续"""

    def __init__(self, config: ExecutionConfig):
        self.config = config
        self.stats = StatsCollector()
        self.messages: list[dict] = []
        self.tool_defs: list[dict] = []

    def run(self, runtime_input: RuntimeInput, input_variables: list = None) -> tuple[list, ExecutionStatus, int]:
        """首次执行 —— 构建初始消息并启动对话循环"""
        self.messages = self._build_initial_messages(runtime_input, input_variables or [])
        self.tool_defs = self._get_tool_definitions()
        return self._execute_loop()

    def follow_up(self, text: str) -> tuple[list, ExecutionStatus, int]:
        """旁入口 —— 在已有对话基础上追加一条用户消息，继续执行"""
        self.messages.append({"role": "user", "content": text})
        return self._execute_loop()

    def _execute_loop(self) -> tuple[list, ExecutionStatus, int]:
        """对话循环 —— 调用API、执行工具、收集响应"""
        responses: list = []
        loop_count = 0
        finished = False

        while loop_count < self.config.max_loop_iterations and not finished:
            self.stats.add_call()

            response_data, error, error_code = self._call_api(self.messages, self.tool_defs)

            if error:
                responses.append(f"[ERROR] {error}")
                return responses, ExecutionStatus.ERROR, error_code

            choice = response_data.get("choices", [{}])[0]
            message = choice.get("message", {})
            finish_reason = choice.get("finish_reason", "stop")

            input_tokens = response_data.get("usage", {}).get("prompt_tokens", 0)
            output_tokens = response_data.get("usage", {}).get("completion_tokens", 0)
            self.stats.add_input_tokens(input_tokens)
            self.stats.add_output_tokens(output_tokens)

            if finish_reason == "tool_calls" and message.get("tool_calls"):
                tool_calls = message["tool_calls"]
                assistant_msg = {
                    "role": "assistant",
                    "content": message.get("content"),
                    "tool_calls": tool_calls,
                }
                if message.get("reasoning_content"):
                    assistant_msg["reasoning_content"] = message["reasoning_content"]
                self.messages.append(assistant_msg)

                for tc in tool_calls:
                    func_name = tc["function"]["name"]
                    try:
                        func_args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        func_args = {}

                    tool_result = _execute_tool(func_name, func_args, self.config.cell_dir)

                    record = ToolCallRecord(
                        call_section=f"[LLM] 调用工具: {func_name}({json.dumps(func_args, ensure_ascii=False)})",
                        reply_section=f"[Cell] 工具 {func_name} 返回: {tool_result}"
                    )
                    responses.append(record)

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": tool_result
                    })

            else:
                content = message.get("content", "")
                if content:
                    responses.append(content)
                finished = True

            loop_count += 1

        if finished:
            return responses, ExecutionStatus.COMPLETED, 0
        else:
            return responses, ExecutionStatus.TRUNCATED, 4

    def _build_initial_messages(self, runtime_input: RuntimeInput, input_variables: list) -> list[dict]:
        """构建初始消息列表 —— 按input_variables顺序交织文字与图片，附带标签"""
        messages = []
        if self.config.prompt:
            messages.append({"role": "system", "content": self.config.prompt})

        text_idx = 0
        image_idx = 0
        label_idx = 0
        content_parts = []

        for var_def in input_variables:
            label = runtime_input.labels[label_idx] if label_idx < len(runtime_input.labels) else ""
            if var_def.type == InputVarType.ORIGINAL_TEXT.value:
                if text_idx < len(runtime_input.input_texts) and runtime_input.input_texts[text_idx]:
                    text = runtime_input.input_texts[text_idx]
                    if label:
                        text = f"【{label}】\n{text}"
                    content_parts.append({"type": "text", "text": text})
                text_idx += 1
            elif var_def.type == InputVarType.ORIGINAL_IMAGE.value:
                if image_idx < len(runtime_input.input_images):
                    if label:
                        content_parts.append({"type": "text", "text": f"【{label}】"})
                    img_b64 = base64.b64encode(runtime_input.input_images[image_idx]).decode("utf-8")
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"}
                    })
                image_idx += 1
            label_idx += 1

        if content_parts:
            if len(content_parts) == 1 and content_parts[0]["type"] == "text":
                messages.append({"role": "user", "content": content_parts[0]["text"]})
            else:
                messages.append({"role": "user", "content": content_parts})

        return messages

    def _get_tool_definitions(self) -> list[dict]:
        """获取本次执行启用的工具定义列表"""
        tool_defs = []
        for name in self.config.tools:
            if name in TOOL_DEFINITIONS:
                tool_defs.append(TOOL_DEFINITIONS[name])
        if self.config.mcp_servers and "mcp_call" not in self.config.tools:
            tool_defs.append(TOOL_DEFINITIONS["mcp_call"])
        return tool_defs

    def _call_api(self, messages: list[dict], tools: list[dict]) -> tuple[dict, str, int]:
        """调用LLM API，返回(响应数据, 错误信息, 错误码)"""
        url = f"{self.config.base_url.rstrip('/')}/v1/chat/completions"
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_context_length,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body), "", 0
        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                pass
            if any(kw in error_body.lower() for kw in ("context_length", "token limit", "max token", "too long")):
                return {}, f"Token超限: {error_body}", 5
            return {}, f"HTTP {e.code}: {error_body}", 1
        except urllib.error.URLError as e:
            return {}, f"网络错误: {e.reason}", 2
        except Exception as e:
            return {}, f"请求异常: {e}", 3
