"""Session search.

Re-exports :class:`Searcher` so that ``asl.searcher`` is importable, which is
what ``asl/cli.py`` and ``tests/test_asl.py`` already import. The
implementation lives in :mod:`asl.indexer` next to :class:`Indexer`.
"""

from .indexer import Searcher

__all__ = ["Searcher"]
