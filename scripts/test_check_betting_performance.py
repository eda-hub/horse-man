"""発走前snapshotに固定された仮想買い目表の読取回帰テスト。"""
from pathlib import Path
import tempfile
import unittest

from check_betting_performance import snapshot_tickets


class FixedTicketReadbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "docs/validation/snapshots/2026-10-11.md"
        self.path.parent.mkdir(parents=True)

    def read(self, section):
        self.path.write_text(
            "## テスト前置き\nsnapshot_id: OTHER\n\n"
            "## 対象\nsnapshot_id: TEST-S01\n" + section,
            encoding="utf-8",
        )
        return snapshot_tickets(
            self.root, "docs/validation/snapshots/2026-10-11.md", "TEST-S01"
        )

    def test_single_trio_from_last_column(self):
        result = self.read(
            "ticket_purpose: OFFICIAL_VIRTUAL\n"
            "### 券種別市場比較\n"
            "| 三連複 | ①-③-⑨ | 200倍 | 30% | 500円 |\n"
            "### 検証用仮想固定買い目\n"
            "| 券種 | 組合せ | オッズ | 確率 | 検証額 |\n"
            "| 三連複 | ①－③－⑨ | 16.5倍 | 11.06% | 10,000円 |\n"
        )
        self.assertEqual(
            result, [{"type": "TRIO", "horses": [1, 3, 9], "stake_yen": 10000}]
        )

    def test_multi_ticket_with_leading_strategy_column(self):
        result = self.read(
            "ticket_purpose: OFFICIAL_VIRTUAL\n"
            "### Production最終検証用仮想買い目と監査\n"
            "| 区分 | 券種 | 組み合わせ | オッズ | 価格 | 検証資金 |\n"
            "| ①期待値型 | ワイド | ⑩－⑯ | 11.4倍 | 1.14 | 7,000円 |\n"
            "| ②高配当型 | ワイド | ⑨－⑯ | 16.1倍 | 1.13 | 3,000円 |\n"
        )
        self.assertEqual(result, [
            {"type": "WIDE", "horses": [10, 16], "stake_yen": 7000},
            {"type": "WIDE", "horses": [9, 16], "stake_yen": 3000},
        ])

    def test_single_win_and_quinella_with_different_amounts(self):
        result = self.read(
            "ticket_purpose: OFFICIAL_VIRTUAL\n"
            "### 検証用固定仮想買い目\n"
            "| 単勝 | ⑪ | 6.0 | 24.0% | 7,000円 |\n"
            "| 馬連 | ④－⑪ | 14.1 | 12.32% | 3,000円 |\n"
        )
        self.assertEqual(result, [
            {"type": "WIN", "horses": [11], "stake_yen": 7000},
            {"type": "QUINELLA", "horses": [4, 11], "stake_yen": 3000},
        ])

    def test_market_table_is_not_fixed_ticket(self):
        with self.assertRaisesRegex(ValueError, "fixed tickets missing"):
            self.read(
                "### 市場・券種の期待値比較\n"
                "| ワイド | ④－⑬ | 7.1倍 | 50% | 10,000円 |\n"
            )

    def test_research_tables_never_become_formal_tickets(self):
        for heading, row in [
            ("研究用の固定反実仮想10,000円（正式日次ROI対象外）",
             "| ワイド | 1-2 | 1,000円 | 5倍 |"),
            ("研究用の反実仮想10,000円",
             "| ワイド | ①－② | 5倍 | 1,000円 |"),
        ]:
            with self.subTest(heading=heading):
                with self.assertRaisesRegex(ValueError, "fixed tickets missing"):
                    self.read("ticket_purpose: OFFICIAL_VIRTUAL\n"
                              + "### " + heading + "\n" + row + "\n")

    def test_counterfactual_metadata_rejects_even_formal_heading(self):
        with self.assertRaisesRegex(ValueError, "not an official"):
            self.read("ticket_purpose: COUNTERFACTUAL\n"
                      "### 検証用仮想購入（正式帳簿）\n"
                      "- 馬連 1-2: 1,000円\n")

    def test_ambiguous_virtual_heading_requires_formal_purpose(self):
        with self.assertRaisesRegex(ValueError, "fixed tickets missing"):
            self.read("### 検証用仮想買い目\n"
                      "| ワイド | ①－② | 5倍 | 1,000円 |\n")

    def test_duplicate_horse_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate horse"):
            self.read(
                "ticket_purpose: OFFICIAL_VIRTUAL\n"
                "### 検証用仮想買い目\n"
                "| ワイド | ④－④ | 10倍 | 10,000円 |\n"
            )


if __name__ == "__main__":
    unittest.main()
