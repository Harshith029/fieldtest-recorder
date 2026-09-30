import sys, time
sys.argv = ['x', '0', 'c10']
src = open('e4_pipeline.py', encoding='utf-8').read().split('stats = defaultdict')[0]
exec(compile(src, 'e4_pipeline.py', 'exec'))
imgs = []
for n in range(10):
    wells = np.vstack([jitter(REFLS['violet'])] * 2)
    img, _ = render(sim.ILL['Daylight (D65)'], wells, sim.random_conditions(), False, 0.01)
    imgs.append(img)
t = time.perf_counter()
for im in imgs:
    ce.read_capture(im, PROFILE)
print(f"engine only: {1000 * (time.perf_counter() - t) / len(imgs):.0f} ms per {imgs[0].shape[1]}x{imgs[0].shape[0]} photo (Python/NumPy, laptop)")
