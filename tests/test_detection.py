"""Deteksi instalasi/USB Windows disimulasikan; tidak membuka port atau flash."""

import json
import subprocess
from types import SimpleNamespace

import pytest

from pm3tool import client, detection
from pm3tool.detection import PM3PortError, SerialPort


@pytest.mark.parametrize("folder", ["client", "client/build", "."])
def test_find_client_in_proxspace_layout(tmp_path, monkeypatch, folder):
    root = tmp_path / "ProxSpace" / "pm3" / "proxmark3"
    directory = root / folder
    directory.mkdir(parents=True)
    exe = directory / "proxmark3.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(detection, "IS_WINDOWS", True)
    monkeypatch.setattr(detection, "_search_roots", lambda: [root])
    assert detection.find_pm3("pm3") == str(exe.resolve())
    assert detection.find_pm3(str(root)) == str(exe.resolve())


def test_client_on_path_and_explicit_missing_path(monkeypatch, tmp_path):
    monkeypatch.setattr(detection, "_search_roots", lambda: [])
    monkeypatch.setattr(detection, "IS_WINDOWS", True)
    monkeypatch.setattr(detection.shutil, "which", lambda name:
                        r"C:\Tools\proxmark3.exe" if name == "proxmark3.exe" else None)
    assert detection.find_pm3("auto") == r"C:\Tools\proxmark3.exe"
    assert detection.find_pm3(str(tmp_path / "missing.exe")) is None


def test_env_binary_is_respected_and_auto_can_override(tmp_path, monkeypatch):
    exe = tmp_path / "manual.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setenv("PM3_BINARY", str(exe))
    monkeypatch.setattr(detection, "_search_roots", lambda: [])
    monkeypatch.setattr(detection.shutil, "which", lambda name: None)
    assert detection.find_pm3() == str(exe.resolve())
    assert detection.find_pm3("auto") is None


@pytest.mark.parametrize("hwid", [
    r"USB\VID_9AC4&PID_4B8F\ICEMAN",
    r"USB\VID_2D2D&PID_504D\1234",
    "USB VID:PID=9ac4:4b8f SER=1234",
])
def test_generic_usb_serial_device_is_identified_by_hardware_id(hwid):
    ports = (SerialPort("COM2", "Bluetooth"),
             SerialPort("COM17", "USB Serial Device", hwid))
    assert detection.choose_pm3_port(ports) == "COM17"


def test_single_unrelated_serial_port_is_never_selected():
    with pytest.raises(PM3PortError, match="belum terdeteksi"):
        detection.choose_pm3_port((SerialPort("COM1", "Arduino"),))


def test_multiple_pm3_devices_require_selection():
    ports = (SerialPort("COM3", "Proxmark3"), SerialPort("COM21", "ProxMark-3"))
    with pytest.raises(PM3PortError, match="COM3, COM21"):
        detection.choose_pm3_port(ports)


def test_duplicate_ports_merge_and_sort_numerically(monkeypatch):
    monkeypatch.setattr(detection, "IS_WINDOWS", True)
    monkeypatch.setattr(detection, "_serial_ports", lambda: [
        SerialPort("COM10", "USB Serial"), SerialPort("COM2", "Bluetooth")])
    monkeypatch.setattr(detection, "_windows_ports", lambda: [
        SerialPort("com10", "USB Serial Device", r"USB\VID_9AC4&PID_4B8F\1")])
    ports = detection.list_serial_ports()
    assert [p.device for p in ports] == ["COM2", "COM10"]
    assert detection.choose_pm3_port(ports) == "COM10"


@pytest.mark.parametrize("as_array", [False, True])
def test_windows_json_supports_one_record_and_arrays(monkeypatch, as_array):
    record = {"Name": "USB Serial Device (COM28)", "PNPDeviceID":
              r"USB\VID_9AC4&PID_4B8F\ICEMAN"}
    monkeypatch.setattr(detection.shutil, "which", lambda name: "powershell.exe")

    def fake_run(argv, **kwargs):
        assert argv[1:4] == ["-NoProfile", "-NonInteractive", "-Command"]
        assert "ConfigManagerErrorCode -eq 0" in argv[4]
        assert not argv[4].lstrip().startswith("+")
        assert kwargs["timeout"] == 10
        return SimpleNamespace(returncode=0, stdout="\ufeff" + json.dumps(
            [record] if as_array else record))

    monkeypatch.setattr(detection.subprocess, "run", fake_run)
    assert detection.choose_pm3_port(tuple(detection._windows_ports())) == "COM28"


@pytest.mark.parametrize("failure", ["timeout", "invalid-json", "exit-error"])
def test_powershell_failure_does_not_crash_gui(monkeypatch, failure):
    monkeypatch.setattr(detection.shutil, "which", lambda name: "powershell.exe")

    def fake_run(argv, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(argv, 10)
        return SimpleNamespace(returncode=1 if failure == "exit-error" else 0,
                               stdout="not json")

    monkeypatch.setattr(detection.subprocess, "run", fake_run)
    assert detection._windows_ports() == []


def test_manual_port_wins_over_auto_detection(monkeypatch):
    monkeypatch.setattr(detection, "find_pm3", lambda binary: "proxmark3.exe")
    monkeypatch.setattr(detection, "list_serial_ports", lambda: (
        SerialPort("COM4", "Proxmark3"),))
    connection = detection.detect_connection("pm3", "COM25")
    assert connection.port == "COM25"
    assert "manual" in connection.messages[1]


def test_native_client_run_gets_detected_port(monkeypatch):
    exe = r"C:\ProxSpace\pm3\proxmark3\client\proxmark3.exe"
    monkeypatch.setattr(client, "find_pm3", lambda binary: exe)
    monkeypatch.setattr(client, "list_serial_ports", lambda: (
        SerialPort("COM8", "Proxmark3"),))
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="Connected", stderr="")

    monkeypatch.setattr(client.subprocess, "run", fake_run)
    result = client.PM3Client().run("hw version")
    assert result.ok
    assert calls == [[exe, "COM8", "-c", "hw version"]]


def test_native_client_missing_pm3_port_does_not_start_offline(monkeypatch):
    monkeypatch.setattr(client, "find_pm3", lambda binary: "proxmark3.exe")
    monkeypatch.setattr(client, "list_serial_ports", lambda: (SerialPort("COM1", "Arduino"),))
    with pytest.raises(PM3PortError):
        client.PM3Client().run("hw version")


def test_manual_port_skips_enumeration(monkeypatch):
    monkeypatch.setattr(client, "find_pm3", lambda binary: "proxmark3.exe")
    monkeypatch.setattr(client, "list_serial_ports", lambda: pytest.fail("manual port must win"))
    monkeypatch.setattr(client.subprocess, "run", lambda argv, **kw:
                        SimpleNamespace(returncode=0, stdout="", stderr=""))
    assert client.PM3Client(port="COM23").run("hw version").ok
