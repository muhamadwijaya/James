"""Validate Python and the version selected by requirements.txt before launching."""
import argparse
import platform
import struct
import sys
import sysconfig
from importlib.metadata import PackageNotFoundError, version


def expected_pyside(python_version=None):
    major, minor = tuple(python_version or sys.version_info)[:2]
    if major != 3 or not 10 <= minor <= 14:
        raise ValueError('Gunakan Python 3.10 sampai 3.14 (64-bit).')
    return '6.10.3' if minor >= 14 else '6.8.3'


def validate_python():
    required = expected_pyside()
    if struct.calcsize('P') * 8 != 64:
        raise ValueError('PySide6 memerlukan Python 64-bit. Python ini adalah 32-bit.')
    if sys.implementation.name != 'cpython':
        raise ValueError('Gunakan CPython standar dari python.org.')
    if sysconfig.get_config_var('Py_GIL_DISABLED'):
        raise ValueError('Gunakan Python standar; paket ini belum mendukung Python free-threaded.')
    return required


def validate_dependencies():
    required = validate_python()
    for package in ('PySide6', 'PySide6-Essentials', 'PySide6-Addons', 'shiboken6'):
        try:
            installed = version(package)
        except PackageNotFoundError:
            raise ValueError(package+' belum terpasang.') from None
        if installed != required:
            raise ValueError(f'{package} {installed} perlu diperbarui menjadi {required}.')
    for package, expected in {'qrcode':'8.2', 'python-barcode':'0.16.1', 'pystrich':'0.20', 'openpyxl':'3.1.5', 'zxing-cpp':'3.0.0'}.items():
        try:
            installed = version(package)
        except PackageNotFoundError:
            raise ValueError(package+' belum terpasang untuk aplikasi.') from None
        if installed != expected:
            raise ValueError(f'{package} {installed} perlu diperbarui menjadi {expected}.')
    return required


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dependencies', action='store_true')
    args = parser.parse_args()
    try:
        required = validate_dependencies() if args.dependencies else validate_python()
    except ValueError as exc:
        print('PERIKSA RUNTIME: '+str(exc))
        return 1
    print(f'Python {platform.python_version()} 64-bit | PySide6 yang dipilih: {required}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
