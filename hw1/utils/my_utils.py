from typing import Callable
import csv
import os

def add_to_dictionary(dictionary: dict, key: str, value:str, force: bool) -> None:
    if (key in dictionary) and (force == False):
        raise KeyError("Key Exists.")
    dictionary[key] = value

def search_dictionary(dictionary: dict, key: str):
    return dictionary.get(key)

def show_dict(dictionary:dict, print_obj: Callable) -> None:
    print_obj(dictionary)

def write_to_csv(dictionary: dict, path: str, header: list, mode:  str, delimiter: str) -> None:
    with open(path, mode, newline="") as f:
        writer = csv.writer(f, delimiter=delimiter)
        writer.writerow(header)
        writer.writerow(dictionary.items())

def read_csv(path: str, mode: str, header: list, delimiter: str):
    data = {}
    try:
        with open(path, mode, newline="") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            for row in reader:
                data[row[header[0]]] = row[header[1]]
    except FileNotFoundError:
        print("FileNotFound")
    return data

def stringiy_dictionary(dictionary: dict, delimiter: str) -> str:
    result = ""
    for key, value in dictionary.items():
        result += f"{key}{delimiter}{value}\n"
    return result

def write_to_text_file(dictionary: dict, path: str, header: list[str], mode:str, delimiter: str) -> None:
    text_to_write = stringiy_dictionary(dictionary, delimiter)
    with open(path, mode) as f:
        f.write(text_to_write)

def read_from_text_file(path: str, mode: str, delimiter: str) -> dict:
    repo = dict()
    try:
        with open(path, mode) as f:
            for line in f.readlines():
                key_value = line.strip().split(delimiter)
                repo[key_value[0]] = int(key_value[1])
    except FileNotFoundError:
        pass
    return repo

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')