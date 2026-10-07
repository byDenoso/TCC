"""New code fingerprints use a separate, idempotently selected cache namespace."""
import pytest
from runtime.nexo_agent_api.retrieval_cli import MEMORY_CACHE_SUFFIX, memory_cache_path


@pytest.mark.parametrize('previous', [
    '', '.retrieval-1.1', '.retrieval-1.1-security-20261006',
    '.retrieval-1.1-continuity-20261007',
    '.retrieval-1.1-continuity-validated-20261007', MEMORY_CACHE_SUFFIX,
])
def test_audit_namespace_preserves_previous_cache(tmp_path, previous):
    cache = tmp_path / ('memory' + previous)
    cache.write_bytes(b'old index must remain intact')
    selected = memory_cache_path(str(cache))
    assert MEMORY_CACHE_SUFFIX == '.retrieval-1.1-continuity-audit-20261007'
    assert selected == str(tmp_path / 'memory') + MEMORY_CACHE_SUFFIX
    assert memory_cache_path(selected) == selected
    assert cache.read_bytes() == b'old index must remain intact'
