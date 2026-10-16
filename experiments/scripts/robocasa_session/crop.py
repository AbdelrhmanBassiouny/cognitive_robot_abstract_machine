import sys
import imageio.v3 as iio, numpy as np
path, start, stop = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
frames = iio.imread(path)
idx = np.linspace(start, stop, 8).astype(int)
rows = [np.concatenate([frames[i] for i in idx[r * 4:(r + 1) * 4]], axis=1) for r in range(2)]
iio.imwrite(path.replace(".mp4", f"_{start}_{stop}.png"), np.concatenate(rows, axis=0)[::2, ::2])
print(idx.tolist())
