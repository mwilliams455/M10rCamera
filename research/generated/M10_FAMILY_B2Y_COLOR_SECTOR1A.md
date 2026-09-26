# M10 FAMILY B2Y COLOR SECTOR1A

Cross-model audit of record 0x18 STILL saturation structure in M10-R, M10 and M10-P.

## M10R-30.22.23.34

All four saturation modes found: **True**.
- MEDIUM six gain words: [8192, 8192, 8192, 8192, 8192, 8192]
- LOW six gain words: [6964, 6964, 6964, 6964, 6964, 6964]
- HIGH six gain words: [9830, 9830, 9830, 9830, 9830, 9830]
- MEDIUM words +0x40..+0x50: [0, 20000, 30000, 40000, 50000]
- LOW-vs-MEDIUM diffs: ['0x10', '0x14', '0x18', '0x1c', '0x20', '0x24']
- HIGH-vs-MEDIUM diffs: ['0x10', '0x14', '0x18', '0x1c', '0x20', '0x24']

## M10-3.22.23.38

All four saturation modes found: **True**.
- MEDIUM six gain words: [8192, 8192, 8192, 8192, 8192, 8192]
- LOW six gain words: [6964, 6964, 6964, 6964, 6964, 6964]
- HIGH six gain words: [9830, 9830, 9830, 9830, 9830, 9830]
- MEDIUM words +0x40..+0x50: [0, 20000, 30000, 40000, 50000]
- LOW-vs-MEDIUM diffs: ['0x10', '0x14', '0x18', '0x1c', '0x20', '0x24']
- HIGH-vs-MEDIUM diffs: ['0x10', '0x14', '0x18', '0x1c', '0x20', '0x24']

## M10P-4.22.23.34

All four saturation modes found: **True**.
- MEDIUM six gain words: [8192, 8192, 8192, 8192, 8192, 8192]
- LOW six gain words: [6964, 6964, 6964, 6964, 6964, 6964]
- HIGH six gain words: [9830, 9830, 9830, 9830, 9830, 9830]
- MEDIUM words +0x40..+0x50: [0, 20000, 30000, 40000, 50000]
- LOW-vs-MEDIUM diffs: ['0x10', '0x14', '0x18', '0x1c', '0x20', '0x24']
- HIGH-vs-MEDIUM diffs: ['0x10', '0x14', '0x18', '0x1c', '0x20', '0x24']

Exact medium geometry across color models with full saturation modes: **True**.

Interpretation boundary: recurrence supports a generic M10-family color-control geometry, but does not by itself label the six lanes or five coordinates.
