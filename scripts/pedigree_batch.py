"""全原票の登録に使う単一writer。正本の検証/CAS/書込みはRegistry.saveを通す。"""
from contextlib import contextmanager
from threading import get_ident
from pedigree_registry import Registry, read


class BatchRegistry(Registry):
    """同じwriter lockの内側でだけ個体一覧を保持し、索引を最後に再構築する。

    save毎に正本JSONの読戻しを行う。途中例外でも保存済みの事実は残るため、
    一括トランザクションではない。索引は例外時にも正本から再構築する。
    """
    def __init__(self, root):
        super().__init__(root)
        self._batch_records = None
        self._saving_key = None
        self._batch_owner = None

    @contextmanager
    def batch(self):
        if self._batch_records is not None:
            raise ValueError('nested batch forbidden')
        with super().writer():
            self._batch_records = {r['horse_key']: r for r in super().records()}
            self._batch_owner = get_ident()
            try:
                yield self
            finally:
                try:
                    Registry.reindex(self)
                finally:
                    self._batch_records = None
                    self._saving_key = None
                    self._batch_owner = None

    @contextmanager
    def writer(self):
        if self._batch_records is None:
            with super().writer():
                yield
        else:
            self._check_owner()
            yield

    def _check_owner(self):
        if self._batch_records is not None and self._batch_owner != get_ident():
            raise ValueError('batch belongs to another thread')

    def records(self):
        self._check_owner()
        if self._batch_records is None:
            return super().records()
        return self._batch_records.values()

    def save(self, candidate, expected_hash=None):
        self._check_owner()
        self._saving_key = candidate['horse_key']
        return super().save(candidate, expected_hash)

    def update_identity(self, candidate, expected_hash, reason, reviewed_by):
        self._check_owner()
        self._saving_key = candidate['horse_key']
        return super().update_identity(candidate, expected_hash, reason, reviewed_by)

    def reindex(self):
        if self._batch_records is None:
            return super().reindex()
        record = read(self.path(self._saving_key))
        if record:
            self._batch_records[record['horse_key']] = record

