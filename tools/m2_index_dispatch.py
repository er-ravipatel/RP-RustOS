"""Design-only strict M2 index dispatch; deliberately separate from live importer."""
from m2_output_contracts import require
from m2_session_contracts import validate_build_index, validate_index
from m2_failure_contracts import validate_failed_index


def validate_index_record(index, *, manifest_bytes=None, record_bytes=None):
    require(type(index.get('schema_version')) is int and index['schema_version'] == 2, 'Not an M2 index')
    kind = index.get('record_kind')
    if kind == 'completed-build':
        require(manifest_bytes is not None, 'Build index needs manifest bytes')
        return validate_build_index(index, manifest_bytes)
    if kind == 'failed-operation':
        require(record_bytes is not None, 'Failed index needs retained failure bytes')
        return validate_failed_index(index, record_bytes, manifest_bytes)
    if kind is None and 'report_path' in index:
        require(manifest_bytes is not None and record_bytes is not None, 'Verification index needs both inputs')
        return validate_index(index, record_bytes, manifest_bytes)
    raise ValueError('Unknown M2 index kind')
