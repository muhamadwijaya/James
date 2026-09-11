import unittest
from unittest.mock import patch
from importlib.metadata import PackageNotFoundError
import runtime_check

class RuntimeTests(unittest.TestCase):
    def test_selects_compatible_qt_for_python314(self):
        self.assertEqual(runtime_check.expected_pyside((3,14,2)), '6.10.3')
        for minor in (10,11,12,13):
            self.assertEqual(runtime_check.expected_pyside((3,minor,0)), '6.8.3')
    def test_unsupported_python_stops_before_install(self):
        for version in [(3,9),(3,15),(2,7)]:
            with self.assertRaises(ValueError):runtime_check.expected_pyside(version)
    def test_wrong_architecture_is_reported(self):
        with patch('runtime_check.struct.calcsize',return_value=4):
            with self.assertRaisesRegex(ValueError,'64-bit'):runtime_check.validate_python()
    def test_partial_installation_requires_repair(self):
        expected=runtime_check.expected_pyside()
        def installed(name):
            if name=='PySide6-Addons':raise PackageNotFoundError(name)
            return expected
        with patch('runtime_check.version',side_effect=installed):
            with self.assertRaisesRegex(ValueError,'belum terpasang'):runtime_check.validate_dependencies()
    def test_version_mismatch_requires_repair(self):
        with patch('runtime_check.version',return_value='6.10.1'):
            with self.assertRaisesRegex(ValueError,'perlu diperbarui'):runtime_check.validate_dependencies()

    def test_camera_decoder_is_installed_when_upgrading(self):
        packages={'qrcode':'8.2','python-barcode':'0.16.1','pystrich':'0.20','openpyxl':'3.1.5'}
        def installed(name):
            if name=='zxing-cpp':raise PackageNotFoundError(name)
            return packages.get(name,runtime_check.expected_pyside())
        with patch('runtime_check.version',side_effect=installed):
            with self.assertRaisesRegex(ValueError,'zxing-cpp'):runtime_check.validate_dependencies()

    def test_excel_dependency_is_installed_when_upgrading(self):
        packages={'qrcode':'8.2','python-barcode':'0.16.1','pystrich':'0.20'}
        def installed(name):
            if name=='openpyxl':raise PackageNotFoundError(name)
            return packages.get(name,runtime_check.expected_pyside())
        with patch('runtime_check.version',side_effect=installed):
            with self.assertRaisesRegex(ValueError,'openpyxl'):runtime_check.validate_dependencies()

if __name__=='__main__':unittest.main()
