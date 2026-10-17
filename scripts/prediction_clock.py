"""JST発走予定と観測時計を分離して判定する。過去の保存証拠は現在時計で上書きしない。"""
from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))
MAX_AGE_SECONDS = 5.0
MAX_DRIFT_SECONDS = 2.0


def aware(value, label="datetime"):
    """オフセット付きの秒精度以上の日時だけを受理する。"""
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        if not re.search(r"(?:Z|[+-]\d\d:\d\d)$", value):
            raise ValueError(label + ": timezone offset required")
        if not re.search(r"T\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$", value):
            raise ValueError(label + ": second resolution required")
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError(label + ": timestamp required")
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(label + ": timezone offset required")
    return result.astimezone(timezone.utc)


@dataclass(frozen=True)
class ClockSample:
    observed_at: str
    monotonic_at: float
    resolution_seconds: float = 0.001
    origin: str = "runtime"

    @classmethod
    def capture(cls, *, wall=None, monotonic=None, resolution_seconds=0.001, origin="runtime"):
        stamp = wall if wall is not None else datetime.now(timezone.utc)
        stamp = aware(stamp, "clock capture")
        return cls(stamp.isoformat(),
                   float(monotonic if monotonic is not None else time.monotonic()),
                   resolution_seconds, origin)


def assess_clock(*, scheduled_post, race_date, race_id, official_race_date,
                 official_race_id, sample, decision_wall=None, decision_monotonic=None,
                 official_source=None, max_age_seconds=MAX_AGE_SECONDS):
    """比較の結果を構造化。未確認の時計/公式出所は発走後と断定しない。"""
    result = dict(status="UNDETERMINED", remaining_seconds=None, reason=None,
                  race_date=race_date, race_id=race_id, scheduled_post_jst=None,
                  decision_at_jst=None, observed_at_jst=None, official_source=official_source,
                  clock_origin=None, clock_age_seconds=None, uncertainty_seconds=None)
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", race_date or "") or not race_id:
            raise ValueError("race identity missing")
        if race_date != official_race_date or race_id != official_race_id or not official_source:
            raise ValueError("official race/date/source mismatch")
        post = aware(scheduled_post, "scheduled post")
        if post.astimezone(JST).date().isoformat() != race_date:
            raise ValueError("scheduled post date mismatch")
        if sample is None or decision_wall is None or decision_monotonic is None:
            raise ValueError("clock unavailable")
        if not isinstance(sample, ClockSample):
            raise ValueError("clock sample invalid")
        observed = aware(sample.observed_at, "clock observation")
        actual_wall = aware(decision_wall, "decision clock")
        delta = float(decision_monotonic) - sample.monotonic_at
        if delta < 0:
            raise ValueError("monotonic clock reversed")
        if delta > max_age_seconds:
            raise ValueError("stale clock observation")
        if not 0 < sample.resolution_seconds <= 1:
            raise ValueError("clock resolution insufficient")
        predicted = observed + timedelta(seconds=delta)
        drift = abs((actual_wall - predicted).total_seconds())
        if drift > MAX_DRIFT_SECONDS:
            raise ValueError("clock drift exceeds 2 seconds")
        # 観測/判定値の差が境界に影響する場合は安全側で未判定。
        uncertainty = sample.resolution_seconds / 2 + drift
        remain = (post - predicted).total_seconds()
        result.update(scheduled_post_jst=post.astimezone(JST).isoformat(),
                      observed_at_jst=observed.astimezone(JST).isoformat(),
                      decision_at_jst=predicted.astimezone(JST).isoformat(),
                      clock_origin=sample.origin, clock_age_seconds=delta,
                      uncertainty_seconds=uncertainty)
        if -uncertainty <= remain <= uncertainty:
            raise ValueError("scheduled post boundary uncertain")
        result.update(status="PRE_SCHEDULED" if remain > 0 else "SCHEDULE_REACHED",
                      remaining_seconds=round(remain, 6), reason="clock and official schedule verified")
    except (ValueError, OverflowError, TypeError) as exc:
        result["reason"] = str(exc)
    return result


def observed_assessment(root, date, race, *, sample=None, wall=None, mono=None):
    """登録済み第4公式scope/公式変更chainから当時認識可能な発走予定を取得。"""
    from cycle04_schedule_change import registered_row, effective_post
    sample = sample or ClockSample.capture()
    wall = wall or datetime.now(timezone.utc)
    mono = mono if mono is not None else time.monotonic()
    row = registered_row(Path(root), race, date)
    if row is None:
        return assess_clock(scheduled_post=None, race_date=date, race_id=race,
                            official_race_date=None, official_race_id=None,
                            official_source=None, sample=sample,
                            decision_wall=wall, decision_monotonic=mono)
    post = effective_post(Path(root), row, race, date, at=sample.observed_at,
                          now=wall)
    return assess_clock(scheduled_post=post, race_date=date, race_id=race,
                        official_race_date=date, official_race_id=race,
                        official_source="cycle04_official_schedule_chain",
                        sample=sample, decision_wall=wall, decision_monotonic=mono)


def safe_for_write(result):
    return result.get("status") == "PRE_SCHEDULED"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--date", required=True)
    parser.add_argument("--race-id", required=True)
    args = parser.parse_args(argv)
    try:
        result = observed_assessment(args.root, args.date, args.race_id)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {"status": "UNDETERMINED", "remaining_seconds": None,
                  "reason": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if safe_for_write(result) else 1


if __name__ == "__main__":
    raise SystemExit(main())
