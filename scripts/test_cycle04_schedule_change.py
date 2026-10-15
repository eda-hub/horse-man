#!/usr/bin/env python3
"""公式発走変更の原本・時点・旧履歴保全に関する合成回帰。"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cycle04_schedule_change import (
    SCHEMA, DIRECTORY, history, effective_post, assert_post, result_post,
)
from check_prediction_compliance import ComplianceError

DATE = "2026-10-14"
RACE = "20261014-TOK-01"
ORIGINAL = DATE + "T10:00:00+09:00"


class OfficialScheduleHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.row = {"scheduled_post_time_jst": ORIGINAL, "schedule_changes": []}

    def saved(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = (json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        path.write_bytes(raw)
        return {"artifact_path": name, "sha256": hashlib.sha256(raw).hexdigest()}

    def add_change(self, new_time="10:10", *,
                   old_time="10:00", read="09:22", observed="09:21",
                   obtained="09:20", published=None, venue="東京",
                   source="https://www.jra.go.jp/schedule", mode="FORWARD"):
        number = len(self.row["schedule_changes"]) + 1
        quote = f"2026年10月14日 {venue}1R 発走時刻変更 {old_time} → {new_time}"
        page = {"provider": "OFFICIAL", "mode": mode, "retrieval_kind": "PAGE_TEXT",
                "source_url": source, "text": "公式のお知らせ\n" + quote + "\n",
                "retrieved_at_jst": DATE + "T" + obtained + ":00+09:00"}
        source_ref = self.saved(f"fixtures/official-{number}.json", page)
        event = {"schema_version": SCHEMA, "race_id": RACE,
                 "race_date_jst": DATE, "revision": number,
                 "old_post_time_jst": DATE + "T" + old_time + ":00+09:00",
                 "new_post_time_jst": DATE + "T" + new_time + ":00+09:00",
                 "official_text_ref": source_ref,
                 "quotation": {"start": len("公式のお知らせ\n"),
                               "end": len(page["text"]) - 1, "text": quote},
                 "official_published_at_jst": (DATE + "T" + published + ":00+09:00"
                                               if published else None),
                 "observed_at_jst": DATE + "T" + observed + ":00+09:00",
                 "readback_verified_at_jst": DATE + "T" + read + ":00+09:00",
                 "previous_sha256": (self.row["schedule_changes"][-1]["sha256"]
                                     if number > 1 else None)}
        path = f"{DIRECTORY}/{DATE}/{RACE}/{number:04d}.json"
        ref = self.saved(path, event)
        self.row["schedule_changes"].append(ref)
        return event, ref

    def test_no_change_preserves_direct_match(self):
        self.assertEqual(effective_post(self.root, self.row, RACE, DATE,
                                        at=DATE+"T09:30:00+09:00").isoformat(), ORIGINAL)
        assert_post(self.root, self.row, RACE, DATE, ORIGINAL,
                    at=DATE+"T09:30:00+09:00")
        with self.assertRaises(ComplianceError):
            result_post(self.root, self.row, RACE, DATE,
                        captured_at=DATE+"T11:00:00+09:00",
                        result_post_time=DATE+"T10:10:00+09:00")

    def test_delayed_and_prior_evidence_are_separate(self):
        self.add_change()
        assert_post(self.root, self.row, RACE, DATE, ORIGINAL,
                    at=DATE+"T09:19:00+09:00")
        assert_post(self.root, self.row, RACE, DATE, DATE+"T10:10:00+09:00",
                    at=DATE+"T09:30:00+09:00")
        with self.assertRaises(ComplianceError):
            assert_post(self.root, self.row, RACE, DATE, DATE+"T10:10:00+09:00",
                        at=DATE+"T09:19:00+09:00")
        self.assertEqual(result_post(self.root, self.row, RACE, DATE,
                                     captured_at=DATE+"T10:20:00+09:00",
                                     result_post_time=DATE+"T10:10:00+09:00").hour, 10)

    def test_late_original_cannot_be_rehabilitated(self):
        self.add_change(obtained="10:02", observed="10:03", read="10:04")
        with self.assertRaises(ComplianceError):
            assert_post(self.root, self.row, RACE, DATE, ORIGINAL,
                        at=DATE+"T10:01:00+09:00")
        assert_post(self.root, self.row, RACE, DATE, DATE+"T10:10:00+09:00",
                    at=DATE+"T10:05:00+09:00")

    def test_two_changes_are_chained(self):
        self.add_change()
        self.add_change(old_time="10:10", new_time="10:20", obtained="09:29",
                        observed="09:30", read="09:31")
        self.assertEqual(len(history(self.root, self.row, RACE, DATE)), 2)
        self.assertEqual(effective_post(self.root, self.row, RACE, DATE,
                                        at=DATE+"T09:25:00+09:00").minute, 10)
        self.assertEqual(effective_post(self.root, self.row, RACE, DATE,
                                        at=DATE+"T09:35:00+09:00").minute, 20)

    def test_revisions_cannot_be_observed_out_of_order(self):
        self.add_change(read="09:30", observed="09:29", obtained="09:28")
        self.add_change(old_time="10:10", new_time="10:20",
                        obtained="09:21", observed="09:22", read="09:23")
        with self.assertRaises(ComplianceError):
            history(self.root, self.row, RACE, DATE)

    def test_advance_invalidates_old_late_gate(self):
        self.add_change(old_time="10:00", new_time="09:50")
        with self.assertRaises(ComplianceError):
            assert_post(self.root, self.row, RACE, DATE, ORIGINAL,
                        at=DATE+"T09:55:00+09:00")
        with self.assertRaises(ComplianceError):
            assert_post(self.root, self.row, RACE, DATE, DATE+"T09:50:00+09:00",
                        at=DATE+"T09:55:00+09:00")

    def test_duplicate_revision_and_chain_divergence_fail(self):
        self.add_change()
        self.row["schedule_changes"].append(self.row["schedule_changes"][0])
        with self.assertRaises(ComplianceError):
            history(self.root, self.row, RACE, DATE)
        self.row["schedule_changes"].pop()
        _, ref = self.add_change(old_time="10:10", new_time="10:20",
                                 obtained="09:23", observed="09:24", read="09:25")
        event = json.loads((self.root / ref["artifact_path"]).read_text())
        event["previous_sha256"] = "0"*64
        self.row["schedule_changes"][-1] = self.saved(ref["artifact_path"], event)
        with self.assertRaises(ComplianceError):
            history(self.root, self.row, RACE, DATE)

    def test_tampering_and_wrong_race_or_source_fail(self):
        _, ref = self.add_change()
        with (self.root / ref["artifact_path"]).open("a") as handle:
            handle.write("altered")
        with self.assertRaises(ComplianceError):
            history(self.root, self.row, RACE, DATE)
        self.row["schedule_changes"].clear()
        self.add_change(venue="京都")
        with self.assertRaises(ComplianceError):
            history(self.root, self.row, RACE, DATE)
        self.row["schedule_changes"].clear()
        self.add_change(source="https://nonofficial.example.com/")
        with self.assertRaises(ComplianceError):
            history(self.root, self.row, RACE, DATE)

    def test_official_quote_cannot_reverse_advance_into_delay(self):
        # 公式は10:10→10:00。変更原本が逆順を宣言しても許容しない。
        self.row["scheduled_post_time_jst"] = DATE + "T10:00:00+09:00"
        _, ref = self.add_change(old_time="10:00", new_time="10:10")
        event = json.loads((self.root / ref["artifact_path"]).read_text())
        source_ref = event["official_text_ref"]
        official = json.loads((self.root / source_ref["artifact_path"]).read_text())
        actual_quote = "2026年10月14日 東京1R 発走時刻変更 10:10 → 10:00"
        official["text"] = "公式のお知らせ\n" + actual_quote + "\n"
        event["official_text_ref"] = self.saved(source_ref["artifact_path"], official)
        event["quotation"]["text"] = actual_quote
        event["quotation"]["end"] = event["quotation"]["start"] + len(actual_quote)
        self.row["schedule_changes"][-1] = self.saved(ref["artifact_path"], event)
        with self.assertRaisesRegex(ComplianceError, "direction"):
            history(self.root, self.row, RACE, DATE)

    def test_quotation_with_unrelated_times_is_not_direction_proof(self):
        _, ref = self.add_change()
        event = json.loads((self.root / ref["artifact_path"]).read_text())
        source_ref = event["official_text_ref"]
        official = json.loads((self.root / source_ref["artifact_path"]).read_text())
        quote = "2026年10月14日 東京1R 発走時刻変更 10:00 と 10:10"
        official["text"] = "公式のお知らせ\n" + quote + "\n"
        event["official_text_ref"] = self.saved(source_ref["artifact_path"], official)
        event["quotation"]["text"] = quote
        event["quotation"]["end"] = event["quotation"]["start"] + len(quote)
        self.row["schedule_changes"][-1] = self.saved(ref["artifact_path"], event)
        with self.assertRaisesRegex(ComplianceError, "direction"):
            history(self.root, self.row, RACE, DATE)

    def rewrite_quote(self, ref, quote):
        event = json.loads((self.root / ref["artifact_path"]).read_text())
        source_ref = event["official_text_ref"]
        source = json.loads((self.root / source_ref["artifact_path"]).read_text())
        prefix = "公式のお知らせ\n"
        source["text"] = prefix + quote + "\n"
        event["official_text_ref"] = self.saved(source_ref["artifact_path"], source)
        event["quotation"] = {"start": len(prefix), "end": len(prefix) + len(quote),
                              "text": quote}
        self.row["schedule_changes"][-1] = self.saved(ref["artifact_path"], event)

    def test_wrong_venue_change_cannot_be_borrowed(self):
        _, ref = self.add_change()
        self.rewrite_quote(
            ref, "2026年10月14日 東京1R 発走予定10:00。"
                 "京都1R 発走変更10:00 → 10:10")
        with self.assertRaisesRegex(ComplianceError, "ambiguous venue/race"):
            history(self.root, self.row, RACE, DATE)

    def test_other_race_change_cannot_be_borrowed(self):
        _, ref = self.add_change()
        self.rewrite_quote(
            ref, "2026年10月14日 東京1R 発走予定10:00。"
                 "東京2R 発走変更10:00 → 10:10")
        with self.assertRaisesRegex(ComplianceError, "ambiguous venue/race"):
            history(self.root, self.row, RACE, DATE)

    def test_unobserved_advance_blocks_late_snapshot(self):
        self.add_change(old_time="10:00", new_time="09:50",
                        obtained="10:01", observed="10:02", read="10:03")
        # 読戻し時点の認識は10:00だが、実際は09:50に前倒しされていた。
        with self.assertRaisesRegex(ComplianceError, "later official advance"):
            assert_post(self.root, self.row, RACE, DATE, ORIGINAL,
                        at=DATE+"T09:55:00+09:00")
        # 発走前の既存原本は改変不要で、引き続き照合できる。
        assert_post(self.root, self.row, RACE, DATE, ORIGINAL,
                    at=DATE+"T09:45:00+09:00")

    def test_japanese_clock_and_advance_are_recognized(self):
        _, ref = self.add_change(new_time="09:50")
        self.rewrite_quote(ref, "2026年10月14日 東京1R 発走時刻変更 10時00分 → 9時50分")
        self.assertEqual(len(history(self.root, self.row, RACE, DATE)), 1)
        assert_post(self.root, self.row, RACE, DATE, DATE+"T09:50:00+09:00",
                    at=DATE+"T09:30:00+09:00")

    def test_future_reversed_and_cross_day_fail(self):
        self.add_change(obtained="09:25", observed="09:21", read="09:22")
        with self.assertRaises(ComplianceError):
            history(self.root, self.row, RACE, DATE)
        self.row["schedule_changes"].clear()
        self.add_change(obtained="23:10", observed="23:11", read="23:12")
        with self.assertRaises(ComplianceError):
            history(self.root, self.row, RACE, DATE,
                    now=__import__("datetime").datetime.fromisoformat(DATE+"T10:00:00+09:00"))
        self.row["schedule_changes"].clear()
        event, ref = self.add_change()
        event["new_post_time_jst"] = "2026-10-15T10:10:00+09:00"
        self.row["schedule_changes"][-1] = self.saved(ref["artifact_path"], event)
        with self.assertRaises(ComplianceError):
            history(self.root, self.row, RACE, DATE)


if __name__ == "__main__":
    unittest.main()
