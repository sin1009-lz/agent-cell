"""Agent单元数据结构定义 —— 纯数据类，不包含业务逻辑"""

from dataclasses import dataclass, field
from enum import Enum


class InputVarType(Enum):
    """入口变量类型枚举"""
    ORIGINAL_TEXT = "original_text"    # 原文
    ORIGINAL_IMAGE = "original_image"  # 图片


class OutputVarType(Enum):
    """出口变量类型枚举"""
    ORIGINAL_TEXT = "original_text"          # LLM文字回复
    TOOL_RESULT = "tool_result"              # 工具调用记录
    COMPLETION_SIGNAL = "completion_signal"  # 完成信号
    ERROR_SIGNAL = "error_signal"            # 报错信号
    ERROR_CODE = "error_code"              # 错误码: 4位二进制 "0000"正常 "0001"HTTP "0010"网络 "0011"异常 "0100"截断 "0101"超限
    COMPLETION_TEXT = "completion_text"      # 完成文本: "{cell名称}执行完成"


class ExecutionStatus(Enum):
    """执行状态枚举"""
    COMPLETED = "completed"    # 正常完成
    TRUNCATED = "truncated"    # 达到循环上限被截断
    ERROR = "error"            # 发生异常


@dataclass
class VariableDef:
    """单个变量定义 —— 只定义类型和序号，名称由Cell自动生成或由标签携带"""
    type: str             # 类型，取值见 InputVarType / OutputVarType
    index: int            # 序号位置，从0开始


@dataclass
class IOSchema:
    """定义变量A：输入输出模式定义 —— 描述Agent的入口和出口结构"""
    name: str                          # Agent单元名称
    input_variables: list[VariableDef] = field(default_factory=list)   # 入口变量列表
    output_variables: list[VariableDef] = field(default_factory=list)  # 出口变量列表


@dataclass
class ExecutionConfig:
    """定义变量B：LLM执行配置 —— 描述调用模型、提示词、工具等参数"""
    prompt: str = ""                        # 系统提示词
    tools: list[str] = field(default_factory=list)        # 启用的工具名称列表，空列表=不启用任何工具
    mcp_servers: list[str] = field(default_factory=list)  # 启用的MCP服务名称列表，空列表=不启用
    max_context_length: int = 8192          # 最大上下文长度（token）
    temperature: float = 0.7                # 模型温度
    max_loop_iterations: int = 10           # 最大循环轮次，超出则截断
    model_name: str = ""                    # 模型名称
    base_url: str = ""                      # LLM API 地址
    api_key: str = ""                       # API 密钥
    cell_dir: str = ""                      # Cell工作目录，工具文件操作限制在此目录内


@dataclass
class RuntimeInput:
    """运行时入口变量 —— 数据内容 + 标签，与IOSchema.input_variables按index一一对应"""
    input_texts: list[str] = field(default_factory=list)    # 文字内容列表
    input_images: list[bytes] = field(default_factory=list)  # 图片内容列表
    labels: list[str] = field(default_factory=list)          # 标签列表，与变量一一对应


@dataclass
class ToolCallRecord:
    """工具调用记录 —— 一次工具交互的完整记录"""
    call_section: str = ""   # LLM发起工具调用的段落
    reply_section: str = ""  # Cell对工具调用的回复段落


@dataclass
class Stats:
    """执行统计信息"""
    total_input_tokens: int = 0    # 输入token总消耗
    total_output_tokens: int = 0   # 输出token总消耗
    model_call_count: int = 0      # 模型调用次数

    @property
    def total_tokens(self) -> int:
        """总token消耗 = 输入 + 输出"""
        return self.total_input_tokens + self.total_output_tokens


@dataclass
class RuntimeOutput:
    """运行时出口 —— Agent执行完毕后返回的完整结果"""
    output_variables: list = field(default_factory=list)   # 出口变量值列表，与IOSchema.output_variables对应
    output_names: list[str] = field(default_factory=list)  # Cell自动生成的变量名
    stats: Stats = field(default_factory=Stats)             # 统计信息
    execution_status: ExecutionStatus = ExecutionStatus.COMPLETED  # 执行状态
