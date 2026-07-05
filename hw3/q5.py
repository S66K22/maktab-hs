import numpy as np

importance = np.array([3, 8, 1, 9, 4, 7])

importance_2d_1 = importance.reshape(-1, 1)
importance_2d_2 = importance[:, np.newaxis]

assert importance_2d_1.shape == (6, 1)
assert importance_2d_2.shape == (6, 1)

print(f"importance_2d_1: {importance_2d_1}")
print(f"importance_2d_2: {importance_2d_2}")

model_out = np.array([[[0.9]]])
print(f"model_out: {model_out.squeeze()}")
print(f"model_out: {model_out[0, 0, 0]}")
print(f"model_out: {model_out.item()}")

notes = np.array([5, 10, 15, 20, 25])
pinned = notes[1:3]
pinned[0] = 999
print(f"notes: {notes}\n\n") # element at index 1 will be changed to 999

notes = np.array([5, 10, 15, 20, 25])
pinned = notes[1:3].copy()
pinned[0] = 999
print(f"notes: {notes}\n\n")

last_elemetns = notes[-3:]
last_elemetns[:] = last_elemetns.cumsum()
print(f"notes: {notes}\n\n")

