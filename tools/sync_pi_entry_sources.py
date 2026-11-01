"""Promote the reviewed, fully enabled preflight without test injection paths."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def expand(text, enabled):
    active, stack, output = True, [], []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('.ifdef '):
            name = stripped.split()[1]
            if not name.startswith('TEST_'):
                raise ValueError('Unreviewed conditional')
            stack.append((active, name in enabled))
            active = active and name in enabled
        elif stripped == '.else':
            parent, condition = stack[-1]
            active = parent and not condition
        elif stripped == '.endif':
            active, _ = stack.pop()
        elif active:
            output.append(line)
    if stack:
        raise ValueError('Unbalanced promotion conditions')
    return '\n'.join(output)+'\n'


def promoted():
    source = (ROOT/'tools/entry-harness/handoff.S').read_text()
    begin, end = source.index('.ifdef TEST_HEADER\n'), source.index('.ifdef TEST_WRITE\n')
    result = {'preflight.S': expand(source[begin:end],
              {'TEST_HEADER','TEST_TREE','TEST_ROOT','TEST_RAM','TEST_STATIC','TEST_CMA'})}
    for name in ['cpu-guards.S','el1-transition.S']:
        result[name] = expand((ROOT/'tools/entry-harness'/name).read_text(), set())
    for name, content in result.items():
        # Replace only development stack symbol spelling; semantics unchanged.
        content = content.replace('__test_stack_top','__stack_top')
        while content.startswith('//'):
            content = content.partition('\n')[2]
        if 'TEST_' in content:
            raise ValueError('Test configuration leaked into Pi entry')
        result[name] = '// Generated from reviewed harness sources; run tools/sync_pi_entry_sources.py --check.\n'+content
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    folder = ROOT/'bsp/rpi-zero2w/kernel/src/entry'
    for name, content in promoted().items():
        path = folder/name
        if args.check:
            if path.read_text() != content:
                raise SystemExit(f'Pi entry promotion differs: {path}')
        else:
            folder.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    print('Pi entry source promotion matches reviewed preflight/control paths.')


if __name__ == '__main__':
    main()
