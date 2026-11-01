"""Run a source-only DTB reproduction in a bounded, network-disabled container."""
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'out/research/m2-source-9b488bc7a1e9'
ARCHIVE = SOURCE / 'linux-9b488bc7a1e9b61713082f3e6c4361988d62f77b.tar.gz'
EXPECTED = '5b31bc70011e454f482ba323b1eca22bf54fa2fa4682576ee73816a2eccfa277'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    image = subprocess.check_output(['docker', 'image', 'inspect', 'rustos-dtb-repro:p6', '--format', '{{.Id}}'], text=True).strip()
    folder = SOURCE / ('repro-' + str(time.time_ns()))
    folder.mkdir()
    name = 'rustos-dtb-' + folder.name
    command = ['docker', 'run', '--rm', '--name', name, '--network', 'none', '--cap-drop', 'ALL',
               '--security-opt', 'no-new-privileges', '--cpus', '2', '--memory', '2g', '--pids-limit', '256',
               '--mount', f'type=bind,source={ARCHIVE},target=/input/source.tar.gz,readonly',
               '--mount', f'type=bind,source={folder},target=/output', image]
    start = time.time()
    timed_out = False
    with (folder / 'build.log').open('wb') as log:
        try:
            code = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=300).returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            code = 124
            subprocess.run(['docker', 'rm', '-f', name], stdout=log, stderr=subprocess.STDOUT, timeout=30)
    artifacts = [{ 'path': p.name, 'size_bytes': p.stat().st_size, 'sha256': digest(p)}
                 for p in folder.iterdir() if p.is_file()]
    rebuilt = folder / 'rebuilt.dtb'
    result = dict(kind='dtb-source-reproduction-not-rustos-boot', image_id=image, command=command,
                  exit_code=code, timed_out=timed_out, elapsed_seconds=round(time.time()-start, 3),
                  expected_dtb_sha256=EXPECTED, actual_dtb_sha256=digest(rebuilt) if rebuilt.exists() else None,
                  binary_match=code == 0 and rebuilt.exists() and digest(rebuilt) == EXPECTED,
                  artifacts=artifacts, network='none', source_mount='read-only')
    (folder / 'result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'result': str(folder / 'result.json'), 'exit_code': code, 'binary_match': result['binary_match']}, indent=2))
    return code if code else (0 if result['binary_match'] else 5)


if __name__ == '__main__':
    raise SystemExit(main())
