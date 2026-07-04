import numpy as np
from typing import Callable

def find_valid_and_invalid_rows_for_given_col(data: np.ndarray, col: int, genders: np.ndarray, desired_gender: str) -> tuple[list[int], list[int]]:
    """
    Find valid and invalid row indices for a given column and gender.

    A row is considered valid if its gender matches ``desired_gender`` and the
    value in the specified column is non-zero. A row is considered invalid if
    its gender matches ``desired_gender`` and the value in the specified column
    is zero.

    Parameters
    ----------
    data : np.ndarray
        A 2D array containing the dataset.
    col : int
        The index of the column to inspect.
    genders : np.ndarray
        A 1D array containing the gender corresponding to each row in
        ``data``.
    desired_gender : str
        The gender used to filter the rows.

    Returns
    -------
    tuple[list[int], list[int]]
        A tuple containing:
        - A list of valid row indices.
        - A list of invalid row indices.
    """
    rows, _ = data.shape
    valid_rows, invalid_rows = [], []
    for row in range(rows):
        if genders[row] != desired_gender:
            continue
        if data[row, col] != 0:
            valid_rows.append(row)
        else:
            invalid_rows.append(row)
    
    # ChatGPT generated code
    # gender_mask = genders == desired_gender
    # valid_rows = np.where(gender_mask & (data[:, col] != 0))[0]
    # invalid_rows = np.where(gender_mask & (data[:, col] == 0))[0]
    return valid_rows, invalid_rows

def imputer(data: np.ndarray, member_genders: np.ndarray, impute_func: Callable):
    """
    Impute missing values in a dataset based on gender.

    Missing values (represented by 0) are imputed independently for each
    column and each gender. For every column, the function computes a
    replacement value by applying ``impute_func`` to the non-missing values
    of members with the same gender, then uses that value to replace the
    missing entries for that gender.

    Parameters
    ----------
    data : np.ndarray
        A 2D array containing the dataset. Missing values must be represented
        by 0.
    member_genders : np.ndarray
        A 1D array containing the gender corresponding to each row in
        ``data``.
    impute_func : Callable
        A function that takes a 1D NumPy array of valid values and returns a
        single value to use for imputation (e.g., ``np.mean``, ``np.median``,
        ``np.max``).

    Returns
    -------
    np.ndarray
        A copy of ``data`` with missing values imputed. The original input
        array is not modified.
    """
    _, cols = data.shape
    new_data = data.copy()
    for col in range(cols):
        valid_males, invalid_males = find_valid_and_invalid_rows_for_given_col(data=new_data, col=col, 
                                                                   genders=member_genders, desired_gender="m")
        valid_females, invalid_females = find_valid_and_invalid_rows_for_given_col(data=new_data, col=col, 
                                                                       genders=member_genders, desired_gender="f")
        if valid_males and invalid_males:
            new_data[invalid_males, col] = impute_func(new_data[valid_males, col])
        if valid_females and invalid_females != 0:
            new_data[invalid_females, col] = impute_func(new_data[valid_females, col])
    
    return new_data

def calculate_bmi(weight: np.ndarray, height: np.ndarray) -> np.ndarray: 
    """
    Calculate the Body Mass Index (BMI) for each individual.

    BMI is computed using the formula:

        BMI = weight / height²

    where weight is measured in kilograms (kg) and height is measured in
    meters (m).

    Parameters
    ----------
    weight : np.ndarray
        A 1D array containing the weights of individuals in kilograms.
    height : np.ndarray
        A 1D array containing the heights of individuals in meters.

    Returns
    -------
    np.ndarray
        A 1D array containing the BMI value for each individual.
    """
    height = height.astype(np.float32) / 100
    weight = weight.astype(np.float32)
    return weight / (height ** 2)

def calculate_criteria(data: np.ndarray, mu1: float, mu2: float):
    """
    Calculate a weighted criterion score for each individual.

    The criterion is computed as a weighted sum of the individual's Body Mass
    Index (BMI) and the value in the last column of ``data``:

        criterion = BMI * mu1 + last_column * mu2

    where BMI is calculated from the first two columns of ``data``.

    Parameters
    ----------
    data : np.ndarray
        A 2D array where:
        - the first column contains weights (kg),
        - the second column contains heights (m),
        - the last column contains the number of sessions.
    mu1 : float
        The weight assigned to the BMI component.
    mu2 : float
        The weight assigned to the number of sessions.

    Returns
    -------
    np.ndarray
        A 1D array containing the weighted criterion score for each
        individual.
    """
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
