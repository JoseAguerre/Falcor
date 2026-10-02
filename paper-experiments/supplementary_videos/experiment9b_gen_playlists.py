import os

QUADROOT = r"C:\Users\Jose\Desktop\Falcor\quadlight"
OUTDIR = r"C:\Users\Jose\Desktop\Falcor\results\experiment9b\playlists"
os.makedirs(OUTDIR, exist_ok=True)

# (scene, family-relative-dir, frame count) - matches each scene's OFFICIAL promoted
# quadlight family (the one its .pyscene actually points a single frame into).
FAMILIES = {
    'phonehand': ('colors', 1199),
    'cinema': ('hdr', 251),
    'fireplace_room': (os.path.join('fireplace', '4k'), 300),
    'rover': ('road', 300),
    'convergence': ('cave', 637),
}

for scene, (family, count) in FAMILIES.items():
    lines = ['#prefetch 12']
    for i in range(1, count + 1):
        path = os.path.join(QUADROOT, family, f'frame_{i:05d}.hdr')
        lines.append(f'{path} 1')
    outpath = os.path.join(OUTDIR, f'{scene}_full.hdrplaylist')
    with open(outpath, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'{scene}: {count} frames -> {outpath}')
