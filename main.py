"""
Application entry point (backward-compatible).
Delegates to CLI for scheduling. Use `python cli.py` for full command set.
"""

from cli import cli

if __name__ == "__main__":
    cli(["run", "--schedule"], standalone_mode=False)
