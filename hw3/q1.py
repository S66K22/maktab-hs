import numpy as np

def find_lost_value_idx(array: np.ndarray) -> np.ndarray:
    rows, cols = array.shape
    lost_cols = []
    for col in np.arange(cols):
        lost_col = [(row, col) for row in np.arange(rows) if array[row, col] == 0]
        lost_cols.extend(lost_col)
    return np.array(lost_cols)

def find_valid_rows_for_given_col(data: np.ndarray, col: int, genders: np.ndarray, desired_gender: str) -> tuple[list[int], list[int]]:
    rows, cols = data.shape
    valid_rows, invalid_rows = [], []
    for row in range(rows):
        if genders[row] != desired_gender:
            continue
        if data[row, col] != 0:
            valid_rows.append(row)
        else:
            invalid_rows.append(row)
    return valid_rows, invalid_rows

def imputer(data: np.ndarray, member_genders, impute_func):
    _, cols = data.shape
    new_data = data.copy()
    for col in range(cols):
        valid_males, invalid_males = find_valid_rows_for_given_col(data=new_data, col=col, 
                                                                   genders=member_genders, desired_gender="m")
        valid_females, invalid_females = find_valid_rows_for_given_col(data=new_data, col=col, 
                                                                       genders=member_genders, desired_gender="f")
        if valid_males and invalid_males:
            new_data[invalid_males, col] = impute_func(new_data[valid_males, col])
        if valid_females and invalid_females != 0:
            new_data[invalid_females, col] = impute_func(new_data[valid_females, col])
    
    return new_data

def calculate_bmi(weight: np.ndarray, height: np.ndarray) -> np.ndarray: 
    height = height.astype(np.float32) / 100
    weight = weight.astype(np.float32)
    return weight / (height ** 2)

def calculate_criteria(data: np.ndarray, mu1: float, mu2: float):
    return calculate_bmi(data[:, 0], data[:, 1]) * mu1 + data[:, -1] * mu2

gym_data = np.array([
    # Age, Weight, Height, #Sessions
    [28,   75,     175,    4], # Ali
    [34,   68,     168,    3], # Sara
    [45,   82,     180,    2], # Reza
    [22,   58,     162,    5], # Neda 
    [38,   90,     0,      1], # Hassan
    [29,   65,     170,    0]  # Maryam
])

member_names = np.array(["Ali", "Sara", "Reza", "Neda", "Hassan", "Maryam"])
member_genders = np.array(["m", "f", "m", "f", "m", "f"])
imputed_data = imputer(gym_data, member_genders, np.mean)

new_gym_data = imputed_data[:, [1, 2, 3]]

criteria = calculate_criteria(new_gym_data, 0.5, 5)

active_member = np.argmax(criteria)
print(criteria)
print(f"{member_names[active_member]} is the most active member with criteria: {criteria[active_member]:.2f}")

std = np.std(new_gym_data[:, -1])
session_diff_with_std = [abs(session - std) for session in new_gym_data[:, -1]]
most_session_diff_with_std = np.argmax(session_diff_with_std)
print(f"{member_names[most_session_diff_with_std]} has most different session value than others with value: {session_diff_with_std[most_session_diff_with_std]:.2f}")