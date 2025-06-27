import pandas as pd

df = pd.read_csv('bill.csv')
df_copy = df[['cluster', 'cluster_keyword']]

df_copy.to_csv('cluster_keywords.csv', index=False)