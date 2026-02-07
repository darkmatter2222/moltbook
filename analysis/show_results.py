import pandas as pd

# Load analyzed data
df = pd.read_csv('comments_analyzed.csv')

print('='*80)
print('MOLTBOOK COMMENT STUDY - ATTRIBUTE-KARMA CORRELATION')
print('='*80)

# Our agent's comments
our_comments = df[df['author'] == 'Darkmatter2222']
print(f'\nOur Agent (Darkmatter2222) Comments: {len(our_comments)}')

# Show sample of high karma comments
print('\n' + '='*80)
print('TOP 10 HIGHEST KARMA COMMENTS')
print('='*80)
top = df.nlargest(10, 'karma')[['author', 'karma', 'content', 'clarity', 'humor', 'intelligence']]
for i, row in top.iterrows():
    karma = row['karma']
    author = row['author']
    content = row['content'][:100]
    clarity = row['clarity']
    humor = row['humor']
    intel = row['intelligence']
    print(f'\n[{karma} karma] @{author}')
    print(f'  Content: {content}...')
    print(f'  Clarity: {clarity}  Humor: {humor}  Intelligence: {intel}')

# Correlation insights
print('\n' + '='*80)
print('KEY INSIGHTS: What Drives Karma?')
print('='*80)

attrs = ['politeness', 'intelligence', 'thoughtfulness', 'humor', 'relevance', 
         'originality', 'engagement_potential', 'emotional_depth', 'clarity', 'helpfulness']

correlations = []
for attr in attrs:
    if attr in df.columns:
        corr = df[attr].corr(df['karma'])
        correlations.append((attr, corr))

correlations.sort(key=lambda x: x[1], reverse=True)

print('\nRanked by Correlation to Karma:')
print('-'*50)
for attr, corr in correlations:
    bar_len = int(abs(corr) * 50)
    bar = '#' * bar_len
    sign = '+' if corr > 0 else '-'
    print(f'{attr:25} {sign}{abs(corr):.3f} {bar}')

# High vs Low karma comparison
print('\n' + '='*80)
print('HIGH KARMA vs LOW KARMA - ATTRIBUTE COMPARISON')
print('='*80)

high_karma = df[df['karma'] >= 5]
low_karma = df[df['karma'] == 0]

print(f'\nHigh Karma (>=5): {len(high_karma)} comments')
print(f'Low Karma (=0):   {len(low_karma)} comments')
print()
print(f'{"Attribute":25} {"High Karma":>12} {"Low Karma":>12} {"Diff":>10}')
print('-'*60)

for attr in attrs:
    if attr in df.columns:
        high_mean = high_karma[attr].mean()
        low_mean = low_karma[attr].mean()
        diff = high_mean - low_mean
        marker = ' UP' if diff > 0.5 else (' DN' if diff < -0.5 else '')
        print(f'{attr:25} {high_mean:12.2f} {low_mean:12.2f} {diff:+10.2f}{marker}')

# Show the full comment table
print('\n' + '='*80)
print('COMMENT ATTRIBUTES TABLE (Sample)')
print('='*80)
cols = ['author', 'karma', 'clarity', 'humor', 'intelligence', 'thoughtfulness', 'engagement_potential']
print(df[cols].head(20).to_string())
