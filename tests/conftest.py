"""pytest 公共配置。

路径注入已交给 `pyproject.toml` 的 `[tool.pytest.ini_options] pythonpath = ["."]`，
本文件只保留真正全局的 fixture。
"""

from __future__ import annotations
