"""Negative layout checks against an explicitly supplied compiler artifact."""
import argparse
import json
import struct
from pathlib import Path
from check_pi_artifacts import layout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-report', type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.compiler_report.read_text())
    results = []
    for variant in report['variants']:
        original = Path(variant['elf']).read_bytes()
        layout(original)
        h = struct.unpack_from('<16sHHIQQQIHHHHHH', original)
        load = next(h[5]+i*56 for i in range(h[10]) if struct.unpack_from('<I', original, h[5]+i*56)[0] == 1)
        cases = [('wrong-machine',18,'H',62), ('wrong-entry',24,'Q',0x100000),
                 ('program-table-overflow',32,'Q',len(original)),
                 ('section-table-overflow',40,'Q',len(original)),
                 ('writable-executable',load+4,'I',7),
                 ('physical-address-mismatch',load+24,'Q',0x100000),
                 ('load-outside-budget',load+40,'Q',0x400000)]
        for name, offset, fmt, value in cases:
            changed = bytearray(original)
            struct.pack_into('<'+fmt, changed, offset, value)
            try:
                layout(changed)
            except ValueError:
                results.append({'variant':variant['variant'],'case':name,'rejected':True})
            else:
                raise AssertionError(f'Accepted altered artifact: {name}')
        for size in [0, 7, 63]:
            try:
                layout(original[:size])
            except ValueError:
                results.append({'variant':variant['variant'],'case':f'truncated-{size}','rejected':True})
            else:
                raise AssertionError('Accepted truncated ELF')
    print(json.dumps({'passed':True,'negative_cases':results}))


if __name__ == '__main__':
    main()
