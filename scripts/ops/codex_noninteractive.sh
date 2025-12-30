#!/usr/bin/env python
"""Pseudo-TTY Codex wrapper that feeds stdin payloads to `codex exec`."""

from __future__ import annotations

import os
import select
import sys
from typing import List


def main() -> int:
    for env_var in ("CODEX_SANDBOX", "CODEX_SANDBOX_NETWORK_DISABLED", "CODEX_INTERNAL_ORIGINATOR_OVERRIDE"):
        os.environ.pop(env_var, None)
    payload = sys.stdin.read()
    cmd: List[str] = ["codex", "exec", "--sandbox", "danger-full-access", "-"]
    pid, master_fd = os.forkpty()
    if pid == 0:
        os.execvp(cmd[0], cmd)
        os._exit(1)

    def _send(data: bytes) -> None:
        if data:
            os.write(master_fd, data)

    encoded = payload.encode("utf-8")
    _send(encoded)
    if not payload.endswith("\n"):
        _send(b"\n")
    _send(b"\x04")  # Ctrl-D

    child_status = None
    try:
        while True:
            rlist, _, _ = select.select([master_fd], [], [], 0.1)
            if master_fd in rlist:
                try:
                    chunk = os.read(master_fd, 1024)
                except OSError:
                    break
                if not chunk:
                    break
                os.write(sys.stdout.buffer.fileno(), chunk)
            if child_status is None:
                finished_pid, status = os.waitpid(pid, os.WNOHANG)
                if finished_pid == pid:
                    child_status = status
                    if not rlist:
                        break
    finally:
        os.close(master_fd)

    if child_status is None:
        _, child_status = os.waitpid(pid, 0)
    if os.WIFEXITED(child_status):
        return os.WEXITSTATUS(child_status)
    if os.WIFSIGNALED(child_status):
        return 128 + os.WTERMSIG(child_status)
    return 1


if __name__ == "__main__":
    sys.exit(main())
