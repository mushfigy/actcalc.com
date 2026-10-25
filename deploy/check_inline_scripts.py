"""Syntax-check every inline browser module in the compiled HTML with Node.
No code from the generated page is executed during this check.
"""
from __future__ import annotations
from pathlib import Path
import re, subprocess, tempfile

index=Path(__file__).resolve().parents[1]/'static'/'index.html'
html=index.read_text(encoding='utf-8')
scripts=re.findall(r'<script(?:\s[^>]*)?>(.*?)</script\s*>',html,flags=re.DOTALL|re.IGNORECASE)
count=0
with tempfile.TemporaryDirectory() as tmp:
    for index,content in enumerate(scripts):
        if not content.strip():continue
        file=Path(tmp)/f'module_{index}.js'
        file.write_text(content,encoding='utf-8')
        result=subprocess.run(['node','--check',str(file)],capture_output=True,text=True)
        if result.returncode:
            raise SystemExit(f'Inline script {index} invalid: {result.stderr[-1200:]}')
        count+=1
assert count>20, 'Unexpected missing frontend scripts'
print(f'PASS: {count} inline browser modules parse')
