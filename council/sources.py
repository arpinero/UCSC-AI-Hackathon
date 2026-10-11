"""Load each teammate's fixtures and pure-Python logic without touching their code.

Containment, Compliance and Fixing all ship modules called `agent`, `scenarios` or `rules`, so a
plain import would collide. `load_group` puts one seat's folder first on sys.path, imports the
named modules, then removes those generic names from sys.modules again. The returned module
objects keep working because they hold their own references.
"""
import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTAINMENT_DIR = ROOT / 'agents' / 'containment'
COMPLIANCE_DIR = ROOT / 'agents' / 'compliance'
COMPLIANCE_REALWORLD = COMPLIANCE_DIR / 'realworld'
FIXING_DIR = ROOT / 'fixing-agent'

GENERIC = ('agent', 'scenarios', 'rules', 'simulator', 'attack', 'evaluate', 'fixing_specs', 'fixing_scenarios')


def load_group(search_dirs, names):
    """Import `names` with `search_dirs` first on sys.path; return {name: module}."""
    saved_path = list(sys.path)
    saved = {k: sys.modules.pop(k) for k in GENERIC if k in sys.modules}
    sys.path[:0] = [str(d) for d in search_dirs]
    try:
        loaded = {}
        for name in names:
            spec = importlib.machinery.PathFinder.find_spec(name, [str(d) for d in search_dirs])
            if spec is None:
                raise ImportError(f'{name} not found in {search_dirs}')
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            loaded[name] = module
        return loaded
    finally:
        sys.path[:] = saved_path
        for key in GENERIC:
            sys.modules.pop(key, None)
        sys.modules.update(saved)


_cache = {}


def containment():
    """Kaylem's modules: agent (validator, SCHEMA), simulator (Simulator)."""
    if 'containment' not in _cache:
        _cache['containment'] = load_group([CONTAINMENT_DIR], ['agent', 'simulator'])
    return _cache['containment']


def compliance():
    """Soren's modules: agent (escalation, held_destructive, SAFE), rules (deadlines)."""
    if 'compliance' not in _cache:
        _cache['compliance'] = load_group([COMPLIANCE_DIR], ['rules', 'agent'])
    return _cache['compliance']


def compliance_attack():
    """Soren's ATT&CK suite: Containment's fixtures plus a compliance block."""
    if 'attack' not in _cache:
        _cache['attack'] = load_group([COMPLIANCE_REALWORLD], ['scenarios', 'attack'])['attack']
    return _cache['attack']


def fixing():
    """Aidan's fixtures and scorer."""
    if 'fixing' not in _cache:
        _cache['fixing'] = load_group([FIXING_DIR], ['fixing_specs', 'fixing_scenarios'])
    return _cache['fixing']


def containment_fixtures():
    """Kaylem's 21 ATT&CK fixtures keyed by (technique, variant)."""
    data = json.loads((CONTAINMENT_DIR / 'mitre-fixtures.json').read_text(encoding='utf-8'))
    return {(c['technique'], c['variant']): c for c in data}
