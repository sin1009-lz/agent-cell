"""工具模块 —— 每个工具独立一个文件，统一接口：接收参数，返回(结果文本, 是否成功)"""

import os


def file_reader(file_path: str) -> tuple[str, bool]:
    """文件读取工具 —— 读取指定文件内容"""
    try:
        if not os.path.isfile(file_path):
            return f"错误：文件不存在 —— {file_path}", False
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content, True
    except Exception as e:
        return f"错误：读取文件失败 —— {e}", False
