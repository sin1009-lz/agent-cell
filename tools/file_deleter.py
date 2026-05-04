"""文件删除工具 —— 删除指定文件"""

import os


def file_deleter(file_path: str) -> tuple[str, bool]:
    """文件删除工具 —— 删除指定路径的文件"""
    try:
        if not os.path.isfile(file_path):
            return f"错误：文件不存在 —— {file_path}", False
        os.remove(file_path)
        return f"删除成功：{file_path}", True
    except Exception as e:
        return f"错误：删除文件失败 —— {e}", False
