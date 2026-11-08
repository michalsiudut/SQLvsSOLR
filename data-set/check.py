
import pandas as pd

df = pd.read_csv("wikipedia.csv")

print("Liczba rekordów:", len(df))
print("Unikalne ID:", df["id"].nunique())

print("\nPuste wartości:")
print(df.isna().sum())

print("\nKategorie topic:")
print(df["topic"].value_counts())

print("\nKategorie article_type:")
print(df["article_type"].value_counts())

dates = pd.to_datetime(df["date_modified"], errors="coerce")
print("\nPoprawne daty:", dates.notna().sum())
print("Niepoprawne daty:", dates.isna().sum())

print("\nŚrednia długość tekstu:", df["text"].str.len().mean())
print("Minimalna długość tekstu:", df["text"].str.len().min())
