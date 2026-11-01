"""Read-only local review of lock/cache bytes. Not the runtime stable-input loader."""
import hashlib
import json
from pathlib import Path

from m2_input_contracts import validate, _path

ROOT = Path(__file__).resolve().parents[1]


def local_path(root, relative):
    _path(relative)
    path = root
    for part in relative.split('/'):
        path = path / part
        if path.is_symlink() or getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
            raise ValueError('Reparse/symlink cache input')
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Cache input escaped repository')
    return path


def check_file(root, record):
    path = local_path(root, record['path'])
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        before = path.stat()
        while True:
            chunk = stream.read(1024*1024)
            if not chunk:
                break
            sha.update(chunk)
        after = path.stat()
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        raise ValueError('Cache input changed while checking')
    if after.st_size != record['size_bytes'] or sha.hexdigest() != record['sha256']:
        raise ValueError('Locked bytes differ: ' + record['path'])
    return path


def check_lock(lock, root=ROOT):
    validate('firmware_lock', lock)
    for asset in lock['assets']:
        check_file(root, {**asset, 'path': lock['cache_root'] + '/boot-assets/' + asset['path']})
    dtbs = [a for a in lock['assets'] if a['role'] == 'device-tree']
    for package in lock['source_packages']:
        for record in [package['archive'], package['reproduction_evidence']] + package['build_materials']:
            check_file(root, record)
        evidence = json.loads(local_path(root, package['reproduction_evidence']['path']).read_text())
        related = [a for a in dtbs if a['source_package_id'] == package['id']]
        if len(related) != 1 or evidence['dtb_sha256'] != related[0]['sha256']:
            raise ValueError('Reproduction/DTB binding mismatch')
        runs = evidence['runs']
        if len(runs) != 2 or len({r['result_path'] for r in runs}) != 2:
            raise ValueError('Two distinct reproduction runs required')
        for run in runs:
            folder = local_path(root, run['result_path']).parent
            if not run['binary_match'] or run['exit_code'] != 0 or run['actual_dtb_sha256'] != related[0]['sha256']:
                raise ValueError('Unsuccessful DTB reproduction')
            result = json.loads((folder / 'result.json').read_text())
            if any(result[key] != run[key] for key in result):
                raise ValueError('Reproduction result differs from bound evidence')
            for artifact in run['artifacts']:
                relative = folder.relative_to(root).as_posix() + '/' + artifact['path']
                check_file(root, {**artifact, 'path': relative})
            rebuilt = [a for a in run['artifacts'] if a['path'] == 'rebuilt.dtb']
            if len(rebuilt) != 1 or rebuilt[0]['sha256'] != related[0]['sha256'] or rebuilt[0]['size_bytes'] != related[0]['size_bytes']:
                raise ValueError('Rebuilt artifact differs from locked DTB')
    return {'status': 'passed', 'boot_assets': len(lock['assets']), 'source_packages': len(lock['source_packages'])}


if __name__ == '__main__':
    path = ROOT / 'assets/locks/rpi-zero2w-boot-assets.lock.json'
    print(json.dumps(check_lock(json.loads(path.read_text(encoding='utf-8'))), indent=2))
