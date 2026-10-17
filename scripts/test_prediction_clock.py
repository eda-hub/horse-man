"""時計の固定回帰：判定時刻、境界、鮮度、出所の正しさ。"""
import unittest
from datetime import datetime, timedelta, timezone
from prediction_clock import ClockSample, assess_clock, aware, JST


class PredictionClockTest(unittest.TestCase):
    def check(self, now, post="2026-10-17T15:15:00+09:00", *, race_date="2026-10-17",
              race_id="2026-10-17-NIIGATA-11", resolution=.000001, lag=0):
        observed = aware(now)
        sample = ClockSample(observed.isoformat(), 100.0, resolution)
        return assess_clock(
            scheduled_post=post, race_date=race_date, race_id=race_id,
            official_race_date=race_date, official_race_id=race_id,
            official_source="fixture verified official scope", sample=sample,
            decision_wall=observed + timedelta(seconds=lag),
            decision_monotonic=100.0 + lag)

    def test_niigata_1510_not_after(self):
        r = self.check("2026-10-17T15:10:00+09:00")
        self.assertEqual(("PRE_SCHEDULED", 300), (r["status"], r["remaining_seconds"]))

    def test_niigata_evidence_milestones(self):
        expected = [
            ("2026-10-17T15:12:13+09:00", 167),
            ("2026-10-17T15:12:58.459+09:00", 121.541),
            ("2026-10-17T15:13:11.764+09:00", 108.236),
        ]
        for instant, remain in expected:
            with self.subTest(instant=instant):
                self.assertEqual(self.check(instant)["remaining_seconds"], remain)

    def test_same_utc_and_jst(self):
        self.assertEqual(self.check("2026-10-17T06:10:00Z")["remaining_seconds"], 300)
        self.assertEqual(self.check("2026-10-17T15:10:00+09:00")["remaining_seconds"], 300)

    def test_race_boundary(self):
        for suffix, state in [
            (".999000", "PRE_SCHEDULED"),
            (".000000", "UNDETERMINED"),
            (".001000", "SCHEDULE_REACHED"),
        ]:
            instant = ("2026-10-17T15:14:59" if suffix.startswith(".999") else "2026-10-17T15:15:00") + suffix + "+09:00"
            self.assertEqual(self.check(instant)["status"], state)

    def test_earlier_examples_from_september(self):
        post = "2026-09-22T14:50:00+09:00"
        r = self.check("2026-09-22T14:40:00+09:00", post,
                       race_date="2026-09-22", race_id="R")
        self.assertEqual(r["remaining_seconds"], 600)
        r = self.check("2026-09-22T16:02:00+09:00",
                       "2026-09-22T16:10:00+09:00",
                       race_date="2026-09-22", race_id="R")
        self.assertEqual(r["remaining_seconds"], 480)

    def test_cross_midnight(self):
        result = self.check("2026-10-17T23:59:59+09:00",
                            "2026-10-18T00:00:01+09:00",
                            race_date="2026-10-18", race_id="R")
        self.assertEqual(result["remaining_seconds"], 2)

    def test_source_or_date_mismatch(self):
        result = self.check("2026-10-17T15:10:00+09:00",
                            race_date="2026-10-16")
        self.assertEqual(result["status"], "UNDETERMINED")
        self.assertIsNone(result["remaining_seconds"])

    def test_naive_and_minute_time_rejected(self):
        with self.assertRaises(ValueError):
            aware("2026-10-17T15:10:00")
        with self.assertRaises(ValueError):
            aware("2026-10-17T15:10+09:00")
        sample = ClockSample("2026-10-17T15:10:00+09:00", 100, 60)
        r = assess_clock(scheduled_post="2026-10-17T15:15:00+09:00",
                         race_date="2026-10-17", race_id="R",
                         official_race_date="2026-10-17", official_race_id="R",
                         official_source="official", sample=sample,
                         decision_wall=aware(sample.observed_at), decision_monotonic=100)
        self.assertEqual(r["status"], "UNDETERMINED")

    def test_stale_and_monotonic_reversal(self):
        for mono in (106, 99):
            sample = ClockSample("2026-10-17T15:10:00+09:00", 100)
            r = assess_clock(scheduled_post="2026-10-17T15:15:00+09:00",
                             race_date="2026-10-17", race_id="R",
                             official_race_date="2026-10-17", official_race_id="R",
                             official_source="official", sample=sample,
                             decision_wall=aware(sample.observed_at), decision_monotonic=mono)
            self.assertEqual(r["status"], "UNDETERMINED")

    def test_large_wall_clock_jump(self):
        sample = ClockSample("2026-10-17T15:10:00+09:00", 100)
        r = assess_clock(scheduled_post="2026-10-17T15:15:00+09:00",
                         race_date="2026-10-17", race_id="R",
                         official_race_date="2026-10-17", official_race_id="R",
                         official_source="official", sample=sample,
                         decision_wall=aware(sample.observed_at)+timedelta(seconds=10),
                         decision_monotonic=101)
        self.assertEqual(r["status"], "UNDETERMINED")

    def test_millisecond_boundary_with_coarse_clock_is_unknown(self):
        result = self.check("2026-10-17T15:14:59.999+09:00", resolution=.01)
        self.assertEqual(result["status"], "UNDETERMINED")


if __name__ == "__main__":
    unittest.main()
