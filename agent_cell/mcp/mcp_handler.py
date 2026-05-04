"""MCP服务模块 —— 统一封装MCP服务调用"""


class MCPHandler:
    """MCP服务处理器 —— 封装MCP服务的连接与调用，对外暴露统一接口"""

    call_history: list = []

    def __init__(self, server_name: str):
        self.server_name = server_name

    def call(self, method: str, params: dict = None) -> tuple[dict, bool]:
        """调用MCP服务方法，返回(结果数据, 是否成功)"""
        params = params or {}
        result = {
            "server": self.server_name,
            "method": method,
            "params": params,
            "result": "ok",
            "message": f"MCP服务 '{self.server_name}' 的 '{method}' 方法执行成功（模拟响应）"
        }
        MCPHandler.call_history.append(result)
        return result, True

    @classmethod
    def get_call_history(cls) -> list:
        """获取所有MCP调用历史记录"""
        return cls.call_history

    @classmethod
    def clear_history(cls):
        """清空调用历史"""
        cls.call_history.clear()
