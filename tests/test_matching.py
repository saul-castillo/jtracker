import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from jtracker.matching import evaluate, target_term
from jtracker.runner import legacy_key, quiet_hours, stable_key


def job(title, description="", location="Austin, TX", country_code="US", **extra):
    value = {
        "company": "Example",
        "platform": "Workday",
        "source_id": "123",
        "title": title,
        "description": description,
        "location": location,
        "country_code": country_code,
        "url": "https://example.com/jobs/123",
    }
    value.update(extra)
    return value


class TermTests(unittest.TestCase):
    def test_explicit_summer_2027(self):
        self.assertEqual(target_term("Hardware Intern", "Summer 2027"), (True, "Summer 2027"))

    def test_multiple_terms_keeps_summer(self):
        valid, _ = target_term(
            "Electrical Engineering Intern",
            "Open for Fall 2026, Spring 2027, and Summer 2027.",
        )
        self.assertTrue(valid)

    def test_compound_term_with_shared_year_keeps_summer(self):
        valid, _ = target_term("Electrical Engineering Intern - Spring/Summer 2027", "")
        self.assertTrue(valid)

    def test_fall_only_is_rejected(self):
        valid, _ = target_term("Electrical Engineering Intern - Fall 2027", "")
        self.assertFalse(valid)

    def test_spring_coop_with_separated_year_is_rejected(self):
        valid, _ = target_term(
            "Electrical Engineering Spring Co-op (January 2027)",
            "Our 2027 Co-Op program offers hands-on hardware experience.",
        )
        self.assertFalse(valid)

    def test_graduation_year_is_not_a_target_term(self):
        valid, _ = target_term(
            "Electrical Engineering Intern",
            "Candidates graduating in 2027 or 2028 may apply.",
        )
        self.assertFalse(valid)

    def test_generic_2027_intern_title(self):
        valid, _ = target_term("2027 Electrical Engineer Intern", "")
        self.assertTrue(valid)


class MatchingTests(unittest.TestCase):
    def test_generic_title_uses_description(self):
        result = evaluate(
            job(
                "2027 Engineering Intern",
                "Work on FPGA prototyping, SystemVerilog, and ASIC design verification.",
            )
        )
        self.assertTrue(result.matched)

    def test_web_software_is_rejected_despite_chip_boilerplate(self):
        result = evaluate(
            job(
                "Software Engineering Intern - Summer 2027",
                "We are a semiconductor hardware company. Build web services and cloud APIs.",
            )
        )
        self.assertFalse(result.matched)

    def test_generic_cpp_software_is_not_mistaken_for_embedded(self):
        result = evaluate(
            job(
                "Software Engineer Intern - C++, Summer 2027",
                "Interns are embedded on teams working on cloud systems and may interface "
                "with hardware groups.",
            )
        )
        self.assertFalse(result.matched)

    def test_firmware_is_included(self):
        result = evaluate(
            job(
                "Firmware Engineering Intern",
                "Summer 2027. Develop embedded firmware for microcontrollers and board bring-up.",
            )
        )
        self.assertTrue(result.matched)

    def test_phd_only_title_is_rejected(self):
        result = evaluate(
            job(
                "PhD Hardware Research Intern - Summer 2027",
                "ASIC and architecture research.",
            )
        )
        self.assertFalse(result.matched)

    def test_full_state_name_is_us(self):
        result = evaluate(
            job(
                "Analog Design Intern - Summer 2027",
                location="Wilmington, Massachusetts",
                country_code="",
            )
        )
        self.assertTrue(result.matched)

    def test_non_us_is_rejected(self):
        result = evaluate(
            job(
                "Analog Design Intern - Summer 2027",
                location="Toronto, Ontario, Canada",
                country_code="CA",
            )
        )
        self.assertFalse(result.matched)


class StateTests(unittest.TestCase):
    def test_new_and_legacy_keys_are_distinct_and_stable(self):
        sample = job("Analog Design Intern - Summer 2027")
        self.assertEqual(stable_key(sample), stable_key(dict(sample)))
        self.assertEqual(legacy_key(sample), legacy_key(dict(sample)))
        self.assertNotEqual(stable_key(sample), legacy_key(sample))

    def test_quiet_hours(self):
        tz = ZoneInfo("America/New_York")
        self.assertTrue(quiet_hours(datetime(2026, 7, 23, 23, 0, tzinfo=tz)))
        self.assertTrue(quiet_hours(datetime(2026, 7, 23, 7, 59, tzinfo=tz)))
        self.assertFalse(quiet_hours(datetime(2026, 7, 23, 8, 0, tzinfo=tz)))
        self.assertFalse(quiet_hours(datetime(2026, 7, 23, 22, 59, tzinfo=tz)))


if __name__ == "__main__":
    unittest.main()
