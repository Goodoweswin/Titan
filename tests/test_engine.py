import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from titan_wb.engine import dispatch


class EngineTests(unittest.TestCase):
    def test_health_protocol_version(self):
        self.assertEqual(dispatch({'command': 'health'})['protocol'], 1)

    def test_real_pixel_probe(self):
        self.assertEqual(dispatch({'command': 'probe'})['corrected_sum'], 80)

    def test_unknown_command_is_not_executed(self):
        with self.assertRaises(ValueError):
            dispatch({'command': '__import__("os").system("false")'})

    def test_json_process_contract(self):
        p = subprocess.run([sys.executable, str(ROOT / 'backend/entry.py')],
                           input=json.dumps({'command': 'probe'}), text=True,
                           capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        data = json.loads(p.stdout)
        self.assertTrue(data['ok'])
        self.assertEqual(data['data']['corrected_sum'], 80)


if __name__ == '__main__':
    unittest.main()
