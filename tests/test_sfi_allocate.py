"""Ch 3.1 S2 — SFI allocation + auto-create gate rules."""
import unittest
from pipeline import sfi_allocate as sa


class TestOccupancy(unittest.TestCase):
    STRUCT = {"nodes": [{"name": "650, Monitoring"}, {"name": "651, BAE system"},
                        {"name": "652, ONYX"}, {"name": "360, Galley"},
                        {"name": "Some file.pdf"}, {"name": "100, Structure"}]}
    REG = {"entries": [{"equipment_id": "652-onyx-monitoring", "subsystem_code": "652", "retired": False},
                       {"equipment_id": "360-oven", "subsystem_code": "360", "retired": False},
                       {"equipment_id": "999-dead", "subsystem_code": "999", "retired": True}]}

    def test_yard_codes(self):
        self.assertEqual(sa.yard_occupied_codes(self.STRUCT), {"650", "651", "652", "360", "100"})

    def test_register_codes_skip_retired(self):
        c = sa.register_occupied_codes(self.REG)
        self.assertIn("652", c); self.assertIn("360", c); self.assertNotIn("999", c)

    def test_is_free(self):
        self.assertFalse(sa.is_free("651", self.STRUCT, self.REG))  # yard
        self.assertFalse(sa.is_free("652", self.STRUCT, self.REG))  # both
        self.assertTrue(sa.is_free("653", self.STRUCT, self.REG))   # neither

    def test_651_mistake_would_not_recur(self):
        # the real bug: assigning 650+1 blindly. allocate_in_range must skip 651/652.
        got = sa.allocate_in_range(650, 656, self.STRUCT, self.REG)
        self.assertEqual(got, "653")

    def test_allocate_range(self):
        self.assertEqual(sa.allocate_in_range(360, 370, self.STRUCT, self.REG), "361")

    def test_range_exhausted_raises(self):
        struct = {"nodes": [{"name": f"{c}, x"} for c in range(510, 516)]}
        with self.assertRaises(ValueError):
            sa.allocate_in_range(510, 515, struct, {"entries": []})

    def test_next_free_after(self):
        self.assertEqual(sa.next_free_after("360", self.STRUCT, self.REG), "361")


class TestAutoCreateGate(unittest.TestCase):
    def test_auto_create_all_three(self):
        r = sa.classify_creation("Grundfos", "CRN-15", "seawater cooling pump")
        self.assertEqual(r["action"], "auto_create")

    def test_flag_missing_model(self):
        r = sa.classify_creation("Mastervolt", None, "battery charger")
        self.assertEqual(r["action"], "create_flagged")
        self.assertIn("model", r["missing"])

    def test_flag_missing_make(self):
        r = sa.classify_creation("", "A-300", "watermaker")
        self.assertIn("make", sa.classify_creation("", "A-300", "watermaker")["missing"])

    def test_flag_unrecognized_class(self):
        r = sa.classify_creation("Acme", "X1", "gizmo widget thing")
        self.assertEqual(r["action"], "create_flagged")
        self.assertIn("recognizable_equipment_class", r["missing"])

    def test_known_class_variants(self):
        for k in ("bilge pump", "circuit breaker", "LED light", "current transformer", "bow thruster"):
            self.assertEqual(sa.classify_creation("M", "X", k)["action"], "auto_create", k)


if __name__ == "__main__":
    unittest.main(verbosity=2)
