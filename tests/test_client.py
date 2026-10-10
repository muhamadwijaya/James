"""Test pembangunan argumen PM3Client (tanpa menjalankan pm3)."""

from pm3tool.client import PM3Client


def test_wrapper_uses_p_flag():
    c = PM3Client(binary="pm3", port="com10")
    argv, joined = c._build_argv(("hw version",))
    assert argv == ["pm3", "-p", "com10", "-c", "hw version"]
    assert joined == "hw version"


def test_wrapper_bat_uses_p_flag():
    c = PM3Client(binary="pm3.bat", port="COM3")
    argv, _ = c._build_argv(("hw tune",))
    assert argv == ["pm3.bat", "-p", "COM3", "-c", "hw tune"]


def test_raw_exe_uses_positional_port():
    c = PM3Client(binary=r"C:\ProxSpace\pm3\proxmark3\client\proxmark3.exe",
                  port="com10")
    argv, _ = c._build_argv(("hf search",))
    assert argv[0].endswith("proxmark3.exe")
    assert argv[1] == "com10"          # posisional, bukan -p
    assert argv[2:] == ["-c", "hf search"]


def test_no_port_omits_port_arg():
    c = PM3Client(binary="pm3")
    argv, joined = c._build_argv(("a", "b"))
    assert argv == ["pm3", "-c", "a; b"]
    assert joined == "a; b"


def test_is_wrapper_detection():
    assert PM3Client(binary="pm3")._is_wrapper() is True
    assert PM3Client(binary="pm3.bat")._is_wrapper() is True
    assert PM3Client(binary="proxmark3.exe")._is_wrapper() is False
    assert PM3Client(binary="/usr/local/bin/proxmark3")._is_wrapper() is False
