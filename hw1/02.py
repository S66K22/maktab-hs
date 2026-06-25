from utils import add_to_dictionary, search_dictionary, show_dict
from pprint import pprint

def main():
    print("Welcome to the library")
    library = {}

    while True:
        command = input("enter [a] to add new book,\n"
                        "enter [s] to search a book\n"
                        "enter [sh] to show all book\n"
                        "enter any other key to exit\n"
                        "## ").strip()
        if command == "a":
            book_name = input("Enter book name: ").strip()
            author_name = input("Enter author name: ").strip()
            try:
                add_to_dictionary(library, book_name, author_name, False)
            except KeyError:
                force = input("Book name exists.\n"
                              "Enter [y] to update the author\n"
                              "Enter any other key to not alter the value\n"
                              "## ")
                if force == "y":
                    add_to_dictionary(library, book_name, author_name, True)
                    continue

        elif command == "s":
            book_name = input("Enter book name: ").strip()
            author_name = search_dictionary(library, book_name)
            if author_name is None:
                print("Book is not found")
            else:
                print(f"Book name: {book_name}, Author name: {author_name}")
        elif command == "sh":
            show_dict(library, pprint)
        else:
            break

if __name__ == "__main__":
    main()