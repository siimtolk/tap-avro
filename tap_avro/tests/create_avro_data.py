import polars as pl

# Load the CSV file
df = pl.read_csv('data/alphabet.csv')

print(df)

path = "data/alphabet.avro"

df.write_avro(path)

dfa = pl.read_avro(path)

import fastavro


headers = []
with open(path, 'rb') as f:
        avro_reader = fastavro.reader(f)
        schema = avro_reader.writer_schema

        headers = []
        for i in schema['fields']:
                headers.append(i['name'])



print(headers)