"""公式発走時刻の追記履歴。元のscopeと固定証跡を変更しない。"""
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from check_prediction_compliance import ComplianceError, iso

SCHEMA = "cycle04-official-post-change-v1"
DIRECTORY = "docs/validation/schedule-changes"
VENUES = {"TOK": "東京", "KYO": "京都", "NII": "新潟"}


def require(condition, reason):
    if not condition:
        raise ComplianceError(reason)


def path_at(root, relative):
    require(isinstance(relative, str) and relative and not Path(relative).is_absolute()
            and ".." not in Path(relative).parts, "invalid schedule source path")
    base = Path(root).resolve()
    full = (base / relative).resolve()
    require(full.is_relative_to(base), "schedule source escapes repository")
    return full


def fixed_json(root, ref):
    require(isinstance(ref, dict) and set(ref) == {"artifact_path", "sha256"},
            "fixed schedule artifact path and hash required")
    raw = path_at(root, ref["artifact_path"]).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == ref["sha256"],
            "schedule artifact hash mismatch")
    return json.loads(raw)


def _minute(text, value):
    moment = iso(value, "official post time")
    hour, minute = moment.hour, moment.minute
    return bool(re.search(r"(?<!\d)0?" + str(hour) +
               r"(?:[:：]" + f"{minute:02d}" + r"|時\s*0?" + str(minute) + r"分)(?!\d)", text))


def _source(root, change, race, date):
    ref = change.get("official_text_ref")
    source = fixed_json(root, ref)
    require(isinstance(source, dict) and source.get("provider") == "OFFICIAL"
            and source.get("mode") == "FORWARD"
            and source.get("retrieval_kind") == "PAGE_TEXT",
            "forward official page text required for schedule change")
    url = urlsplit(source.get("source_url", ""))
    require(url.scheme == "https" and url.hostname and
            (url.hostname in ("jra.go.jp", "jra.jp") or
             url.hostname.endswith(".jra.go.jp") or url.hostname.endswith(".jra.jp"))
            and not url.username and not url.password,
            "schedule change must cite a JRA official source")
    body = source.get("text")
    quote = change.get("quotation")
    require(isinstance(body, str) and body and isinstance(quote, dict)
            and set(quote) == {"start", "end", "text"}
            and type(quote["start"]) is int and type(quote["end"]) is int
            and 0 <= quote["start"] < quote["end"] <= len(body)
            and body[quote["start"]:quote["end"]] == quote["text"],
            "schedule change quotation/source text mismatch")
    # 変更の時刻だけでは別レースへの流用を検出できない。
    ident = re.fullmatch(r"\d{8}-(TOK|KYO|NII)-(\d{2})", race)
    require(ident is not None, "unsupported official schedule race identity")
    y, m, d = map(int, date.split("-"))
    excerpt = quote["text"]
    require((date in excerpt or date.replace("-", "") in excerpt or
             re.search(rf"{y}年\s*0?{m}月\s*0?{d}日", excerpt))
            and VENUES[ident[1]] in excerpt
            and re.search(rf"(?<!\d)0?{int(ident[2])}(?:R|レース)(?!\d)", excerpt)
            and "発走" in excerpt
            and not any(word in excerpt for word in ("開催中止", "レース中止", "翌日延期"))
            and _minute(excerpt, change["old_post_time_jst"])
            and _minute(excerpt, change["new_post_time_jst"]),
            "official schedule quotation does not establish date/race/old/new times")
    obtained = iso(source.get("retrieved_at_jst"), "official source retrieval")
    observed = iso(change.get("observed_at_jst"), "schedule observation")
    readback = iso(change.get("readback_verified_at_jst"), "schedule readback")
    require(obtained <= observed <= readback,
            "schedule source retrieval/observation/readback order invalid")
    published = change.get("official_published_at_jst")
    if published is not None:
        require(iso(published, "official publication") <= obtained,
                "official publication later than page retrieval")
    return readback


def history(root, row, race, date, *, now=None):
    """全revisionを毎回原本読戻しする。旧予定は行から絶対に変更しない。"""
    require(isinstance(row, dict), "race record required")
    initial = iso(row.get("scheduled_post_time_jst"), "registered scheduled post")
    refs = row.get("schedule_changes", [])
    require(isinstance(refs, list), "schedule change references must be a list")
    previous_hash = None
    current = initial
    checked = []
    instant = now or datetime.now(timezone.utc)
    for index, ref in enumerate(refs, 1):
        require(isinstance(ref, dict), "schedule change ref required")
        expected_path = f"{DIRECTORY}/{date}/{race}/{index:04d}.json"
        require(ref.get("artifact_path") == expected_path,
                "schedule change revision path mismatch")
        change = fixed_json(root, ref)
        require(change.get("schema_version") == SCHEMA and
                change.get("race_id") == race and change.get("race_date_jst") == date and
                change.get("revision") == index and
                change.get("previous_sha256") == previous_hash,
                "schedule change identity/revision/chain mismatch")
        old_post = iso(change.get("old_post_time_jst"), "old scheduled post")
        new_post = iso(change.get("new_post_time_jst"), "new scheduled post")
        require(old_post == current and old_post != new_post,
                "schedule change must follow previous revision without redefinition")
        require(new_post.date() == initial.date() and new_post.utcoffset() == initial.utcoffset()
                and old_post.utcoffset() == initial.utcoffset(),
                "different-day schedule requires owner confirmation, not automatic migration")
        readback = _source(root, change, race, date)
        require(readback <= instant, "future schedule change observation/readback")
        checked.append((new_post, readback, change))
        current, previous_hash = new_post, ref["sha256"]
    return checked


def effective_post(root, row, race, date, *, at, now=None):
    """その時点までに取得・読戻し済みの変更だけを適用する。"""
    instant = iso(at, "schedule evidence timestamp")
    require(instant <= (now or datetime.now(timezone.utc)), "future evidence timestamp cannot be used")
    post = iso(row.get("scheduled_post_time_jst"), "original post")
    for new_post, readback, _ in history(root, row, race, date, now=now):
        if readback <= instant:
            post = new_post
    return post


def _git_recorded_before(root, race, date, revision, moment):
    """実Git checkoutでは変更原本が証跡時点までにGitへ保存済みか検査する。"""
    if not (Path(root) / ".git").exists():
        return  # isolated synthetic fixtures cannot claim Git provenance
    path = f"{DIRECTORY}/{date}/{race}/{revision:04d}.json"
    command = ["git", "log", "-1", "--diff-filter=A", "--format=%cI",
               "HEAD", "--", path]
    result = subprocess.run(command, cwd=root, text=True, capture_output=True,
                            check=False)
    require(result.returncode == 0 and result.stdout.strip(),
            "schedule change has no tracked Git creation proof")
    require(iso(result.stdout.strip().splitlines()[0], "change Git timestamp") <= iso(moment, "evidence readback"),
            "schedule change committed after claimed evidence/readback")


def assert_post(root, row, race, date, post, *, at, forward=True, now=None):
    """過去のLATEを遅延後に適格化しない。確認後の新規固定は当時予定へ結び付ける。"""
    actual = effective_post(root, row, race, date, at=at, now=now)
    provided = iso(post, "evidence scheduled post")
    require(actual == provided,
            "schedule mismatch: evidence post is not official post known at readback")
    if forward:
        require(iso(at, "evidence readback") < actual,
                "schedule change cannot rehabilitate late/replay evidence")
        applied = [change for changed, readback, change in
                   history(root, row, race, date, now=now)
                   if readback <= iso(at, "evidence readback")]
        if applied:
            _git_recorded_before(root, race, date, applied[-1]["revision"], at)
    return actual


def result_post(root, row, race, date, *, captured_at, result_post_time):
    """結果の公式予定と初回予定の差は同一race/dateのchange-chainでだけ認める。"""
    current = effective_post(root, row, race, date, at=captured_at)
    require(current == iso(result_post_time, "official result post"),
            "official result scheduled post lacks verified schedule history")
    applied = [change for new_post, readback, change in history(root, row, race, date)
               if readback <= iso(captured_at, "result capture")]
    if applied:
        _git_recorded_before(root, race, date, applied[-1]["revision"], captured_at)
    return current


def registered_row(root, race, date):
    """既存の第4台帳だけを見る。未登録の日別台帳を暗黙作成しない。"""
    path = Path(root) / "docs/validation/records/cycle_04" / (date + ".json")
    if not path.is_file():
        return None
    ledger = json.loads(path.read_text(encoding="utf-8"))
    require(ledger.get("cycle_id") == "cycle_04" and
            ledger.get("race_date_jst") == date and
            race in ledger.get("initial_scope", []),
            "registered race/date required for official schedule history")
    return ledger["races"][race]
