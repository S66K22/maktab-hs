import random

random.seed(42)

NUM_GUESSES = 5
MIN_VALUE = 0
MAX_VALUE = 100

the_number = random.randint(MIN_VALUE, MAX_VALUE)
guess = int(input("Guess the number: "))
won = False
for i in range(NUM_GUESSES):
    if guess == the_number:
        print("WIN!")
        won = True
        break
    if guess < the_number:
        guess = int(input("Guess bigger number: "))
    elif guess > the_number:
        guess = int(input("Guess smaller number: "))

if won == False:
    print("You lost!")
    print(f"The number = {the_number}")