"""Token统计模块 —— 累计输入输出token和调用次数"""

from .types import Stats


class StatsCollector:
    """统计收集器 —— 在LLM交互过程中累计token消耗与调用次数"""

    def __init__(self):
        self._stats = Stats()

    def add_input_tokens(self, count: int):
        """累加输入token"""
        self._stats.total_input_tokens += count

    def add_output_tokens(self, count: int):
        """累加输出token"""
        self._stats.total_output_tokens += count

    def add_call(self):
        """模型调用次数+1"""
        self._stats.model_call_count += 1

    @property
    def stats(self) -> Stats:
        """获取当前统计快照"""
        return self._stats
