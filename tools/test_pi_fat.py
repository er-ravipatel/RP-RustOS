"""Run independent-reader positive and corruption checks on a synthetic image."""
import argparse
import json
import struct
from pathlib import Path
from check_pi_fat import inspect


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture',type=Path,required=True)
    args=parser.parse_args()
    original=(args.fixture/'fixture.img').read_bytes()
    expected=json.loads((args.fixture/'expected.json').read_text())
    result=inspect(original,expected)
    mutations=[('mbr-signature',510),('partition-type',450),('boot-backup',1048576+3072+3),
               ('fsinfo-backup',1048576+3584),('fat-mirror',1064960+8),
               ('long-name-checksum',2113536+13),('file-content',2113536+512)]
    negatives=[]
    for name,offset in mutations:
        changed=bytearray(original);changed[offset]^=1
        try:inspect(changed,expected)
        except ValueError:negatives.append(name)
        else:raise AssertionError('Accepted corruption: '+name)
    # Corrupt both FAT copies identically so mirror equality cannot hide a cycle.
    changed=bytearray(original)
    for start in [1064960,1589248]:struct.pack_into('<I',changed,start+8,2)
    try:inspect(changed,expected)
    except ValueError:negatives.append('root-chain-cycle')
    else:raise AssertionError('Accepted cyclic root directory')
    print(json.dumps({'positive':result,'rejected_corruptions':negatives},indent=2))


if __name__=='__main__':main()
