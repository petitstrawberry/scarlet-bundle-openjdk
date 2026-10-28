"""Require actual compilation records even when native output is interleaved."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("run_java", Path(__file__).with_name("run-java.py"))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class CompilationLogTests(unittest.TestCase):
    def test_requires_requested_tier_and_osr(self):
        c1 = '231 42    b  3       Tiered::dispatch (10 bytes)\n'
        c2 = '240 43    b  4       Tiered::dispatch (10 bytes)\n'
        osr = '250 44 %  b  4       Tiered::osr @ 4 (31 bytes)\n'
        self.assertFalse(runner.compiled_method(c1, 'Tiered', 'dispatch', level=4))
        self.assertTrue(runner.compiled_method(c1 + c2, 'Tiered', 'dispatch', level=4))
        self.assertTrue(runner.compiled_method(osr, 'Tiered', 'osr', level=4, osr=True))
        self.assertFalse(runner.compiled_method(c2, 'Tiered', 'dispatch', level=4, osr=True))
        self.assertFalse(runner.compiled_method(c2.rstrip() + ' made not entrant\n',
                                               'Tiered', 'dispatch', level=4))

    def test_requires_real_c2_deoptimization(self):
        records = ''.join(f'230 42 b {level} Tiered::{name} (10 bytes)\n'
                          for name in ('dispatch', 'materialize') for level in (3, 4))
        records += '250 44 % b 4 Tiered::osr @ 4 (31 bytes)\n'
        deopt = ('[1s][debug][deoptimization] cid=42 level=4 '
                 'Tiered.materialize(IZ)I trap_bci=10 unstable_if reinterpret pc=123\n')
        self.assertFalse(runner.tiered_evidence(records))
        self.assertFalse(runner.tiered_evidence(records + deopt.replace('level=4', 'level=3')))
        self.assertTrue(runner.tiered_evidence(records + deopt))

    def test_compilation_after_another_threads_prefix(self):
        record = "1923   22    b        JitStress::recurse (9 bytes)\r\n"
        for prefix in ("", "### Excluding compile: java.lang.Throwable::"):
            self.assertTrue(runner.compiled_method(prefix + record, "JitStress", "recurse"))

    def test_exclusions_and_markers_are_not_compilation_evidence(self):
        for text in ("### Excluding compile: JitStress::recurse\n",
                     "made not compilable on level 1 JitStress::recurse (9 bytes)\n",
                     "OPENJDK_JIT_STRESS PASS threads=4 gc=8 null=32 stack=4 roots=ok\n",
                     "1923\n22 b JitStress::recurse (9 bytes)\n",
                     "1923 22 b JitStress::field (9 bytes)\n"):
            self.assertFalse(runner.compiled_method(text, "JitStress", "recurse"))
