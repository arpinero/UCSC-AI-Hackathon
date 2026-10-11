# PyInstaller spec for the Sentinel bridge. Build from the repository root:
#   pyinstaller --noconfirm --distpath desktop/build/py --workpath desktop/build/work desktop/packaging/sentinel-server.spec
from pathlib import Path

root = Path(SPECPATH).resolve().parent.parent

# council.sources loads these teammate modules by file path at runtime, so PyInstaller cannot
# discover them. Ship the sources and fixtures unchanged under the same relative layout.
datas = [
    (str(root / 'desktop' / 'web-build'), 'desktop/web-build'),
    (str(root / 'fixing-agent' / 'fixing_specs.py'), 'fixing-agent'),
    (str(root / 'fixing-agent' / 'fixing_scenarios.py'), 'fixing-agent'),
    (str(root / 'agents' / 'compliance' / 'agent.py'), 'agents/compliance'),
    (str(root / 'agents' / 'compliance' / 'rules.py'), 'agents/compliance'),
    (str(root / 'agents' / 'compliance' / 'realworld' / 'scenarios.py'), 'agents/compliance/realworld'),
    (str(root / 'agents' / 'compliance' / 'realworld' / 'attack.py'), 'agents/compliance/realworld'),
    (str(root / 'agents' / 'compliance' / 'realworld' / 'mitre-fixtures.json'), 'agents/compliance/realworld'),
    (str(root / 'agents' / 'compliance' / 'scenarios'), 'agents/compliance/scenarios'),
    (str(root / 'agents' / 'containment' / 'agent.py'), 'agents/containment'),
    (str(root / 'agents' / 'containment' / 'simulator.py'), 'agents/containment'),
    (str(root / 'agents' / 'containment' / 'benchmark_cases.py'), 'agents/containment'),
    (str(root / 'agents' / 'containment' / 'mitre-fixtures.json'), 'agents/containment'),
]

# Standard-library modules imported only by those path-loaded teammate files.
hiddenimports = ['argparse', 'datetime', 'hashlib', 'random', 'math', 'uuid', 'urllib.request', 'urllib.error']

a = Analysis([str(root / 'desktop' / 'sentinel_server.py')], pathex=[str(root)], datas=datas,
             hiddenimports=hiddenimports, excludes=['tkinter'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='sentinel-server', console=True)
coll = COLLECT(exe, a.binaries, a.datas, name='sentinel-server')
