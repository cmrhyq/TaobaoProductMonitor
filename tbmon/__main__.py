"""`python -m tbmon` 的入口。

存在的意义：无桌面环境的服务端无法弹出扫码窗口，需要在本机执行
`python -m tbmon login` 生成登录态文件后再复制过去。
"""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
