"""Synthetic integration tests; no diffraction data, GUI, or network."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from inventory_crystal_input import classify_header, inventory
from prepare_ligand import prepare
from validate_crystal_package import audit

class SolutionHelpersTests(unittest.TestCase):
    def test_calibration_and_unknown_are_not_confirmed_frames(self):
        for kind in ('ACTIVE MASK','INITIAL BACKGROUND','BACKGROUND'):
            self.assertEqual(classify_header(('TYPE: '+kind).ljust(80).encode())[0],'calibration')
        self.assertEqual(classify_header(b'garbage')[0],'unknown')
        self.assertEqual(classify_header(b'TYPE: OTHER'.ljust(80))[0],'unknown')
        self.assertEqual(classify_header(b'TYPE: SAMPLE'.ljust(80))[0],'diffraction_candidate')

    def test_zip_inventory_reads_headers_without_extracting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); zpath=root/'input.zip'
            with zipfile.ZipFile(zpath,'w') as z:
                z.writestr('scan/image.sfrm',b'TYPE: SAMPLE'.ljust(80))
                z.writestr('cal/mask.sfrm',b'TYPE: ACTIVE MASK'.ljust(80))
                z.writestr('unknown.sfrm',b'unknown')
            before=zpath.read_bytes(); result=inventory(zpath)
            self.assertEqual(result['sfrm_counts'],dict(diffraction_candidate=1,calibration=1,unknown=1))
            self.assertEqual(zpath.read_bytes(),before)
            self.assertEqual(len(list(root.iterdir())),1)
            self.assertIn('not established',result['reintegration_status'])

    def test_ligand_optimized_reference_preserves_source(self):
        from rdkit import Chem
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'ligand.mol'
            source.write_text(Chem.MolToMolBlock(Chem.MolFromSmiles('CCO')))
            before=source.read_bytes()
            result=prepare(source,root/'ref.mol',root/'report.json',True,0,1000)
            self.assertEqual(source.read_bytes(),before)
            self.assertEqual(result['formula'],'C2H6O')
            self.assertEqual(result['optimization_status'],0)
            self.assertIn('not measured',result['limitation'])
            self.assertTrue(Chem.MolFromMolFile(str(root/'ref.mol')).GetConformer().Is3D())

    def test_ligand_multi_record_and_overwrite_rejected(self):
        from rdkit import Chem
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'multi.sdf'
            with Chem.SDWriter(str(source)) as w:
                w.write(Chem.MolFromSmiles('CCO')); w.write(Chem.MolFromSmiles('CCN'))
            with self.assertRaises(ValueError): prepare(source,root/'new.mol',root/'r.json')
            source=root/'one.mol'; source.write_text(Chem.MolToMolBlock(Chem.MolFromSmiles('CCO')))
            with self.assertRaises(ValueError): prepare(source,source,root/'r.json')
            (root/'ref.mol').write_text('earlier output')
            with self.assertRaises(FileExistsError): prepare(source,root/'ref.mol',root/'r.json')
            self.assertEqual((root/'ref.mol').read_text(),'earlier output')

    def test_disconnected_ligand_not_optimized_as_one_complex(self):
        from rdkit import Chem
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'salt.mol'
            source.write_text(Chem.MolToMolBlock(Chem.MolFromSmiles('CC[NH3+].[Cl-]')))
            result=prepare(source,root/'topology.mol',root/'r.json')
            self.assertEqual(result['fragments'],2)
            with self.assertRaises(ValueError): prepare(source,root/'optimized.mol',root/'o.json',True)

    def package(self,root):
        for ext in ('cif','fcf','res','ins','hkl','lst'): (root/('sample.'+ext)).write_text('test\n')

    def test_fab_and_include_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.package(root)
            (root/'sample.ins').write_text('TITL s\nABIN\n++restraints.inc\nHKLF 4\nEND\n')
            result=audit(root,'sample')
            self.assertTrue(any('FAB' in x for x in result['errors']))
            self.assertTrue(any('include' in x for x in result['errors']))
            (root/'sample.fab').write_text('test'); (root/'restraints.inc').write_text('REM constraints')
            self.assertEqual(audit(root,'sample')['errors'],[])
            (root/'sample.ins').write_text('++../outside.inc\nHKLF 4\n')
            self.assertTrue(any('escaping' in x for x in audit(root,'sample')['errors']))

    def test_checksum_tampering_and_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.package(root)
            h=hashlib.sha256((root/'sample.hkl').read_bytes()).hexdigest()
            (root/'DELIVERY_SHA256.csv').write_text('relpath,sha256,bytes\nsample.hkl,'+h+',5\n')
            self.assertEqual(audit(root,'sample')['errors'],[])
            (root/'sample.hkl').write_text('modified')
            self.assertTrue(any('Checksum' in x for x in audit(root,'sample')['errors']))
            (root/'DELIVERY_SHA256.csv').write_text('relpath,sha256\n../outside.hkl,000\n')
            self.assertTrue(any('escapes' in x for x in audit(root,'sample')['errors']))

    def test_missing_basename_not_accepted_as_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.package(root)
            (root/'sample.hkl').rename(root/'old.hkl')
            self.assertTrue(audit(root,'sample')['errors'])
            self.assertEqual(audit(root,'sample')['scientific_validation'],'not performed')

    def test_delivery_support_files_and_zip_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.package(root)
            (root/'sample.ins').write_text('TITL test\nABIN\nHKLF 4\nEND\n')
            (root/'sample.fab').write_text('dependency')
            script=Path(__file__).with_name('10_delivery.py'); out=root/'delivery'
            command=[sys.executable,str(script),'--outdir',str(out),'--name','selected','--zip']
            for ext in ('cif','fcf','res','ins','hkl','lst'): command+=['--'+ext,str(root/('sample.'+ext))]
            command+=['--support',str(root/'sample.fab')]
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(audit(out,'selected')['errors'],[])
            with zipfile.ZipFile(str(out)+'.zip') as z: self.assertIsNone(z.testzip())

if __name__=='__main__': unittest.main(verbosity=2)
