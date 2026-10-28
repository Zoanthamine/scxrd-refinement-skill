"""Read-only inventory. Frame candidates do not establish reintegration capability."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import zipfile

HEADER_BYTES = 7680

def classify_header(data):
    text = data[:HEADER_BYTES].decode('latin-1')
    for pos in range(0, len(text), 80):
        line = text[pos:pos+80]
        if line.split(':', 1)[0].strip() == 'TYPE' and ':' in line:
            kind = line.split(':', 1)[1].strip()
            if any(word in kind.upper() for word in ('MASK', 'BACKGROUND')):
                return 'calibration', kind
            if kind.upper() in {'SAMPLE', 'DIFFRACTION'}:
                return 'diffraction_candidate', kind
            return 'unknown', kind
    return 'unknown', 'UNKNOWN'

def inventory(source):
    source = Path(source).resolve(strict=True)
    rows = []
    def add(name, size, header=None):
        item = dict(name=name, bytes=size)
        if header is not None:
            item['classification'], item['type'] = classify_header(header)
        rows.append(item)
    if source.is_dir():
        for p in sorted(source.rglob('*')):
            if p.is_file():
                header = None
                if p.suffix.lower() == '.sfrm':
                    with p.open('rb') as f: header = f.read(HEADER_BYTES)
                add(p.relative_to(source).as_posix(), p.stat().st_size, header)
    elif zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as z:
            for item in sorted(z.infolist(), key=lambda i:i.filename):
                if item.is_dir(): continue
                header = None
                if item.filename.lower().endswith('.sfrm'):
                    with z.open(item) as f: header = f.read(HEADER_BYTES)
                add(item.filename, item.file_size, header)
    else:
        raise ValueError('Expected a directory or ZIP; no extraction is performed')
    counts = Counter(item.get('classification') for item in rows if 'classification' in item)
    return dict(source=str(source), file_count=len(rows), files=rows,
                extensions=dict(Counter(Path(r['name']).suffix.lower() for r in rows)),
                sfrm_counts=dict(counts),
                reintegration_status='not established: check sequence completeness, decoder and geometry',
                note='Unknown TYPE is not classified as diffraction. Other frame formats require their own reader.')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path)
    args=p.parse_args()
    try: result=inventory(args.input)
    except (OSError,ValueError,zipfile.BadZipFile) as exc: p.error(str(exc))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
