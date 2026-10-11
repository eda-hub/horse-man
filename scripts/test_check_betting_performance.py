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

    def test_duplicate_horse_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate horse"):
            self.read(
                "### 検証用仮想買い目\n"
                "| ワイド | ④－④ | 10倍 | 10,000円 |\n"
            )


if __name__ == "__main__":
    unittest.main()
