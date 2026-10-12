"""保存工程の証跡を日本語へ変換する。確認の実行や証跡の生成は行わない。"""

import argparse
import json
import sys
from pathlib import Path


def describe_persistence(target, *, write_attempted=False, write_succeeded=None,
                         readback_matches=None, verification_succeeded=None):
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
        next_check = '書込の失敗記録を確認し、原因を解消して再試行してください。'
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

    return {'status_code': code, 'complete': code == 'COMPLETE', 'target': target,
            'message': message, 'cause': cause, 'impact': impact, 'next_check': next_check,
            'checks': {'書込': label(write_succeeded), '読戻し一致': label(readback_matches),
                       '個別完了確認': label(verification_succeeded)}}


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
