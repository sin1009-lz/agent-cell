"""Agent单元核心类 —— 接收定义变量、组装请求、调用LLM、打包输出"""

from .types import (
    IOSchema, ExecutionConfig, RuntimeInput, RuntimeOutput,
    InputVarType, OutputVarType, ExecutionStatus, ToolCallRecord, Stats
)
from .llm_client import LLMClient


class AgentUnit:
    """Agent单元 —— 无共享状态，每次执行独立，天然支持并行

    使用方式：
        schema = IOSchema(
            name="翻译助手",
            input_variables=[
                VariableDef(type=InputVarType.ORIGINAL_TEXT.value, index=0),
            ],
            output_variables=[
                VariableDef(type=OutputVarType.ORIGINAL_TEXT.value, index=0),
                VariableDef(type=OutputVarType.COMPLETION_SIGNAL.value, index=1),
                VariableDef(type=OutputVarType.ERROR_SIGNAL.value, index=2),
            ],
        )
        agent = AgentUnit(schema, config)
        output = agent.run(RuntimeInput(
            input_texts=["你好世界"],
            labels=["待翻译文本"],
        ))
        # 输出结束后可通过旁入口继续对话
        reply = agent.follow_up("再翻一句……")
    """

    def __init__(self, io_schema: IOSchema, exec_config: ExecutionConfig):
        self.io_schema = io_schema
        self.exec_config = exec_config
        self._client: LLMClient = None
        self._output_vars = sorted(self.io_schema.output_variables, key=lambda v: v.index)

    def run(self, runtime_input: RuntimeInput) -> RuntimeOutput:
        """执行一次完整的「接收输入 → 调用LLM → 打包输出」流程"""
        input_vars = sorted(self.io_schema.input_variables, key=lambda v: v.index)

        self._validate_input(runtime_input, input_vars)

        self._client = LLMClient(self.exec_config)
        raw_responses, status, error_code = self._client.run(runtime_input, input_vars)

        return self._make_output(raw_responses, status, error_code)

    def follow_up(self, text: str) -> str:
        """旁入口 —— 像对话一样发送消息，直接返回LLM的文字回复"""
        if self._client is None:
            raise RuntimeError("请先调用 run() 再使用 follow_up()")
        raw_responses, status, error_code = self._client.follow_up(text)
        output = self._make_output(raw_responses, status, error_code)
        if status == ExecutionStatus.ERROR:
            return f"[出错] {raw_responses[0]}" if raw_responses else "[出错] 未知错误"
        texts = [v for v, d in zip(output.output_variables, self._output_vars)
                 if d.type == OutputVarType.ORIGINAL_TEXT.value and isinstance(v, str) and v]
        return "\n\n".join(texts) if texts else ""

    def get_context(self) -> list[dict]:
        """获取当前完整对话上下文（messages列表）"""
        if self._client is None:
            return []
        return list(self._client.messages)

    def _make_output(self, raw_responses: list, status: ExecutionStatus, error_code: int = 0) -> RuntimeOutput:
        output_vars_data, output_names = self._package_output(raw_responses, status, self._output_vars, self.io_schema.name, error_code)
        return RuntimeOutput(
            output_variables=output_vars_data,
            output_names=output_names,
            stats=self._client.stats.stats if self._client else Stats(),
            execution_status=status,
        )

    def _validate_input(self, runtime_input: RuntimeInput, input_vars: list):
        """校验入口变量数量与定义一致"""
        expected_texts = sum(
            1 for v in input_vars
            if v.type != InputVarType.ORIGINAL_IMAGE.value
        )
        expected_images = sum(
            1 for v in input_vars
            if v.type == InputVarType.ORIGINAL_IMAGE.value
        )
        if len(runtime_input.input_texts) != expected_texts:
            raise ValueError(
                f"入口文本数量不匹配：期望{expected_texts}，实际{len(runtime_input.input_texts)}"
            )
        if len(runtime_input.input_images) != expected_images:
            raise ValueError(
                f"入口图片数量不匹配：期望{expected_images}，实际{len(runtime_input.input_images)}"
            )
        if len(runtime_input.labels) != len(input_vars):
            raise ValueError(
                f"标签数量不匹配：期望{len(input_vars)}，实际{len(runtime_input.labels)}"
            )

    def _package_output(self, raw_responses: list, status: ExecutionStatus, output_vars: list, cell_name: str, error_code: int = 0) -> tuple[list, list[str]]:
        """将LLM原始响应按output_variables定义打包，名称 = Cell名 + 类型 + 序号"""
        is_error = status != ExecutionStatus.COMPLETED

        text_responses = [] if is_error else [r for r in raw_responses if isinstance(r, str)]
        tool_records = [] if is_error else [r for r in raw_responses if isinstance(r, ToolCallRecord)]

        values = []
        names = []
        text_idx = 0
        tool_idx = 0
        text_count = 0
        tool_count = 0
        prefix = f"{cell_name}_" if cell_name else ""

        for var_def in output_vars:
            if var_def.type == OutputVarType.ORIGINAL_TEXT.value:
                names.append(f"{prefix}text_{text_count}")
                text_count += 1
                values.append(text_responses[text_idx] if text_idx < len(text_responses) else "")
                text_idx += 1
            elif var_def.type == OutputVarType.TOOL_RESULT.value:
                names.append(f"{prefix}tool_{tool_count}")
                tool_count += 1
                values.append(tool_records[tool_idx] if tool_idx < len(tool_records) else None)
                tool_idx += 1
            elif var_def.type == OutputVarType.COMPLETION_SIGNAL.value:
                names.append(f"{prefix}完成")
                values.append(status == ExecutionStatus.COMPLETED)
            elif var_def.type == OutputVarType.COMPLETION_TEXT.value:
                names.append(f"{prefix}完成文本")
                values.append(f"{cell_name}执行完成" if status == ExecutionStatus.COMPLETED else "")
            elif var_def.type == OutputVarType.ERROR_SIGNAL.value:
                names.append(f"{prefix}出错")
                values.append(status != ExecutionStatus.COMPLETED)
            elif var_def.type == OutputVarType.ERROR_CODE.value:
                names.append(f"{prefix}错误码")
                code = error_code if is_error else 0
                values.append(f"{code:04b}")
            else:
                names.append(f"{prefix}unknown")
                values.append(None)

        return values, names
