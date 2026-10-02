"""`bitcraft` command and window launcher (no real windows are spawned)."""

import sys

import pytest

from bitcraft import __version__, cli, launcher


class _Spawn:
    """Records Popen calls instead of starting processes."""

    def __init__(self) -> None:
        self.calls: list[tuple[list, dict]] = []

    def __call__(self, cmd, **kwargs):
        self.calls.append((list(cmd), kwargs))
        return object()


@pytest.fixture
def spawn(monkeypatch):
    recorder = _Spawn()
    monkeypatch.setattr(launcher.subprocess, "Popen", recorder)
    return recorder


@pytest.fixture
def launched(monkeypatch):
    """Capture what the CLI would open instead of opening it."""
    seen: list[launcher.Options] = []
    monkeypatch.setattr(cli, "open_window", lambda opts: seen.append(opts) or "test terminal")
    return seen


def test_bare_command_opens_new_window(launched, capsys) -> None:
    assert cli.main([]) == 0
    assert launched[0].source == "auto" and launched[0].size == launcher.DEFAULT_SIZE
    assert "new test terminal window" in capsys.readouterr().out


def test_flags_without_subcommand_mean_run(launched) -> None:
    cli.main(["--demo", "--size", "200x60"])
    assert launched[0].source == "demo" and launched[0].size == (200, 60)


def test_demo_subcommand_and_api_url(launched) -> None:
    cli.main(["demo"])
    cli.main(["run", "--api", "--api-url", "http://box:9000"])
    assert launched[0].source == "demo"
    assert launched[1].source == "api" and launched[1].api_url == "http://box:9000"


def test_rejects_tiny_window() -> None:
    with pytest.raises(SystemExit):
        cli.main(["run", "--size", "80x24"])


def test_version(capsys) -> None:
    assert cli.main(["version"]) == 0
    assert capsys.readouterr().out.strip() == f"bitcraft {__version__}"


def test_status_without_api(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "api_healthy", lambda *a, **k: False)
    assert cli.main(["status", "--api-url", "http://nowhere:1"]) == 1
    assert "not reachable" in capsys.readouterr().out


def test_no_terminal_falls_back_to_current(monkeypatch) -> None:
    def no_window(opts):
        raise RuntimeError("none")

    monkeypatch.setattr(cli, "open_window", no_window)
    ran = []
    monkeypatch.setattr(cli, "run_session", lambda opts: ran.append(opts) or 0)
    assert cli.main([]) == 0 and ran


def test_session_command_forwards_options() -> None:
    cmd = launcher.session_command(launcher.Options(source="api", api_url="http://box:9000"))
    assert cmd[:4] == [sys.executable, "-m", "bitcraft.cli", "here"]
    assert cmd[4:] == ["--api", "--api-url", "http://box:9000"]


def test_windows_terminal_gets_size_and_title(spawn, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(launcher.shutil, "which", lambda name: "C:/wt.exe" if name.startswith("wt") else None)
    where = launcher._open_windows(["py", "-m", "bitcraft.cli", "here"], 190, 52, tmp_path)
    cmd, _ = spawn.calls[0]
    assert where == "Windows Terminal"
    assert cmd[:5] == ["C:/wt.exe", "--size", "190,52", "--title", "BitCraft"]
    assert cmd[-4:] == ["py", "-m", "bitcraft.cli", "here"]


@pytest.mark.skipif(sys.platform != "win32", reason="console flags are Windows-only")
def test_falls_back_to_resized_console(spawn, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(launcher.shutil, "which", lambda name: None)
    where = launcher._open_windows(["py", "-m", "bitcraft.cli"], 180, 50, tmp_path)
    cmd, kwargs = spawn.calls[0]
    assert where == "Command Prompt"
    assert "mode con: cols=180 lines=50" in cmd[-1]
    assert kwargs["creationflags"] == launcher.subprocess.CREATE_NEW_CONSOLE


def test_linux_uses_first_available_emulator(spawn, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(launcher.shutil, "which", lambda name: f"/usr/bin/{name}" if name == "xterm" else None)
    where = launcher._open_linux(["py"], 190, 52, tmp_path)
    cmd, _ = spawn.calls[0]
    assert where == "xterm" and cmd[:3] == ["/usr/bin/xterm", "-geometry", "190x52"]
