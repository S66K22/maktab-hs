import numpy as np

scores = np.array([
    # Quiz Midterm Final
    [18,   15,     20], # Student A
    [12,   14,     16], # Student B
    [20,   19,     18], # Student C
    [10,    8,     15]  # Student D
])

scheme_A = np.array([0.5, 0.3, 0.2])
scheme_B = np.array([0.2, 0.3, 0.5])
scheme_C = np.array([0.1, 0.2, 0.7])

weight_matrix = np.vstack([scheme_A, scheme_B, scheme_C])

final_scores = scores @ weight_matrix.T

assert(final_scores.shape == (4, 3))

best_scheme_per_student = np.argmax(final_scores, axis=1)

class_mean_per_exam = final_scores.mean(axis=0)

best_global_scheme = np.argmax(class_mean_per_exam)

rng = np.random.default_rng()

w0 = rng.uniform(0, 1/3)
w2 = 2 * w0
w1 = 1 - 3 * w0

scheme_D = np.array([w0, w1, w2])

weight_matrix = np.vstack([weight_matrix, scheme_D])
