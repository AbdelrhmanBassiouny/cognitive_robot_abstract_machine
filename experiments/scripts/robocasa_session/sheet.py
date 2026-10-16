import sys
import imageio.v3 as iio, numpy as np
for path in sys.argv[1:]:
    frames = iio.imread(path)
    n = len(frames)
    idx = np.linspace(0, n - 1, 16).astype(int)
    rows = [np.concatenate([frames[i][::2, ::2] for i in idx[r * 4:(r + 1) * 4]], axis=1) for r in range(4)]
    iio.imwrite(path.replace(".mp4", "_sheet.png"), np.concatenate(rows, axis=0))
    print(path, n, idx.tolist())
