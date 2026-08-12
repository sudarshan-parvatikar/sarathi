from __future__ import annotations

import json
import selectors
import subprocess
import time
from collections.abc import Iterator
from typing import Any


class CodexProtocolError(RuntimeError):
    pass


class CodexAppServer:
    """Small JSONL client for the documented Codex app-server protocol."""

    def __init__(self, command: tuple[str, ...] = ("codex", "app-server", "--listen", "stdio://"), timeout: float = 10.0) -> None:
        self.command = command
        self.timeout = timeout

    def _messages(self, process: subprocess.Popen[str], deadline: float) -> Iterator[dict[str, Any]]:
        if process.stdout is None:
            raise CodexProtocolError("app-server stdout unavailable")
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        while time.monotonic() < deadline:
            ready = selector.select(max(0.0, deadline - time.monotonic()))
            if not ready:
                break
            line = process.stdout.readline()
            if not line:
                break
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
        raise TimeoutError("timed out waiting for Codex app-server")

    def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        try:
            if process.stdin is None:
                raise CodexProtocolError("app-server stdin unavailable")
            requests = (
                {
                    "method": "initialize",
                    "id": 1,
                    "params": {
                        "clientInfo": {
                            "name": "sarathi",
                            "title": "Sarathi Work Controller",
                            "version": "0.1.0",
                        }
                    },
                },
                {"method": method, "id": 2, "params": params},
            )
            deadline = time.monotonic() + self.timeout
            process.stdin.write(json.dumps(requests[0]) + "\n")
            process.stdin.flush()
            messages = self._messages(process, deadline)
            initialized = next(message for message in messages if message.get("id") == 1)
            if "error" in initialized:
                raise CodexProtocolError(str(initialized["error"]))
            process.stdin.write(json.dumps(requests[1]) + "\n")
            process.stdin.flush()
            response = next(message for message in messages if message.get("id") == 2)
            if "error" in response:
                raise CodexProtocolError(str(response["error"]))
            return response.get("result", {})
        finally:
            if process.stdin:
                process.stdin.close()
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()

    def start_thread(self, cwd: str) -> str:
        result = self.call(
            "thread/start",
            {"cwd": cwd, "approvalPolicy": "never", "sandbox": "workspaceWrite", "serviceName": "sarathi"},
        )
        return str(result["thread"]["id"])

    def set_name(self, thread_id: str, name: str) -> None:
        self.call("thread/name/set", {"threadId": thread_id, "name": name})
