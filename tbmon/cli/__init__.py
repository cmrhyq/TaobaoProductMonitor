"""命令行工具（开发者排障用，非业务入口）。

    python -m tbmon login
    python -m tbmon fetch "https://e.tb.cn/h.xxx?tk=yyy"

- `main.py`    argparse 装配与命令分派
- `render.py`  终端渲染
"""

from __future__ import annotations

from .main import EXIT_AUTH, EXIT_FAIL, EXIT_OK, EXIT_RISK, build_parser, main

__all__ = ["EXIT_AUTH", "EXIT_FAIL", "EXIT_OK", "EXIT_RISK", "build_parser", "main"]
