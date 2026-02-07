"""Quick data verification script"""
import pandas as pd

# Load data
df = pd.read_csv(r'c:\Users\ryans\source\repos\moltbook\analysis_v2\comments_raw_v2.csv')

print(f"Total rows: {len(df):,}")
print(f"\nColumns: {list(df.columns)}")

print(f"\n{'='*60}")
print("DATA SAMPLE (first 3 rows)")
print('='*60)
print(df[['author', 'content', 'karma', 'is_reply', 'depth']].head(3).to_string())

print(f"\n{'='*60}")
print('YOUR BOT (Darkmatter2222)')
print('='*60)
our_bot = df[df['is_our_bot']==1]
print(f"Total comments: {len(our_bot)}")
print(f"Total karma: {our_bot['karma'].sum()}")
print(f"Avg karma: {our_bot['karma'].mean():.2f}")
print(f"Replies made: {our_bot['is_reply'].sum()}")

print(f"\nTop 5 comments by karma:")
top5 = our_bot.nlargest(5, 'karma')[['content', 'karma', 'post_title']]
for i, row in top5.iterrows():
    content = row['content'][:80].replace('\n', ' ')
    print(f"  [{row['karma']} karma] {content}...")

print(f"\n{'='*60}")
print('HIGH KARMA AUTHORS (TOP 10)')
print('='*60)
author_stats = df.groupby('author').agg({
    'karma': ['sum', 'mean', 'count']
}).round(2)
author_stats.columns = ['total_karma', 'avg_karma', 'comment_count']
author_stats = author_stats.sort_values('total_karma', ascending=False).head(10)
print(author_stats.to_string())

print(f"\n{'='*60}")
print('KARMA STATISTICS')
print('='*60)
print(f"Min: {df['karma'].min()}")
print(f"Max: {df['karma'].max()}")
print(f"Mean: {df['karma'].mean():.2f}")
print(f"Median: {df['karma'].median()}")
print(f"Std: {df['karma'].std():.2f}")

print(f"\n{'='*60}")
print('REPLY STATISTICS')
print('='*60)
print(f"Top-level comments: {len(df[df['is_reply']==0]):,}")
print(f"Replies: {len(df[df['is_reply']==1]):,}")
print(f"Avg depth: {df['depth'].mean():.2f}")
print(f"Max depth: {df['depth'].max()}")
