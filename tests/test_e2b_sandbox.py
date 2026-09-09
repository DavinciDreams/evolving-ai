"""Contract tests for the asynchronous E2B sandbox integration."""

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from evolving_agent.integrations.e2b_sandbox import E2BSandbox


def _sdk_fixture(*, command_result=None):
    sandbox = MagicMock()
    sandbox.commands.run = AsyncMock(
        return_value=command_result
        or SimpleNamespace(stdout="ok", stderr="", exit_code=0)
    )
    sandbox.files.write = AsyncMock()
    sandbox.files.read = AsyncMock(return_value="contents")
    sandbox.kill = AsyncMock(return_value=True)

    async_sandbox = MagicMock()
    async_sandbox.create = AsyncMock(return_value=sandbox)
    module = SimpleNamespace(AsyncSandbox=async_sandbox)
    return module, async_sandbox, sandbox


async def test_run_code_uses_async_sdk_factory_and_cleans_up():
    module, async_sandbox, sandbox = _sdk_fixture()

    with patch.dict(sys.modules, {"e2b": module}):
        result = await E2BSandbox("synthetic-api-key").run_code(
            "print('hello')",
            timeout=30,
        )

    async_sandbox.create.assert_awaited_once_with(
        api_key="synthetic-api-key",
        timeout=40,
    )
    sandbox.commands.run.assert_awaited_once_with(
        'python3 -c "print(\'hello\')"',
        timeout=30,
    )
    sandbox.kill.assert_awaited_once_with()
    assert result == {"stdout": "ok", "stderr": "", "exit_code": 0}


async def test_run_code_cleans_up_when_command_fails():
    module, _, sandbox = _sdk_fixture()
    sandbox.commands.run.side_effect = RuntimeError("synthetic failure")

    with patch.dict(sys.modules, {"e2b": module}):
        result = await E2BSandbox("synthetic-api-key").run_command("false")

    sandbox.kill.assert_awaited_once_with()
    assert result == {"error": "synthetic failure"}


async def test_async_file_operations_create_and_close_sandboxes():
    write_module, write_factory, write_sandbox = _sdk_fixture()
    with patch.dict(sys.modules, {"e2b": write_module}):
        write_result = await E2BSandbox("synthetic-api-key").write_file(
            "/tmp/example.txt",
            "contents",
        )

    write_factory.create.assert_awaited_once_with(api_key="synthetic-api-key")
    write_sandbox.files.write.assert_awaited_once_with(
        "/tmp/example.txt",
        "contents",
    )
    write_sandbox.kill.assert_awaited_once_with()
    assert write_result == {"path": "/tmp/example.txt", "written": True}

    read_module, read_factory, read_sandbox = _sdk_fixture()
    with patch.dict(sys.modules, {"e2b": read_module}):
        read_result = await E2BSandbox("synthetic-api-key").read_file(
            "/tmp/example.txt"
        )

    read_factory.create.assert_awaited_once_with(api_key="synthetic-api-key")
    read_sandbox.files.read.assert_awaited_once_with("/tmp/example.txt")
    read_sandbox.kill.assert_awaited_once_with()
    assert read_result == {"path": "/tmp/example.txt", "content": "contents"}
