"""Generate reviewable JSON Schemas for parsed TOML and JSON reports, not an assembler."""
import json
from pathlib import Path


def obj(fields, **extra):
    return dict(type='object', properties=fields, required=list(fields), additionalProperties=False, **extra)


def array(item, minimum=0, unique=False):
    return dict(type='array', items=item, minItems=minimum, uniqueItems=unique)


def ref(name):
    return {'$ref': '#/$defs/' + name}


def make_schema():
    text = {'type': 'string', 'minLength': 1}
    nullable = {'type': ['string', 'null']}
    boolean = {'type': 'boolean'}
    integer = {'type': 'integer', 'minimum': 0}
    identifier = {'type': 'string', 'pattern': '^[a-z][a-z0-9-]*$'}
    version = {'type': 'string', 'pattern': '^[0-9]+\\.[0-9]+\\.[0-9]+$'}
    sha = {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}
    path = {'type': 'string', 'minLength': 1, 'pattern': r'^(?![A-Za-z]:)(?!/)(?!.*\\)(?!.*:)(?!.*(?:^|/)\.{1,2}(?:/|$))[^\x00]+$'}
    timestamp = {'type': 'string', 'format': 'date-time', 'pattern': r'(Z|\+00:00)$'}
    states = {'enum': ['not_run', 'running', 'passed', 'failed', 'cancelled', 'timed_out', 'skipped']}
    terminal = {'enum': ['passed', 'failed', 'cancelled', 'timed_out']}
    d = {}
    d['diagnostic'] = obj({'code': text, 'severity': {'enum': ['error', 'warning', 'info']}, 'stage': text, 'message': text, 'input': nullable, 'field': nullable, 'dependency_chain': array(identifier)})
    diagnostics = array(ref('diagnostic'))
    d['config'] = obj({'schema_version': {'const': 1, 'type': 'integer'}, 'target': identifier, 'features': array(identifier, 1, True), 'output_dir': path})
    d['profile'] = obj({'schema_version': {'const': 1, 'type': 'integer'}, 'id': identifier, 'version': version, 'architecture': {'const': 'aarch64'}, 'rust_target': {'const': 'aarch64-unknown-none-softfloat'}, 'base_modules': array(identifier, 1, True), 'supported_features': array(identifier, 1, True), 'artifact_format': {'const': 'elf'}, 'emulator': obj({'qemu_version': {'const': '11.1.0'}, 'machine': {'const': 'virt-11.1'}, 'cpu': {'const': 'cortex-a53'}, 'memory_mib': {'const': 128, 'type': 'integer'}, 'cores': {'const': 1, 'type': 'integer'}, 'accelerator': {'const': 'tcg'}, 'instruction_counting': {'const': 'auto'}, 'secure': {'const': False, 'type': 'boolean'}, 'virtualization': {'const': False, 'type': 'boolean'}, 'gic_version': {'const': 2, 'type': 'integer'}}), 'verification': obj({'scope': {'const': 'emulator'}, 'recipe': {'const': 'startup-and-panic-v1'}})})
    d['module'] = obj({'id': identifier, 'version': version, 'kind': {'enum': ['kernel', 'hal', 'bsp', 'driver']}, 'source_dir': path, 'architectures': array(text, 1, True), 'targets': array(identifier, 1, True), 'requires': array(identifier, unique=True), 'conflicts': array(identifier, unique=True)})
    d['catalog'] = obj({'schema_version': {'const': 1, 'type': 'integer'}, 'modules': array(ref('module'), 1), 'features': array(obj({'id': identifier, 'requires': array(identifier, 1, True)}), 1)})
    d['resolved_module'] = obj({'id': identifier, 'version': version, 'reasons': array(obj({'kind': {'enum': ['base', 'feature', 'dependency']}, 'from': identifier}), 1, True)})
    d['input'] = obj({'path': text, 'sha256': sha})
    d['recipe'] = obj({'id': identifier, 'version': version, 'sha256': sha})
    d['plan'] = obj({'requested_features': array(identifier, 1, True), 'resolved_modules': array(ref('resolved_module'), 1), 'build_order': array(identifier, 1, True), 'inputs': array(ref('input'), 1), 'artifact_format': {'const': 'elf'}, 'verification_recipe': ref('recipe'), 'missing_prerequisites': diagnostics})
    d['artifact'] = obj({'id': identifier, 'variant': {'enum': ['normal', 'panic-test']}, 'path': path, 'sha256': sha, 'size_bytes': integer})
    d['manifest'] = obj({'schema_version': {'const': 1, 'type': 'integer'}, 'bundle_id': text, 'created_at': timestamp, 'complete': {'const': True, 'type': 'boolean'}, 'target': obj({'id': identifier, 'version': version, 'architecture': {'const': 'aarch64'}, 'rust_target': {'const': 'aarch64-unknown-none-softfloat'}}), 'requested_features': array(identifier, 1, True), 'resolved_modules': array(ref('resolved_module'), 1), 'inputs': array(ref('input'), 1), 'tools': array(obj({'name': text, 'version': text}), 1), 'artifacts': {**array(ref('artifact'), 2), 'maxItems': 2}, 'verification_recipe': ref('recipe')})
    d['log'] = obj({'stream': {'enum': ['stdout', 'stderr']}, 'path': path, 'sha256': sha})
    d['step'] = obj({'id': {'enum': ['startup', 'panic']}, 'artifact_id': identifier, 'artifact_sha256': sha, 'status': states, 'deadline_ms': {'const': 10000, 'type': 'integer'}, 'observed_marker': nullable, 'stop_requested': boolean, 'logs': array(ref('log')), 'diagnostics': diagnostics})
    d['cleanup'] = obj({'status': {'enum': ['not_run', 'running', 'passed', 'failed']}, 'stop_budget_ms': {'const': 5000, 'type': 'integer'}, 'kill_budget_ms': {'const': 5000, 'type': 'integer'}, 'processes_settled': boolean, 'diagnostics': diagnostics})
    d['verification'] = obj({'schema_version': {'const': 1, 'type': 'integer'}, 'run_id': text, 'complete': boolean, 'operation': {'const': 'verify'}, 'target': identifier, 'manifest_sha256': sha, 'verification_scope': {'const': 'emulator'}, 'started_at': timestamp, 'finished_at': {'anyOf': [timestamp, {'type': 'null'}]}, 'status': states, 'steps': {**array(ref('step')), 'maxItems': 2}, 'cleanup': ref('cleanup'), 'diagnostics': diagnostics, 'evidence': array(path)})
    d['verification']['allOf'] = [{'if': {'properties': {'complete': {'const': True}}}, 'then': {'properties': {'finished_at': timestamp, 'status': terminal}}, 'else': {'properties': {'finished_at': {'type': 'null'}, 'status': {'const': 'running'}}}}]
    d['cli'] = obj({'schema_version': {'const': 1, 'type': 'integer'}, 'operation': {'enum': ['validate', 'plan', 'build', 'verify']}, 'status': terminal, 'target': {'anyOf': [identifier, {'type': 'null'}]}, 'build_ready': {'type': ['boolean', 'null']}, 'diagnostics': diagnostics, 'result': {}, 'evidence': array(path)})
    result_types = {'validate': obj({'missing_prerequisites': diagnostics}), 'plan': ref('plan'), 'build': obj({'manifest_path': text, 'manifest_sha256': sha}), 'verify': ref('verification')}
    d['cli']['allOf'] = [{'if': {'properties': {'operation': {'const': op}}}, 'then': {'properties': {'result': {'anyOf': [schema, {'type': 'null'}]}}}} for op, schema in result_types.items()]
    d['cli']['allOf'] += [{'if': {'properties': {'status': {'const': 'passed'}}}, 'then': {'properties': {'result': {'not': {'type': 'null'}}}}}, {'if': {'properties': {'operation': {'const': 'verify'}}}, 'then': {'properties': {'build_ready': {'type': 'null'}}}}]
    return {'$schema': 'https://json-schema.org/draft/2020-12/schema', 'title': 'RustOS schema 1 design contracts', '$comment': 'Validate a specific $defs entry; cross-record invariants require semantic checks. This is not an assembler.', '$defs': d}


if __name__ == '__main__':
    destination = Path(__file__).resolve().parents[1] / 'docs/schemas/contracts.schema.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(make_schema(), indent=2) + '\n', encoding='utf-8')
    print('Generated', destination)
