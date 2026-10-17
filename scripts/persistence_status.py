"""保存工程の証跡を日本語へ変換する。確認の実行や証跡の生成は行わない。"""

import argparse
import json
import sys
from pathlib import Path


def describe_persistence(target, *, write_attempted=False, write_succeeded=None,
                         readback_matches=None, verification_succeeded=None,
                         failure_category=None, timing_status=None):
    """未確認はNone、実際の成功/失敗はbool。監査成功は入力にしない。"""
    if not isinstance(target, str) or not target.strip() or any(c in target for c in '\r\n'):
        raise ValueError('対象を空でない1行の日本語名称で指定してください')
    if type(write_attempted) is not bool:
        raise ValueError('書込試行の有無は真偽値で指定してください')
    for value in (write_succeeded, readback_matches, verification_succeeded):
        if value is not None and type(value) is not bool:
            raise ValueError('確認結果は真偽値、未実施はnullで指定してください')
    if not write_attempted and any(v is not None for v in
                                   (write_succeeded, readback_matches, verification_succeeded)):
        raise ValueError('未試行の書込に確認結果を設定できません')
    if write_attempted and write_succeeded is None:
        raise ValueError('書込結果が未確認です。結果を確認してから状態を判定してください')
    if write_succeeded is not True and readback_matches is not None:
        raise ValueError('書込成功前に読戻し結果を設定できません')
    if readback_matches is not True and verification_succeeded is not None:
        raise ValueError('読戻し一致の確認前に個別完了確認の結果を設定できません')

    if failure_category is not None and failure_category not in {
            'safety_refusal', 'authorization', 'branch_policy', 'conflict',
            'timeout', 'transport', 'rate_limit', 'server_unavailable',
            'ci_or_checker', 'unknown'}:
        raise ValueError('未知の拒否分類です')
    if timing_status is not None and timing_status not in {
            'PRE_SCHEDULED', 'SCHEDULE_REACHED', 'UNDETERMINED'}:
        raise ValueError('未知の時刻判定です')
    if failure_category and write_succeeded is True:
        raise ValueError('書込成功と書込拒否を同時指定できません')
    target = target.strip()
    if not write_attempted:
        code, message = 'NOT_ATTEMPTED', '保存は未試行です。'
        cause = '書込をまだ試していません。'
        impact = '今回の内容は保存未確認です。'
        next_check = '対象の内容を書き込み、書込結果を確認してください。'
    elif not write_succeeded:
        code, message = 'WRITE_FAILED', '保存の書込に失敗しました。'
        cause = '今回の書込が失敗しています。'
        impact = '今回の内容が保存されたことを確認できません。'
        next_check = '拒否主体と再試行可否を確認してください。安全性拒否・不明理由を別経路で迂回しないでください。'
        if failure_category == 'safety_refusal':
            cause = '実行環境・ツールの安全性拒否として記録されました。GitHub権限失敗とは断定しません。'
        elif failure_category == 'authorization':
            cause = 'GitHub応答で認証・権限不足が確認されました。'
        elif failure_category == 'conflict':
            cause = '既存の内容またはSHAと競合しています。原本を変更せず読取り確認してください。'
        elif failure_category == 'unknown':
            cause = '失敗の発生層は未特定です。許可確認前の再試行は行いません。'
    elif readback_matches is False:
        code, message = 'READBACK_MISMATCH', '保存先から読戻した内容が一致しません。'
        cause = '指定した内容と読戻した内容が不一致です。'
        impact = '今回の内容を保存完了と扱えません。'
        next_check = '内容・対象ファイル・参照先を照合し、再保存して読戻してください。'
    elif readback_matches is None:
        code, message = 'BODY_SAVED_UNVERIFIED', '本体は書込済み。読戻しと個別完了確認は未実施です。'
        cause = '書込成功後の読戻し確認が未実施です。'
        impact = '保存先との一致と個別完了は未確認です。'
        next_check = '保存先を読戻し、一致を確認してから個別完了確認を実行してください。'
    elif verification_succeeded is not True:
        code = 'BODY_SAVED_UNVERIFIED'
        if verification_succeeded is None:
            message = '本体は保存済み。個別完了確認は未実施です。'
            cause = '本体の読戻しは一致していますが、個別完了確認は未実施です。'
            next_check = '保存対象に対応する個別完了確認を実行してください。'
        else:
            message = '本体は保存済み。個別完了確認で不足が見つかりました。'
            cause = '個別完了確認が失敗しています。'
            next_check = '個別完了確認の失敗記録を確認し、不足を解消して再検証してください。'
        impact = '本体を保全したまま、個別完了は未確認として扱います。'
    else:
        code, message = 'COMPLETE', '対象の保存工程はすべて完了しました。'
        cause = '書込・読戻し一致・個別完了確認がすべて成功しています。'
        impact = '指定した対象の保存工程を完了として扱えます。'
        next_check = '今回の確認結果と参照した証跡を記録してください。'

    def label(value):
        return '未実施' if value is None else '成功' if value else '失敗'

    if timing_status is not None and timing_status != 'PRE_SCHEDULED' and code == 'COMPLETE':
        code, message = 'TIMING_UNVERIFIED', '保存の読戻しは一致しましたが発走前適格は未認証です。'
        impact = '保存済み原本を保全し、発走前の個別完了とは扱いません。'
        next_check = '独立した当時の読戻し時刻と公式発走予定を検査してください。'
    return {'status_code': code, 'complete': code == 'COMPLETE', 'target': target,
            'message': message, 'cause': cause, 'impact': impact, 'next_check': next_check,
            'failure_category': failure_category, 'timing_status': timing_status,
            'checks': {'書込': label(write_succeeded), '読戻し一致': label(readback_matches),
                       '個別完了確認': label(verification_succeeded)}}


def describe_operation(target, operation, *, individual_verified=None):
    """prediction_persistence_io の実測結果を表示。保存I/O単独で完了昇格しない。"""
    data = operation.as_dict() if hasattr(operation, 'as_dict') else operation
    write_state = data['write_state']
    readback = data['readback_state']
    failure = data.get('failure_category')
    # 既存bytesを読んだだけでは今回の発走前保存証明とはならない。
    confirmed = write_state == 'WRITTEN' and readback == 'MATCH'
    attempted = write_state != 'NOT_ATTEMPTED' or failure is not None
    return describe_persistence(
        target, write_attempted=attempted,
        write_succeeded=confirmed if attempted else None,
        readback_matches=readback == 'MATCH' if confirmed else None,
        verification_succeeded=individual_verified if confirmed and readback == 'MATCH' else None,
        failure_category=failure if not confirmed else None,
        timing_status=data.get('timing_state'))


def render_persistence(report):
    """利用者向け出力には内部状態コードを含めない。"""
    return '\n'.join((f"対象：{report['target']}", report['message'],
                      f"原因：{report['cause']}", f"影響：{report['impact']}",
                      f"次の確認：{report['next_check']}"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True,
                        help='実際の保存確認結果を記載したJSONファイル')
    parser.add_argument('--json', action='store_true', help='監査用の内部コードを含むJSONを出力')
    args = parser.parse_args(argv)
    try:
        evidence = json.loads(args.evidence.read_text(encoding='utf-8'))
        if not isinstance(evidence, dict):
            raise ValueError('確認結果はJSONオブジェクトで指定してください')
        report = describe_persistence(**evidence)
    except OSError:
        print('保存状態を判定できません：確認結果ファイルを読み取れません。対象ファイルを確認してください。',
              file=sys.stderr)
        return 1
    except json.JSONDecodeError:
        print('保存状態を判定できません：確認結果のJSON形式が不正です。内容を確認してください。',
              file=sys.stderr)
        return 1
    except TypeError:
        print('保存状態を判定できません：入力項目が保存工程の形式と一致しません。項目を確認してください。',
              file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f'保存状態を判定できません：{exc}', file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json
          else render_persistence(report))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
