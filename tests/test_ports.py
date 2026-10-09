"""Test deteksi port — tidak bergantung perangkat nyata."""

from pm3tool import ports


def test_list_serial_ports_returns_list():
    result = ports.list_serial_ports()
    assert isinstance(result, list)
    assert all(isinstance(p, str) for p in result)


def test_com_sort_key_numeric_order():
    names = ["COM10", "COM3", "COM2", "COM1"]
    assert sorted(names, key=ports._com_sort_key) == \
        ["COM1", "COM2", "COM3", "COM10"]
