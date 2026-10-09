"""Test parser mfkey & modul attack — tanpa perangkat."""

from pm3tool import parse, attack
from pm3tool.client import PM3Result


class FakeClient:
    def __init__(self, stdout: str = "", returncode: int = 0):
        self.commands: list[str] = []
        self._stdout = stdout
        self._rc = returncode

    def run(self, *commands: str, timeout=None) -> PM3Result:
        joined = "; ".join(commands)
        self.commands.append(joined)
        return PM3Result(command=joined, stdout=self._stdout, stderr="",
                         returncode=self._rc)


MFKEY_SAMPLE = """
[=] Collecting nonces...
[+]  Found valid key: ffffffffffff
[+] Found Key: A [a0a1a2a3a4a5]
"""


def test_parse_mfkey_keys():
    keys = parse.parse_mfkey_keys(MFKEY_SAMPLE)
    assert keys == ["FFFFFFFFFFFF", "A0A1A2A3A4A5"]


def test_parse_mfkey_dedup():
    text = "key: ffffffffffff\nFound valid key: FFFFFFFFFFFF\n"
    assert parse.parse_mfkey_keys(text) == ["FFFFFFFFFFFF"]


def test_parse_mfkey_none():
    assert parse.parse_mfkey_keys("tidak ada") == []


def test_recover_via_reader_command():
    c = FakeClient(stdout=MFKEY_SAMPLE)
    data = attack.recover_via_reader(c, uid="2C:D7:2F:90")
    assert c.commands[0] == "hf mf sim --1k -x -u 2CD72F90 -e"
    assert data["keys"] == ["FFFFFFFFFFFF", "A0A1A2A3A4A5"]


def test_recover_via_reader_no_uid_no_store():
    c = FakeClient()
    attack.recover_via_reader(c, store_keys=False)
    assert c.commands[0] == "hf mf sim --1k -x"


def test_sniff_and_crack_runs_both():
    c = FakeClient(stdout="Found valid key: a0a1a2a3a4a5\n")
    data = attack.sniff_and_crack(c)
    assert c.commands[0] == "hf 14a sniff"
    assert c.commands[1] == "trace list -t mf"
    assert data["keys"] == ["A0A1A2A3A4A5"]
    assert "sniff_raw" in data
