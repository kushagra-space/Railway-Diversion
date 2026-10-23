import csv

with open("data/trains.csv", "r") as file:
    reader = csv.DictReader(file)

    for train in reader:
        print(train["train_number"])
        print(train["train_name"])
        print()