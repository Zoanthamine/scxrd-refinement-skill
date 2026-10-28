"""Audit files, basenames, ABIN/include dependencies and optional recorded hashes.
This does not validate a structure, report scientific acceptance or run external programs.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import zipfile

def audit(root, basename=None):
    root=Path(root).resolve(strict=True)
    if not root.is_dir(): raise ValueError('Expected package directory')
    files=[p for p in root.rglob('*') if p.is_file()]
    errors=[]; notes=[]
    groups={ext:[p for p in files if p.suffix.lower()=='.'+ext] for ext in ('cif','fcf','res','ins','hkl','lst')}
    for ext,paths in groups.items():
        if not paths: errors.append('Missing '+ext.upper())
    if basename:
        for ext,paths in groups.items():
            if not any(p.stem==basename for p in paths): errors.append('No selected basename for '+ext)
    elif any(len(paths)>1 for paths in groups.values()):
        notes.append('Multiple candidate sets: select --basename and inspect provenance')
    for p in groups['ins']:
        if basename and p.stem!=basename: continue
        text=p.read_text(encoding='latin-1')
        active=re.split(r'^\s*HKLF\b',text,1,flags=re.M|re.I)[0]
        if re.search(r'^\s*ABIN\b',active,re.M|re.I) and not any(f.name==p.stem+'.fab' for f in files):
            errors.append('Missing FAB required by '+p.name)
        for name in re.findall(r'^\+{1,2}([^!\r\n]+)',active,re.M):
            name=name.strip()
            normalized=name.replace('\\','/')
            if re.match(r'^[A-Za-z]:|^/',normalized) or '..' in Path(normalized).parts:
                errors.append('External/escaping include dependency: '+name)
            elif not (p.parent/normalized).is_file():
                errors.append('Missing include beside INS: '+name)
        if re.search(r'^\s*(TWIN|BASF)\b',active,re.M|re.I):
            notes.append('Twin protocol and source observations require scientific review: '+p.name)
    manifest=root/'DELIVERY_SHA256.csv'
    checked=0
    if manifest.exists():
        with manifest.open(encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                name=row.get('relpath','').replace('\\','/')
                path=(root/name).resolve()
                if path==root or root not in path.parents:
                    errors.append('Checksum path escapes package: '+name); continue
                if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest().lower()!=row.get('sha256','').lower():
                    errors.append('Checksum mismatch/missing file: '+name)
                checked+=1
    else: notes.append('No DELIVERY_SHA256.csv: source/package integrity not verified')
    notes.append('Geometry, experimental metadata, CIF/FCF consistency and packaged rerun require separate validation')
    return dict(package=str(root),errors=errors,notes=notes,checksum_entries_checked=checked,
                file_counts={k:len(v) for k,v in groups.items()},files_complete=not errors,
                scientific_validation='not performed')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('package',type=Path); p.add_argument('--basename')
    p.add_argument('--zip',dest='archive',type=Path,help='Existing ZIP to integrity-test without extracting')
    a=p.parse_args()
    try:
        result=audit(a.package,a.basename)
        if a.archive:
            with zipfile.ZipFile(a.archive) as z: bad=z.testzip()
            result['zip_integrity']='ok' if bad is None else 'failed: '+bad
            if bad is not None: result['errors'].append('ZIP integrity failed')
    except (OSError,ValueError,zipfile.BadZipFile) as exc: p.error(str(exc))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(1 if result['errors'] else 0)

if __name__=='__main__': main()
