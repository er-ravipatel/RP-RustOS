"""Independent, strict reader for the D17 root-only engineering FAT32 layout."""
import argparse
import hashlib
import json
import struct
from pathlib import Path


def inspect(data, expected):
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    def word(offset):
        return struct.unpack_from('<I', data, offset)[0]
    require(len(data) == 67108864 and data[510:512] == b'\x55\xaa', 'Image size or MBR signature')
    require(data[450] == 12 and word(454) == 2048 and word(458) == 129024 and data[462:510] == bytes(48), 'Partition geometry')
    base = 1048576
    boot = data[base:base+512]
    require(boot == data[base+3072:base+3584] and boot[510:] == b'\x55\xaa', 'Boot backup/signature')
    require(struct.unpack_from('<H',boot,11)[0] == 512 and boot[13] == 1 and struct.unpack_from('<H',boot,14)[0] == 32 and boot[16] == 2, 'BPB geometry')
    require(struct.unpack_from('<H',boot,17)[0] == 0 and struct.unpack_from('<H',boot,19)[0] == 0 and struct.unpack_from('<H',boot,22)[0] == 0, 'FAT32 fields')
    require(struct.unpack_from('<IIII',boot,28) == (2048,129024,1024,0), 'BPB extent/flags')
    require(struct.unpack_from('<IHH',boot,44) == (2,1,6), 'Root/FSInfo/backup locations')
    info = data[base+512:base+1024]
    require(info == data[base+3584:base+4096], 'FSInfo backup')
    require(struct.unpack_from('<I',info,0)[0] == 0x41615252 and struct.unpack_from('<I',info,484)[0] == 0x61417272 and struct.unpack_from('<I',info,508)[0] == 0xaa550000, 'FSInfo signatures')
    fat = data[base+16384:base+16384+524288]
    require(fat == data[base+16384+524288:base+16384+1048576], 'FAT mirrors')
    table = struct.unpack('<131072I',fat)
    require(table[:2] == (0x0ffffff8,0xffffffff), 'Reserved FAT entries')
    claimed = set()
    def chain(first):
        result = bytearray()
        while first < 0x0ffffff8:
            require(2 <= first <= 126945 and first not in claimed, 'Cycle/crosslink/range')
            claimed.add(first)
            offset = base+1064960+(first-2)*512
            result.extend(data[offset:offset+512])
            first = table[first]
        require(first <= 0x0fffffff, 'Invalid FAT terminator')
        return bytes(result)
    directory = chain(2)
    found, aliases, pending = {}, set(), []
    ended = False
    for pos in range(0,len(directory),32):
        entry = directory[pos:pos+32]
        if entry[0] == 0:
            require(not pending and directory[pos:] == bytes(len(directory)-pos), 'Directory tail')
            ended = True
            break
        require(entry[0] != 0xe5, 'Deleted directory entry')
        if entry[11] == 15:
            require(entry[12] == 0 and entry[26:28] == bytes(2), 'LFN metadata')
            pending.append(entry)
            continue
        require(entry[11] == 32 and entry[:11] not in aliases and pending, 'File attribute/alias/LFN')
        aliases.add(entry[:11])
        checksum = 0
        for byte in entry[:11]:
            checksum = (((checksum & 1)<<7) + (checksum>>1) + byte) & 255
        units = []
        for index, long in enumerate(pending):
            require(long[0] == (len(pending)-index | (64 if index == 0 else 0)) and long[13] == checksum, 'LFN sequence/checksum')
        for long in reversed(pending):
            units.extend(struct.unpack_from('<H',long,o)[0] for o in [1,3,5,7,9,14,16,18,20,22,24,28,30])
        if 0 in units:
            stop = units.index(0)
            require(all(u == 65535 for u in units[stop+1:]), 'LFN padding')
            units = units[:stop]
        require(all(0 < u < 128 for u in units), 'Unsupported filename')
        name = ''.join(map(chr,units))
        require(name not in found, 'Duplicate file')
        size = struct.unpack_from('<I',entry,28)[0]
        first = struct.unpack_from('<H',entry,26)[0] | struct.unpack_from('<H',entry,20)[0]<<16
        content = chain(first) if size else b''
        require((size > 0 or first == 0) and len(content) == (size+511)//512*512 and content[size:] == bytes(len(content)-size), 'File allocation/padding')
        found[name] = hashlib.sha256(content[:size]).hexdigest()
        pending = []
    require(ended and found == expected, 'File inventory or digest')
    require(all(table[c] == 0 for c in range(2,126946) if c not in claimed), 'Orphan allocated cluster')
    require(struct.unpack_from('<I',info,488)[0] == 126944-len(claimed), 'FSInfo free count')
    return {'passed':True,'files':found,'allocated_clusters':len(claimed),'image_sha256':hashlib.sha256(data).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',type=Path,required=True)
    parser.add_argument('--expected',type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.image.read_bytes(),json.loads(args.expected.read_text())),indent=2))
