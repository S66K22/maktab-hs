import numpy as np

weather_data = np.random.randn(2, 8, 4) * 5 + 20

def analyze_day(day_data: np.ndarray):
    day_data = day_data.T
    assert day_data.shape == (4, 8)

analyze_day(weather_data[1])
flatten_weather_data = weather_data.flatten()
assert flatten_weather_data.shape == (64, )


day3 = np.random.randn(8, 4)
day3 = day3[np.newaxis, :, :]
weather_data = np.concat([weather_data, day3])
assert weather_data.shape == (3, 8, 4)