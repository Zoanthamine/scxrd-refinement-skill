"""Offline behavioral tests with synthetic observations; no private data or network."""
import importlib.util
import json
import os
from unittest.mock import patch
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
from dials_stage import expand_arguments, run_stage, resolve_executable
from dials_screen import screen, map_candidates


class DialsHelpersTests(unittest.TestCase):
    def test_launcher_explicit_overrides_environment_and_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            explicit = root/'explicit'; explicit.mkdir()
            configured = root/'configured'; configured.mkdir()
            name = 'dials.report' + ('.exe' if os.name == 'nt' else '')
            (explicit/name).write_text('explicit')
            (configured/name).write_text('configured')
            with patch.dict(os.environ, {'DIALS_BIN': str(configured)}), patch('dials_stage.shutil.which') as which:
                self.assertEqual(resolve_executable('report', explicit), (explicit/name).resolve())
                self.assertEqual(resolve_executable('report'), (configured/name).resolve())
                which.assert_not_called()

    def test_invalid_configuration_does_not_silently_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {'DIALS_BIN': tmp}), patch('dials_stage.shutil.which') as which:
                with self.assertRaises(FileNotFoundError):
                    resolve_executable('report')
                with self.assertRaises(FileNotFoundError):
                    resolve_executable('report', Path(tmp)/'missing')
                which.assert_not_called()

    def test_launcher_path_fallback_and_missing_program(self):
        with tempfile.TemporaryDirectory() as tmp:
            name = 'dials.report' + ('.exe' if os.name == 'nt' else '')
            exe = Path(tmp)/name; exe.write_text('launcher')
            with patch.dict(os.environ, {'DIALS_BIN': ''}), patch('dials_stage.shutil.which', return_value=str(exe)):
                self.assertEqual(resolve_executable('report'), exe.resolve())
            with patch.dict(os.environ, {'DIALS_BIN': ''}), patch('dials_stage.shutil.which', return_value=None):
                with self.assertRaises(FileNotFoundError):
                    resolve_executable('report')

    def test_joint_evidence_and_leave_dataset_out(self):
        # Two suspect measurements in dataset 0 cannot validate each other.
        datasets = np.array([0, 0, 1, 1, 2, 3, 4])
        values = np.array([100., 100., 10., 10., 10., 10., 10.])
        variance = np.ones(7)
        common = (np.zeros(7, int), datasets, values, variance, np.ones(7, bool), np.ones(7, bool))
        candidate, z, refs, distinct = screen(*common, np.array([2., .1, .1, .1, .1, .1, .1]), 1., 5., 4, 3)
        self.assertEqual(candidate.tolist(), [True, False, False, False, False, False, False])
        self.assertEqual(refs[0], 5)
        self.assertEqual(distinct[0], 4)
        self.assertGreater(z[0], 50)
        # Weak/negative intensity alone never becomes a candidate.
        candidate, *_ = screen(np.arange(7), datasets, -values, variance,
                               np.ones(7, bool), np.ones(7, bool), np.full(7, 5.), 1., 5., 4, 3)
        self.assertFalse(candidate.any())

    def test_reference_diversity_required(self):
        candidate, *_ = screen(np.zeros(6, int), np.array([0, 1, 1, 1, 1, 1]),
            np.array([100., 10., 10., 10., 10., 10.]), np.ones(6), np.ones(6, bool),
            np.ones(6, bool), np.full(6, 2.), 1., 5., 4, 3)
        self.assertFalse(candidate.any())

    def test_mapping_bijection_and_other_equivalents_retained(self):
        self.assertEqual(map_candidates({('a', 1)}, [('b', 1), ('a', 1)]).tolist(), [False, True])
        for source in ([('b', 1)], [('a', 1), ('a', 1)]):
            with self.assertRaises(ValueError):
                map_candidates({('a', 1)}, source)

    def test_runner_hashes_checks_outputs_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'input'; source.write_text('original')
            out = root / 'ok'
            status = run_stage([sys.executable, '-c', "open('result','w').write('ok')"], out,
                               [source], ['result'])
            self.assertEqual(status['state'], 'completed')
            self.assertEqual(source.read_text(), 'original')
            self.assertEqual(len(json.loads((out/'command.json').read_text())['inputs'][0]['sha256']), 64)
            with self.assertRaises(FileExistsError):
                run_stage([sys.executable], out)
            with self.assertRaises(RuntimeError):
                run_stage([sys.executable, '-c', 'pass'], root/'missing', expected=['absent'])
            with self.assertRaises(RuntimeError):
                run_stage([sys.executable, '-c', 'raise SystemExit(7)'], root/'failed')
            self.assertEqual(json.loads((root/'failed'/'status.json').read_text())['exit_code'], 7)
            with self.assertRaises(ValueError):
                run_stage([sys.executable], root/'escape', expected=['../source'])

    def test_unmatched_glob_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                expand_arguments([str(Path(tmp)/'*.sfrm')])

    def test_last_refinement_cycle_is_reported(self):
        spec = importlib.util.spec_from_file_location('run_module', Path(__file__).with_name('03_run.py'))
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            lst = Path(tmp)/'model.lst'
            lst.write_text('Mean shift/esd = 0.5 Maximum = 5.2\nMax. shift = 0.9 A\n'
                           'Mean shift/esd = 0.000 Maximum = -1.0E-3\nMax. shift = 0.0001 A\n')
            result = module.parse_lst(lst)
            self.assertEqual(float(result['shift_esd']), -0.001)
            self.assertEqual(result['maxshift_A'], 0.0001)


if __name__ == '__main__':
    unittest.main(verbosity=2)
