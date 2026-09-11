"""Run: python main.py. F11 toggles full screen."""
import argparse
import os
import sys
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description='Dashboard desktop AGREGASI')
    parser.add_argument('--data-dir',type=Path,help='Override data directory for testing/portable use')
    parser.add_argument('--screenshot',type=Path,help='Save dashboard PNG and exit (offscreen supported)')
    parser.add_argument('--windowed',action='store_true')
    args=parser.parse_args()
    from runtime_check import validate_python
    try:
        validate_python()
    except ValueError as exc:
        print(str(exc))
        return 1
    from PySide6.QtCore import QStandardPaths,QTimer
    from PySide6.QtWidgets import QApplication
    from agregasi.store import Store
    from agregasi.app import MainWindow
    from agregasi.dashboard import BASE
    from agregasi.typography import ui_font
    app=QApplication(sys.argv)
    app.setApplicationName('AGREGASI_UI')
    app.setOrganizationName('AGREGASI')
    app.setStyle('Fusion')
    app.setFont(ui_font())
    app.setStyleSheet((BASE/'styles/theme.qss').read_text(encoding='utf-8'))
    data_dir=args.data_dir or Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    store=Store(data_dir/'agregasi.sqlite3')
    window=MainWindow(store)
    if args.screenshot:window.show()
    else:window.show_configured(windowed=args.windowed)
    if args.screenshot:
        def capture():
            args.screenshot.parent.mkdir(parents=True,exist_ok=True)
            window.pages['dashboard'].grab().save(str(args.screenshot))
            app.quit()
        QTimer.singleShot(600,capture)
    try:return app.exec()
    finally:store.close()

if __name__=='__main__':
    sys.exit(main())
