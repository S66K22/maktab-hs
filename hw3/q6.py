import numpy as np

bib_numbers = np.array([101, 102, 103, 104, 105, 106])
times_5k = np.array([22.3, 25.1, 21.8, 26.4, 23.0, 24.7])

bib_numbers_2 = np.array([107, 108])
times_5k_2 = np.array([20.5, 27.9])

bib_numbers = np.hstack([bib_numbers, bib_numbers_2])
times_5k = np.hstack([times_5k, times_5k_2])

shuffled_idx = list(np.arange(len(bib_numbers)))
np.random.shuffle(shuffled_idx)
shuffled_bib_numbers = bib_numbers[shuffled_idx]
shuffled_times_5k = times_5k[shuffled_idx]

shuffled_pairs = list(zip(shuffled_bib_numbers, shuffled_times_5k))
normal_pairs = list(zip(bib_numbers, times_5k))

is_shuffle_valid = all(item in normal_pairs for item in shuffled_pairs)
assert is_shuffle_valid

sorted_idx = np.argsort(times_5k)
for i, idx in enumerate(sorted_idx):
    print(f"{bib_numbers[idx]}: {times_5k[idx]}: rank: {i + 1}")

bib_number = 104
idx = np.where(bib_numbers == bib_number)
rank = np.where(sorted_idx == idx[0])
print(f"{bib_number} rank is: {rank[0].item() + 1}")
