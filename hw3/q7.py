import numpy as np

X_messages = np.array([
    [12, 0, 1],
    [45, 5, 8],
    [8, 0, 0],
    [30, 3, 4]
])

w = np.array([0.1, 0.8, 0.5])
b = -2.0

preds = X_messages @ w + b
preds = np.where(preds < 0, 0, preds)

threshold = 5

for i, pred in enumerate(preds):
    if pred < threshold:
        print(f"message_{i}: is calm.")
    else:
        print(f"message_{i}: is energetic.")