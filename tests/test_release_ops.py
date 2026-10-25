"""Operational release gates: avoid approving a false-ready build."""
from __future__ import annotations
import os,subprocess,sys


def test_operator_check_fails_closed():
    variables={k:v for k,v in os.environ.items() if not k.startswith('ACTCALC_')}
    r=subprocess.run([sys.executable,'-m','backend.manage','check'],env=variables,capture_output=True,text=True,timeout=10)
    assert r.returncode!=0
    assert 'Launch ready: False' in r.stdout
    assert 'Verification required:' in r.stdout
