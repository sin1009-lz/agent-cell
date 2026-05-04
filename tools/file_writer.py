"""文件写入工具 —— 将内容写入指定路径"""

import os


def file_writer(file_path: str, content: str) -> tuple[str, bool]:
    """文件写入工具 —— 将内容写入文件，自动创建父目录"""
    try:
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"写入成功：{file_path}（{len(content)} 字符）", True
    except Exception as e:
        return f"错误：写入文件失败 —— {e}", False
