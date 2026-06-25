from utils import (add_to_dictionary, search_dictionary, show_dict,
                   write_to_text_file, read_from_text_file, clear_screen)

FILE_PATH = "repo.csv"
HEADER = ["product", "count"]

def report(dictionary: dict) -> str:
    report_string = f"There are {len(dictionary)} distinct products in repository.\n"
    total_products = 0
    min_product_key = ""
    min_product_value = float('inf')
    max_product_key = ""
    max_product_value = 0

    for key, value in dictionary.items():
        report_string += f"{key}: {value}\n"
        total_products += value
        if value < min_product_value:
            min_product_key = key
            min_product_value = value
        if value > max_product_value:
            max_product_key = key
            max_product_value = value
    report_string += f"Min Product: {min_product_key}: {min_product_value}\n"
    report_string += f"Max Product: {max_product_key}: {max_product_value}\n"
    report_string += f"total number of products: {total_products}\n"
    return report_string
    


def main():
    clear_screen()
    repo = read_from_text_file(FILE_PATH, "r")
    while True:
        command = input("enter [a] to add new product,\n"
                        "enter [s] to search a product\n"
                        "enter [se] to sell a product\n"
                        "enter [sh] to show all products\n"
                        "enter [sa] to save all data to a file.\n"
                        "enter [re] to show report\n"
                        "enter any other key to exit\n"
                        "## ").strip()
        
        if command == 'a':
            try:
                key = input("Enter product name:\n# ").strip()
                value = int(input("Enter number of products:\n# ").strip())
                add_to_dictionary(repo, key, value, False)
            except KeyError:
                value += search_dictionary(repo, key)
                add_to_dictionary(repo, key, value, True)
        elif command == "s":
            key = input("Enter product name:\n# ").strip()
            value = search_dictionary(repo, key)
            if value is None:
                print(f"{key} does not exists.\n")
            else:
                print(f"{key}: {value}")
        elif command == 'se':
            key = input("Enter product name:\n# ").strip()
            value = int(input("Enter number of products you want to se:\n# ").strip()) * (-1)
            temp_value = search_dictionary(repo, key)
            if temp_value is None:
                print(f"{key} is not a valid product name")
                continue
            value += temp_value
            if value < 0:
                print(f"Max number of products you can sell is: {temp_value}")
            elif value == 0:
                del repo[key]
            else:
                add_to_dictionary(repo, key, value, True)
        elif command == "sh":
            show_dict(repo, print)
        elif command == "sa":
            write_to_text_file(repo, FILE_PATH, HEADER, "w", " - ")
        elif command == "re":
            if len(repo) == 0:
                print("There is no item in repo\n")
            else:
                print(report(repo))
        else:
            write_to_text_file(repo, FILE_PATH, HEADER, "w", " - ")
            break
        input("# Press Enter to continue...")
        clear_screen()
        
            


if __name__ == "__main__":
    main()