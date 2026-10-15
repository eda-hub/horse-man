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
    # 旧→新の向きだけでなく、日付・開催場・レース・時刻が
    # *同一の記載* に結び付いているかを検査する。別場/別レースの
    # 発走変更との寄せ集めは、正式認証せず保留する。
    ident = re.fullmatch(r"\d{8}-(TOK|KYO|NII)-(\d{2})", race)
    require(ident is not None, "unsupported official schedule race identity")
    y, m, d = map(int, date.split("-"))
    excerpt = quote["text"]
    require(not any(word in excerpt for word in ("開催中止", "レース中止", "翌日延期")),
            "cancelled or postponed schedule requires owner confirmation")
    venue_mentions = re.findall("|".join(map(re.escape, VENUES.values())), excerpt)
    race_mentions = re.findall(r"(?<!\d)0?([1-9]|1[0-2])(?:R|レース)(?!\d)", excerpt)
    require(venue_mentions == [VENUES[ident[1]]] and
            race_mentions == [str(int(ident[2]))],
            "official schedule quotation contains ambiguous venue/race identity")

    clock = r"(?:[01]?\d|2[0-3])(?:[:：][0-5]\d|時\s*[0-5]?\d分)"
    transition = re.compile(
        rf"(?<!\d)({clock})\s*(?:→|⇒|->|から)\s*({clock})(?!\d)"
    )
    def normalize_clock(value):
        match = re.fullmatch(r"(\d{1,2})(?:[:：](\d{2})|時\s*(\d{1,2})分)", value)
        require(match is not None, "invalid official post time in quotation")
        return f"{int(match[1]):02d}:{int(match[2] or match[3]):02d}"

    expected = (iso(change["old_post_time_jst"], "old official post").strftime("%H:%M"),
                iso(change["new_post_time_jst"], "new official post").strftime("%H:%M"))
    records = [part.strip() for part in re.split(r"[。\r\n；;]", excerpt) if part.strip()]
    matches = []
    for record in records:
        if VENUES[ident[1]] not in record or not re.search(
                rf"(?<!\d)0?{int(ident[2])}(?:R|レース)(?!\d)", record):
            continue
        date_present = (date in record or date.replace("-", "") in record or
                        re.search(rf"{y}年\s*0?{m}月\s*0?{d}日", record))
        changes = transition.findall(record)
        if date_present and "発走" in record and "変更" in record and len(changes) == 1:
            matches.append(changes[0])
    # 同じレースの1記載に唯一の変更が示されている場合のみ認証。
    # 無関係な行に別の変更があれば、引用範囲を絞るまで認証しない。
    require(len(matches) == 1 and len(transition.findall(excerpt)) == 1 and
            tuple(normalize_clock(value) for value in matches[0]) == expected,
            "official schedule quotation does not prove race-bound old-to-new direction")
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
    previous_readback = None
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
        require(previous_readback is None or previous_readback < readback,
                "schedule revision observations must follow previous readback")
        require(readback <= instant, "future schedule change observation/readback")
        previous_readback = readback
        checked.append((new_post, readback, change))
        current, previous_hash = new_post, ref["sha256"]
    return checked


def effective_post(root, row, race, date, *, at, now=None):
    """その時点までに取得・読戻し済みの変更だけを適用する。"""
    instant = iso(at, "schedule evidence timestamp")
    post = iso(row.get("scheduled_post_time_jst"), "original post")
    for new_post, readback, _ in history(root, row, race, date, now=now):
        if readback <= instant:
            post = new_post
    return post


def _git_recorded_before(root, race, date, revision, moment, source_ref=None):
    """公式本文と変更原本のGit初出bytesが、利用証跡より前に固定されているか。"""
    if not (Path(root) / ".git").exists():
        return  # unit-test fixture only: no production Git provenance claim

    def check_path(relative):
        path = path_at(root, relative)
        command = ["git", "log", "-1", "--diff-filter=A", "--format=%H %cI",
                   "HEAD", "--", relative]
        result = subprocess.run(command, cwd=root, capture_output=True,
                                text=True, check=False)
        require(result.returncode == 0 and result.stdout.strip(),
                "schedule original has no tracked Git creation proof")
        sha, recorded = result.stdout.strip().splitlines()[0].split(maxsplit=1)
        require(iso(recorded, "Git original timestamp") <= iso(moment, "evidence readback"),
                "schedule original was committed after evidence/readback")
        original = subprocess.run(["git", "show", sha + ":" + relative],
                                  cwd=root, capture_output=True, check=False)
        require(original.returncode == 0 and
                hashlib.sha256(original.stdout).digest() ==
                hashlib.sha256(path.read_bytes()).digest(),
                "schedule original bytes differ from Git creation proof")

    check_path(f"{DIRECTORY}/{date}/{race}/{revision:04d}.json")
    if source_ref is not None:
        check_path(source_ref["artifact_path"])


def assert_pre_race(root, row, race, date, *, at, persisted_at=None, now=None):
    """当時認識していた時刻と、後日判明した前倒し境界を別々に照合する。"""
    instant = iso(at, "evidence readback")
    stored = iso(persisted_at, "evidence persistence") if persisted_at else instant
    known = iso(row.get("scheduled_post_time_jst"), "initial official post")
    changes = history(root, row, race, date, now=now)
    previous = known
    for new_post, readback, _ in changes:
        if readback <= instant:
            # 証跡の読戻しまでに確認した改訂は最新値で置き換える。
            # 延長途中の時刻を、後から独立した期限として再検査しない。
            known = new_post
        elif new_post < previous:
            # 読戻し後に初めて判明した前倒しだけを遡及検査する。
            # 後日確認の単なる延長でLATEを復活させることはない。
            require(stored < new_post and instant < new_post,
                    "later official advance invalidates pre-race eligibility")
        previous = new_post
    require(stored < known and instant < known,
            "schedule change cannot rehabilitate late/replay evidence")
    return known


def assert_post(root, row, race, date, post, *, at, forward=True, now=None):
    """当時予定を照合し、前向き適格の場合は後判明前倒しも審査する。"""
    actual = effective_post(root, row, race, date, at=at, now=now)
    provided = iso(post, "evidence scheduled post")
    require(actual == provided,
            "schedule mismatch: evidence post is not official post known at readback")
    if forward:
        assert_pre_race(root, row, race, date, at=at, now=now)
        applied = [change for changed, readback, change in
                   history(root, row, race, date, now=now)
                   if readback <= iso(at, "evidence readback")]
        if applied:
            _git_recorded_before(root, race, date, applied[-1]["revision"], at,
                                 source_ref=applied[-1]["official_text_ref"])
    return actual


def result_post(root, row, race, date, *, captured_at, result_post_time):
    """結果の公式予定と初回予定の差は同一race/dateのchange-chainでだけ認める。"""
    current = effective_post(root, row, race, date, at=captured_at)
    require(current == iso(result_post_time, "official result post"),
            "official result scheduled post lacks verified schedule history")
    applied = [change for new_post, readback, change in history(root, row, race, date)
               if readback <= iso(captured_at, "result capture")]
    if applied:
        _git_recorded_before(root, race, date, applied[-1]["revision"], captured_at,
                             source_ref=applied[-1]["official_text_ref"])
    return current


def registered_row(root, race, date):
    """既存の第4台帳だけを見る。未登録の日別台帳を暗黙作成しない。"""
    path = Path(root) / "docs/validation/records/cycle_04" / (date + ".json")
    if not path.is_file():
        return None
    ledger = json.loads(path.read_text(encoding="utf-8"))
    if ledger.get("cycle_id") != "cycle_04" or ledger.get("race_date_jst") != date:
        return None  # 合成検査の旧/部分台帳を正式登録済みとは見なさない
    if race not in ledger.get("initial_scope", []):
        return None  # 未登録レースを発走履歴の存在として誤認しない
    return ledger["races"][race]
