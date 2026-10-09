"""Offline regression checks: no scientific model selection and no network calls."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).parent
def module(name):
    spec = importlib.util.spec_from_file_location('test_' + name, HERE / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

run = module('03_run')
cif = module('08_cif')
check = module('09_checkcif')

class RegressionTests(unittest.TestCase):
    def test_preserve_model_instructions(self):
        lines = ['TITL sample', 'CELL 0.71073 10 11 12 90 100 90',
                 'LATT -1', 'SFAC C H', 'UNIT 2 4', 'WGHT 0.12 1.34',
                 'FVAR 1 0.7', 'PART 1', 'SAME C1 > C4',
                 'C1 1 .1 .2 .3 21 .02 .03 =', ' .04 .001 .002 .003',
                 'AFIX 23', 'H1 2 .1 .2 .4 21 -1.2', 'AFIX 0', 'PART 0',
                 'HKLF 5', 'REM trailing diagnostics', 'WGHT .9 9', 'END']
        result = run.clean_ins(lines)
        self.assertIn('HKLF 5', result)
        self.assertIn('SAME C1 > C4', result)
        self.assertIn('WGHT 0.12 1.34', result)
        self.assertNotIn('WGHT .9 9', result)
        self.assertNotIn('ACTA', result)
        self.assertEqual(result[result.index('C1 1 .1 .2 .3 21 .02 .03 =')+1], ' .04 .001 .002 .003')
        self.assertEqual(run.ensure_weights(result), result)

    def test_reject_missing_hkl_and_external_dependencies(self):
        for lines in (['TITL missing'], ['TITL include', '+restraints.ins', 'HKLF 4']):
            with self.assertRaises(ValueError):
                run.clean_ins(lines)

    def test_ambiguous_data_not_guessed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            base = root / 'sample.res'; base.write_text('TITL sample\nHKLF 4\nEND\n')
            for name in ('a.hkl','b.hkl'): (root/name).write_text('0 0 0 0 0')
            with self.assertRaisesRegex(ValueError, 'Multiple HKL'):
                run.run_stage(str(base), 'ambiguous', str(root/'work'))

    def test_iterations_have_separate_artifacts_and_no_duplicate_overlay(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); base = root/'sample.res'; hkl=root/'sample.hkl'
            base.write_text('TITL s\nWGHT .1 1\nC1 1 .1 .2 .3 11 .02\nHKLF 4\nEND\n')
            hkl.write_text('0 0 0 0 0'); calls=[]
            def fake(lines, hk, arch, job, threads, timeout):
                calls.append((list(lines),arch))
                (Path(arch)/(job+'.res')).write_text('\n'.join(lines))
                return b''
            metrics = dict(WGHT_used='.1 1',WGHT_next='.2 2',wR2=.1)
            with patch.object(run,'_run_once',fake), patch.object(run,'summarize_one',return_value=metrics):
                final,_=run.run_stage(str(base),'test',str(root/'work'),extra='RIGU .004 .008',converge=1)
            self.assertNotEqual(calls[0][1],calls[1][1])
            self.assertEqual(calls[1][0].count('RIGU .004 .008'),1)
            self.assertTrue(final.endswith('weight_01'))
            self.assertTrue((root/'work'/'test'/'run_result.json').is_file())
            with self.assertRaises(FileExistsError):
                run.run_stage(str(base),'test',str(root/'work'))

    def test_failed_subprocess_stops_and_retains_temp(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); arch=root/'archive'; arch.mkdir(); tmp=root/'tmp'; tmp.mkdir()
            hkl=root/'x.hkl'; hkl.write_text('0 0 0 0 0')
            process=SimpleNamespace(returncode=1,stdout=b'failure',stderr=b'')
            with patch.object(run.tempfile,'mkdtemp',return_value=str(tmp)), patch.object(run.subprocess,'run',return_value=process):
                with self.assertRaises(RuntimeError):
                    run._run_once(['TITL s','HKLF 4'],str(hkl),str(arch),'model',1,5)
            self.assertTrue(tmp.exists())
            self.assertTrue((arch/'console.txt').exists())

    def test_metadata_unknowns_conflicts_quotes_and_embedded_text(self):
        import gemmi
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); source=root/'x.cif'; mc=root/'x.metacif'; meta=root/'meta.json'; out=root/'out.cif'
            source.write_text("data_s\n_diffrn_radiation_wavelength 1.34139\n_shelx_res_file\n;\nTITL original\nWGHT .1 1\n;\n_publ_section_exptl_refinement\n;\nOriginal description\n;\n")
            mc.write_text("data_s\n_diffrn_radiation_wavelength 0.71073\n_exptl_absorpt_correction_T_min 0.0099\n_exptl_absorpt_correction_T_max 0.0276\n_exptl_crystal_colour 'pale yellow'\n")
            meta.write_text(json.dumps({'_publ_section_exptl_refinement':'Verified text\nSecond line'}))
            cif.do_prepare(SimpleNamespace(cif=str(source),metacif=str(mc),meta=str(meta),out=str(out)))
            block=gemmi.cif.read_file(str(out)).sole_block()
            self.assertEqual(block.find_value('_diffrn_radiation_wavelength'),'1.34139')
            self.assertEqual(block.find_value('_exptl_absorpt_correction_T_min'),'0.0099')
            self.assertEqual(block.find_value('_exptl_crystal_size_max'),'?')
            self.assertIsNone(block.find_value('_chemical_absolute_configuration'))
            self.assertIsNone(block.find_value('_diffrn_ambient_temperature'))
            self.assertEqual(block.find_value('_shelx_res_file'),gemmi.cif.read_file(str(source)).sole_block().find_value('_shelx_res_file'))
            self.assertIn('Second line',block.find_value('_publ_section_exptl_refinement'))

    def test_vrf_has_no_assumed_explanation_and_keeps_repeated_atoms(self):
        alerts=check.parse_alerts('<pre>PLAT234_ALERT_2_C C1-C2\nPLAT234_ALERT_2_C C3-C4\n</pre>')
        self.assertEqual(len(alerts),2)
        reply=check.make_vrf(alerts)
        self.assertIn('TODO',reply)
        self.assertNotIn('genuine intramolecular hydrogen bond',reply)

    def test_network_fallback_records_actual_mode(self):
        with patch.object(check,'submit',side_effect=[('bad','url','failed'),('report','url',None)]):
            result=check.submit_with_fallback('x.cif','x.fcf',verbose=False)
        self.assertEqual(result[-1],'checkcif_only')

if __name__ == '__main__':
    unittest.main(verbosity=2)
