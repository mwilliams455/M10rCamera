#!/usr/bin/env python3
from pathlib import Path
import hashlib, struct, sys

COMP_OFF = 0x38
CODES = {
    '00': 6, '01': 7,
    '100': 1, '101': 5,
    '1100': 0, '1101': 2,
    '1110': 4, '11110': 3, '11111': 8,
}

def u32(b, o):
    return struct.unpack_from('<I', b, o)[0]

def iter_bits(buf):
    for byte in buf:
        for shift in range(7, -1, -1):
            yield (byte >> shift) & 1

def decode_chunk(chunk, out_size, table):
    bits = iter_bits(chunk)
    out = bytearray()
    while len(out) < out_size:
        code = ''
        while code not in CODES:
            code += str(next(bits))
        k = CODES[code]
        if k == 0:
            value = 0
        else:
            x = 0
            for _ in range(k):
                x = (x << 1) | next(bits)
            value = x if x >= (1 << (k - 1)) else x - ((1 << k) - 1)
        out.append(table[value + 128])
    return bytes(out)

def unpack(src: Path, dst: Path):
    fw = src.read_bytes()
    if fw[COMP_OFF:COMP_OFF+4] != b'COMP':
        raise SystemExit('COMP container not found at 0x38')

    header_size = u32(fw, COMP_OFF + 0x08)
    expected_size = u32(fw, COMP_OFF + 0x10)
    table = fw[COMP_OFF + 0x54:COMP_OFF + 0x54 + 256]
    if len(table) != 256 or len(set(table)) != 256 or table[128] != 0:
        raise SystemExit('unexpected M10-R translation table')

    seg_table = COMP_OFF + header_size
    output = bytearray()
    for i in range(8):
        e = seg_table + i * 16
        rel_off = u32(fw, e + 4)
        packed_size = u32(fw, e + 8)
        unpacked_size = u32(fw, e + 12)
        packed = fw[COMP_OFF + rel_off:COMP_OFF + rel_off + packed_size]
        decoded = decode_chunk(packed, unpacked_size, table)
        print(f'chunk {i}: {packed_size} -> {len(decoded)}')
        output.extend(decoded)

    if len(output) != expected_size:
        raise SystemExit(f'size mismatch: {len(output)} != {expected_size}')
    dst.write_bytes(output)
    print(f'wrote {dst} ({len(output)} bytes)')
    print('sha256', hashlib.sha256(output).hexdigest())

if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(f'usage: {sys.argv[0]} M10-R.FW decoded.bin')
    unpack(Path(sys.argv[1]), Path(sys.argv[2]))
