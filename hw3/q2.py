import numpy as np

recipes = np.array([
    # Cooking Time (min) Calories Spiciness
    [15,                 350, 2,  5],  # "Salad"
    [45,                 600, 7,  10], # "Curry"
    [10,                 200, 0,  3],  # "Toast"
    [30,                 450, 5,  7],  # "Pasta"
    [60,                 800, 8,  12]  # "Stew"
])

users = np.array([
    [10, 250, 1, 4],
    [50, 700, 8, 11],
    [25, 400, 4, 6]
])

recipe_names = np.array(["Salad", "Curry", "Toast", "Pasta", "Stew"])

recipes_min = recipes.min(axis=0)
recipes_max = recipes.max(axis=0)
normalized_recipes = (recipes - recipes_min) / (recipes_max - recipes_min)

normalized_users = (users - recipes_min) / (recipes_max - recipes_min)

def euclidean_distance_calculator(array1: np.ndarray, array2: np.ndarray) -> np.ndarray:
    return ((array1 - array2) ** 2).sum()

def find_distance_between_users_and_recipies(users: np.ndarray, recipies: np.ndarray):
    distances = np.zeros((users.shape[0], recipies.shape[0]))
    for row in np.arange(users.shape[0]):
        for col in np.arange(recipies.shape[0]):
            distances[row, col] = euclidean_distance_calculator(users[row, :], recipes[col, :])
    
    return distances

distances = find_distance_between_users_and_recipies(normalized_users, normalized_recipes)
vectorized_distances = ((normalized_users[:, np.newaxis, :] - normalized_recipes[np.newaxis, :, :]) ** 2).sum(axis=2)
nearest_food_taste = np.argmin(vectorized_distances, axis=1)

for user_idx in np.arange(len(users)):
    print(f"user_{user_idx} favorite food: {recipe_names[nearest_food_taste[user_idx]]}")


sorted_vectorized_distances = np.argsort(vectorized_distances, axis=1)
sorted_recipie_names = list()

for row_idx in np.arange(len(sorted_vectorized_distances)):
    sorted_recipie_names.append(recipe_names[sorted_vectorized_distances[row_idx]])

print(np.array(sorted_recipie_names))