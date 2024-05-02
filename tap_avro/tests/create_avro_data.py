import polars as pl

# Load the CSV file
df = pl.read_csv('data/alphabet.csv')

print(df)

path = "data/alphabet.avro"

df.write_avro(path)

dfa = pl.read_avro(path)


print(dfa)