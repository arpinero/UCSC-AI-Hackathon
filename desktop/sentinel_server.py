"""Entry point for the packaged Sentinel bridge (PyInstaller) and for `python -m desktop.sentinel_server`.

Runs the same loopback bridge as `python -m desktop.bridge`. In a frozen build the UI files are
unpacked under sys._MEIPASS, so the web root defaults there instead of next to the source file.
Pass --port 0 to let the OS pick a free loopback port; the chosen port is printed on startup.
"""
import sys
from pathlib import Path

from desktop.bridge import main


def run(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    bundle = getattr(sys, '_MEIPASS', None)
    if bundle and '--web-root' not in argv:
        argv += ['--web-root', str(Path(bundle) / 'desktop' / 'web-build')]
    main(argv)


if __name__ == '__main__':
    run()
