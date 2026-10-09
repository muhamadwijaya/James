"""Test modul clone — memakai PM3Client palsu, tanpa perangkat."""

from pm3tool import clone
from pm3tool.client import PM3Result


class FakeClient:
    """Rekam perintah yang dipanggil & kembalikan output yang diset."""

    def __init__(self, stdout: str = "", returncode: int = 0):
        self.commands: list[str] = []
        self._stdout = stdout
        self._rc = returncode

    def run(self, *commands: str, timeout=None) -> PM3Result:
        joined = "; ".join(commands)
        self.commands.append(joined)
        return PM3Result(command=joined, stdout=self._stdout, stderr="",
                         returncode=self._rc)


def test_card_info_detects_magic():
    c = FakeClient(stdout="[+] Magic capabilities : Gen 1a\n")
    data = clone.card_info(c)
    assert data["magic"] is True
    assert "Gen1A" in data["generations"]


def test_card_info_non_magic():
    c = FakeClient(stdout="[+] Regular MIFARE Classic 1K\n")
    data = clone.card_info(c)
    assert data["magic"] is False
    assert data["generations"] == []


def test_clone_to_gen1a_command():
    c = FakeClient()
    clone.clone_to_gen1a(c, "mydump.bin")
    assert c.commands == ["hf mf cload -f mydump.bin"]


def test_restore_without_block0():
    c = FakeClient()
    clone.restore_dump(c, dumpfile="d.bin", keyfile="k.bin")
    assert c.commands[0] == "hf mf restore --1k -f d.bin -k k.bin"
    assert "--force" not in c.commands[0]


def test_restore_with_block0_adds_force():
    c = FakeClient()
    clone.restore_dump(c, dumpfile="d.bin", write_block0=True)
    assert "--force" in c.commands[0]


def test_set_magic_uid_strips_separators():
    c = FakeClient()
    clone.set_magic_uid(c, "2C:D7:2F:90")
    assert c.commands == ["hf mf csetuid -u 2CD72F90"]
