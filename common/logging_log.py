"""
@File logging_log.py
@Contact cmrhyq@163.com
@License (C)Copyright 2022-2025, AlanHuang
@Modify Time 2024/9/10 下午2:15
@Author Alan Huang
@Version 0.0.1
@Description None
"""
from __future__ import annotations

import sys
import logging
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler


class ColorStreamHandler(logging.StreamHandler):
    """
    console color
    定义终端彩色日志处理器，不影响日志文件中记录的内容
    """
    COLOR_CODES = {
        logging.DEBUG: "\033[1;34m",  # Blue
        logging.INFO: "\033[1;37m",  # White
        logging.WARNING: "\033[1;33m",  # Yellow
        logging.ERROR: "\033[1;31m",  # Red
        logging.CRITICAL: "\033[1;41m"  # Red with background
    }
    RESET_CODE = "\033[0m"

    # html color
    # COLOR_CODES = {
    #     logging.DEBUG: "<span style='color:blue'>",  # Blue
    #     logging.INFO: "<span style='color:white'>",  # White
    #     logging.WARNING: "<span style='color:yellow'>",  # Yellow
    #     logging.ERROR: "<span style='color:red'>",  # Red
    #     logging.CRITICAL: "<span style='color:blue'>"  # Red with background
    # }
    # RESET_CODE = "</span>"
    def emit(self, record):
        try:
            message = self.format(record)
            self.stream.write(self.COLOR_CODES.get(record.levelno, "") + message + self.RESET_CODE)
            self.stream.write("\n")
            self.stream.flush()
        except Exception:
            self.handleError(record)


class MyLogger(logging.Logger):
    def __init__(self, tag, level=logging.DEBUG, colorful: bool = False,
                 name: str | None = 'run_logs',
                 save_pth: str | Path = Path.cwd() / 'logs',
                 existing_counts: int = 14):
        """
        参数解释：
        :param tag: 用于区分MyLogger对象，相当于命名空间，不同命名空间里的参数配置也不同，避免多个实例之间的冲突
        :param level: 仅输出大于等于该级别的日志，日志记录级别--DEBUG < INFO < WARNING < ERROR < CRITICAL
        :param colorful: 是否以彩色文本输出至控制台
        :param name: 日志文件的名称，None则不保存
        :param save_pth: 日志文件保存路径， None则不记录日志
        :param existing_counts: 日志文件保存的个数，默认14个，按照天划分文件，即默认存2周
        """
        super().__init__(tag, level=level)
        # 日志输出格式: 时间(默认毫秒级)+级别(-7代表左对齐，输出固定长度7)+位置+信息
        """
        asctime - 时间
        levelname - 日志级别
        pathname - 记录日志的位置
        filename - 记录日志的文件名
        lineno - 文件中记录日志的行号
        funcName - 文件中记录日志的函数名称
        """
        fmt = "%(asctime)s | %(levelname)-8s | %(pathname)s::%(funcName)s:%(lineno)d | %(message)s"
        formatter = logging.Formatter(fmt, datefmt='%Y-%m-%d %H:%M:%S')
        # 保存日志: 格式，路径，保存天数
        name and self._save_log(formatter, name, save_pth, existing_counts)
        """
        输出流句柄StreamHandler,默认无颜色输出至console,即sys.stdout;
        若想对不同级别的日志进行颜色区分，应当自定义输出流类，继承StreamHandler
        """
        ch = logging.StreamHandler(stream=sys.stdout) if not colorful else ColorStreamHandler(stream=sys.stdout)
        ch.setFormatter(formatter)
        self.addHandler(ch)

    def _save_log(self, formatter: logging.Formatter,
                  filename: str,
                  save_pth: str | Path,
                  existing_counts: int):
        # Path.mkdir中的参数: parents和exist_ok均为True，即创建所有父目录，且已存在时不报错
        not Path(save_pth).exists() and Path(save_pth).mkdir(parents=True, exist_ok=True)
        file = f'{save_pth}/{filename}'
        """文件流句柄TimedRotatingFileHandler的参数介绍:
        :param when: 参数设置为"midnight"，表示午夜（凌晨）作为切分日志文件的时间点; H, M, S, D时分秒天，都是以最后一次记录日志为起点计算，
                     即最后一次记录日志后，等待interval个时分秒天，这期间没有新的日志记录，那么下一次记录时，划分日志文件； W0-W6为周一到周日，
                     此时，interval参数无效
        :param interval: 参数设置为1，表示每1个midnight生成一个日志文件;
        :param backupCount: 参数设置为7，表示最多保留7个日志文件，由于是按照天进行划分，因此等同于日志文件仅保留7天.
        :param delay: 参数设置为True，表示延迟日志文件的切分，例：假设最后一次记录日志后，到了切分文件的时间点，并不会将日志文件进行切分，
                      而是延迟到下一次记录日志的时候，把旧日志文件重新命名，再重新记录新的日志文件；如果delay=False，那么会在记录日志时，立马对日志文件进行切分，
                      但是往文件中写入日志与重命名日志文件时同时进行的，就会引发PermissionError，所以必须要设置为True，先写入日志文件，下一次写入时，
                      将上一次的先重命名，再重新写入
        """
        fh = TimedRotatingFileHandler(file, when="midnight", interval=1, backupCount=existing_counts,
                                      delay=True, encoding='utf8')
        fh.suffix = "%Y-%m-%d.logs"  # 切分日志时，给旧日志文件添加的后缀, 命名方式修改为由.namer决定
        fh.setFormatter(formatter)
        # 设置切分后的日志文件名格式
        # time_fmt = datetime.now().strftime(f"%Y-%m-%d-%H%M")
        # fh.namer = lambda name: name.split(".")[0] + f"-{time_fmt}" + ".logs"
        self.addHandler(fh)


if __name__ == '__main__':
    log = MyLogger(tag='mylog', colorful=True, save_pth="../logs", existing_counts=7)
    log.debug('fff')
    log.info('ggg')
    log.warning('hhh')
    log.error('iii')
