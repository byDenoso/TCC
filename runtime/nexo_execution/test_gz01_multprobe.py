from __future__ import annotations

import unittest

from benchmarks.gz01_multprobe_consistency import gaussian_tension, weighted_constant_fit, weighted_linear_fit


class GZ01MultprobeTests(unittest.TestCase):
    def test_nominal_desi_kids_vs_erosita_s8_tension(self):
        result = gaussian_tension(0.771, 0.017, 0.86, 0.01)
        self.assertAlmostEqual(result["z"], 4.5124791264, places=8)

    def test_erosita_redshift_bins_are_not_inconsistent_with_constant_s8(self):
        values = [0.83, 0.82, 0.86, 0.84, 0.94]
        errors = [0.02, 0.07, 0.06, 0.03, 0.04]
        fit = weighted_constant_fit(values, errors)
        self.assertAlmostEqual(fit["mean"], 0.84826073896, places=8)
        self.assertAlmostEqual(fit["chi2"], 6.3707903608, places=8)
        self.assertAlmostEqual(fit["p_value"], 0.1731158850, places=8)

    def test_erosita_linear_s8_redshift_slope_is_hint_level(self):
        redshift = [0.1375, 0.2095, 0.287, 0.391, 0.626]
        values = [0.83, 0.82, 0.86, 0.84, 0.94]
        errors = [0.02, 0.07, 0.06, 0.03, 0.04]
        fit = weighted_linear_fit(redshift, values, errors)
        self.assertAlmostEqual(fit["slope"], 0.1837955, places=6)
        self.assertAlmostEqual(fit["slope_sigma"], 0.08447728, places=6)
        self.assertAlmostEqual(fit["slope_z"], 2.1756797, places=6)


if __name__ == "__main__":
    unittest.main()
