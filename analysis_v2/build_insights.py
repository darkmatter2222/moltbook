"""
MOLTBOOK KARMA RECIPE FINDER
=============================
Reads enriched analysis data and builds comprehensive correlation matrices,
visualizations, and insights to find the secret karma recipe.

Works with partial data (traditional features only) or full data (traditional + LLM).

Usage:
    python build_insights.py
"""

import pandas as pd
import numpy as np
import os
import sys
import json

# Try importing viz libraries
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend for saving files
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import seaborn as sns
    HAS_VIZ = True
except ImportError:
    HAS_VIZ = False
    print("⚠️  matplotlib/seaborn not installed - will skip visualizations")
    print("   Install with: pip install matplotlib seaborn")

try:
    from scipy import stats as scipy_stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(BASE_DIR, 'analysis_enriched.csv')

# Feature groups
LLM_DIMENSIONS = [
    "politeness", "humor", "sarcasm", "intelligence", "originality",
    "emotional_intensity", "sentiment", "helpfulness", "controversy",
    "confidence", "empathy", "assertiveness", "storytelling",
    "technical_depth", "persuasiveness", "authenticity", "engagement_bait",
    "warmth", "authority", "specificity", "provocativeness", "agreement",
    "call_to_action", "cultural_reference", "community_insider", "curiosity",
    "wit", "toxicity", "conciseness", "casual_tone",
]

TRADITIONAL_FEATURES = [
    'word_count', 'char_count', 'sentence_count', 'avg_word_length',
    'unique_word_ratio', 'emoji_count', 'has_emoji',
    'lobster_emoji_count', 'has_lobster',
    'question_count', 'has_question',
    'exclamation_count', 'has_exclamation',
    'caps_ratio', 'all_caps_words',
    'punctuation_density', 'has_url',
    'first_person_count', 'second_person_count',
    'newline_count',
]

# Metadata features from original data
META_FEATURES = ['depth', 'is_reply', 'has_replies', 'reply_count', 'content_length']


# ============================================================
# DATA LOADING
# ============================================================

def load_data():
    """Load enriched data and determine available features."""
    print(f"📥 Loading enriched data from {INPUT_FILE}...")
    df = pd.read_csv(INPUT_FILE)
    
    # Determine which feature groups are available
    available_trad = [f for f in TRADITIONAL_FEATURES if f in df.columns]
    available_llm = [f for f in LLM_DIMENSIONS if f in df.columns]
    available_meta = [f for f in META_FEATURES if f in df.columns]
    
    # Count LLM-analyzed rows
    llm_count = 0
    if available_llm:
        llm_count = df[available_llm[0]].notna().sum()
    
    print(f"   Total rows: {len(df):,}")
    print(f"   Traditional features: {len(available_trad)}")
    print(f"   LLM dimensions: {len(available_llm)} ({llm_count:,} rows analyzed)")
    print(f"   Metadata features: {len(available_meta)}")
    
    all_features = available_trad + available_llm + available_meta
    print(f"   Total analysis features: {len(all_features)}")
    
    return df, available_trad, available_llm, available_meta


# ============================================================
# CORRELATION ANALYSIS
# ============================================================

def build_karma_correlations(df, feature_cols, method='spearman'):
    """Build correlation of all features with karma."""
    print(f"\n📊 Building {method.title()} correlations with karma...")
    
    results = []
    
    for col in feature_cols:
        if col not in df.columns:
            continue
        
        series = df[col].dropna()
        karma = df.loc[series.index, 'karma']
        
        if len(series) < 30 or series.nunique() < 2:
            continue
        
        if HAS_SCIPY:
            if method == 'spearman':
                corr, pval = scipy_stats.spearmanr(series, karma)
            else:
                corr, pval = scipy_stats.pearsonr(series, karma)
        else:
            corr = series.corr(karma, method=method)
            pval = 0.0  # Can't compute without scipy
        
        results.append({
            'feature': col,
            'correlation': corr,
            'p_value': pval,
            'n_samples': len(series),
            'significant': pval < 0.05 if pval else True,
        })
    
    corr_df = pd.DataFrame(results).sort_values('correlation', ascending=False)
    return corr_df


def build_full_correlation_matrix(df, feature_cols):
    """Build full feature-to-feature + karma correlation matrix."""
    cols = [c for c in feature_cols + ['karma'] if c in df.columns]
    
    # Use only rows that have LLM features if any LLM cols are present
    subset = df[cols].dropna()
    
    if len(subset) < 30:
        # Fall back to just traditional features
        trad_cols = [c for c in TRADITIONAL_FEATURES + ['karma'] if c in df.columns]
        subset = df[trad_cols].dropna()
        cols = trad_cols
    
    print(f"   Computing {len(cols)}x{len(cols)} correlation matrix on {len(subset):,} rows...")
    corr_matrix = subset.corr(method='spearman')
    
    return corr_matrix


# ============================================================
# VISUALIZATIONS
# ============================================================

def plot_karma_drivers_bar(corr_df, filename='karma_drivers.png'):
    """Horizontal bar chart of top karma drivers."""
    if not HAS_VIZ:
        return
    
    fig, ax = plt.subplots(figsize=(14, 12))
    
    # Sort by absolute correlation
    sorted_df = corr_df.sort_values('correlation', ascending=True)
    
    # Color based on positive/negative
    colors = ['#e74c3c' if c < 0 else '#2ecc71' for c in sorted_df['correlation']]
    
    y_pos = range(len(sorted_df))
    bars = ax.barh(y_pos, sorted_df['correlation'], color=colors, edgecolor='white', linewidth=0.5)
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels(sorted_df['feature'], fontsize=9)
    ax.set_xlabel('Spearman Correlation with Karma', fontsize=12)
    ax.set_title('🔍 What Drives Karma? Feature Correlations\n(Spearman rank correlation)', fontsize=14, fontweight='bold')
    ax.axvline(x=0, color='black', linewidth=0.8)
    ax.grid(axis='x', alpha=0.3)
    
    # Add value labels
    for bar, val in zip(bars, sorted_df['correlation']):
        x = bar.get_width()
        ax.text(x + 0.002 * np.sign(x), bar.get_y() + bar.get_height()/2,
                f'{val:+.3f}', va='center', fontsize=8, fontweight='bold')
    
    # Add significance markers
    for i, (_, row) in enumerate(sorted_df.iterrows()):
        if row.get('significant', True) and abs(row['correlation']) > 0.05:
            ax.text(max(sorted_df['correlation']) + 0.02, i, '★', fontsize=10, va='center', color='gold')
    
    # Legend
    pos_patch = mpatches.Patch(color='#2ecc71', label='Positive (more = more karma)')
    neg_patch = mpatches.Patch(color='#e74c3c', label='Negative (more = less karma)')
    ax.legend(handles=[pos_patch, neg_patch], loc='lower right', fontsize=10)
    
    plt.tight_layout()
    path = os.path.join(BASE_DIR, filename)
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"   📊 Saved: {path}")


def plot_correlation_heatmap(corr_matrix, filename='correlation_heatmap.png'):
    """Full correlation heatmap."""
    if not HAS_VIZ:
        return
    
    n = len(corr_matrix.columns)
    figsize = (max(16, n * 0.5), max(14, n * 0.45))
    fig, ax = plt.subplots(figsize=figsize)
    
    mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
    
    sns.heatmap(
        corr_matrix, mask=mask, annot=True, fmt='.2f',
        cmap='RdBu_r', center=0, vmin=-1, vmax=1,
        square=True, linewidths=0.5,
        annot_kws={'size': 6},
        cbar_kws={'shrink': 0.8, 'label': 'Spearman Correlation'},
        ax=ax
    )
    
    ax.set_title('🔥 Full Feature Correlation Matrix\n(Spearman rank correlations)', 
                 fontsize=14, fontweight='bold')
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right', fontsize=7)
    ax.set_yticklabels(ax.get_yticklabels(), fontsize=7)
    
    plt.tight_layout()
    path = os.path.join(BASE_DIR, filename)
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"   📊 Saved: {path}")


def plot_karma_heatmap_focused(corr_matrix, filename='karma_heatmap_focused.png'):
    """Focused heatmap showing only correlations with karma."""
    if not HAS_VIZ or 'karma' not in corr_matrix.columns:
        return
    
    karma_corr = corr_matrix['karma'].drop('karma').sort_values(ascending=False)
    
    fig, ax = plt.subplots(figsize=(10, max(8, len(karma_corr) * 0.3)))
    
    colors = ['#e74c3c' if v < 0 else '#2ecc71' if v > 0.05 else '#f39c12' for v in karma_corr.values]
    
    bars = ax.barh(range(len(karma_corr)), karma_corr.values, color=colors, edgecolor='white')
    ax.set_yticks(range(len(karma_corr)))
    ax.set_yticklabels(karma_corr.index, fontsize=8)
    ax.set_xlabel('Spearman Correlation with Karma')
    ax.set_title('🎯 All Features vs Karma\n(Sorted by correlation strength)', fontsize=13, fontweight='bold')
    ax.axvline(x=0, color='black', linewidth=0.8)
    ax.grid(axis='x', alpha=0.3)
    
    for bar, val in zip(bars, karma_corr.values):
        x = bar.get_width()
        ax.text(x + 0.003 * np.sign(x), bar.get_y() + bar.get_height()/2,
                f'{val:+.3f}', va='center', fontsize=7, fontweight='bold')
    
    plt.tight_layout()
    path = os.path.join(BASE_DIR, filename)
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"   📊 Saved: {path}")


def plot_high_vs_low_radar(high_profile, low_profile, dims, filename='karma_profile_radar.png'):
    """Radar chart comparing high-karma vs low-karma profiles."""
    if not HAS_VIZ or len(dims) < 3:
        return
    
    # Use top 15 most discriminating dimensions
    diffs = {d: abs(high_profile.get(d, 0) - low_profile.get(d, 0)) for d in dims}
    top_dims = sorted(diffs, key=diffs.get, reverse=True)[:15]
    
    angles = np.linspace(0, 2 * np.pi, len(top_dims), endpoint=False).tolist()
    angles += angles[:1]
    
    high_vals = [high_profile.get(d, 0) for d in top_dims] + [high_profile.get(top_dims[0], 0)]
    low_vals = [low_profile.get(d, 0) for d in top_dims] + [low_profile.get(top_dims[0], 0)]
    
    fig, ax = plt.subplots(figsize=(12, 10), subplot_kw=dict(polar=True))
    
    ax.plot(angles, high_vals, 'o-', linewidth=2, label='High Karma (≥10)', color='#2ecc71')
    ax.fill(angles, high_vals, alpha=0.15, color='#2ecc71')
    ax.plot(angles, low_vals, 'o-', linewidth=2, label='Low Karma (0)', color='#e74c3c')
    ax.fill(angles, low_vals, alpha=0.15, color='#e74c3c')
    
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(top_dims, fontsize=9)
    ax.set_ylim(0, 5)
    ax.set_title('🎯 High-Karma vs Low-Karma Comment Profiles\n(Top 15 most discriminating dimensions)',
                 fontsize=13, fontweight='bold', pad=20)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=11)
    
    plt.tight_layout()
    path = os.path.join(BASE_DIR, filename)
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"   📊 Saved: {path}")


def plot_top_author_comparison(df, llm_dims, filename='author_comparison.png'):
    """Compare LLM dimension profiles of top authors."""
    if not HAS_VIZ or not llm_dims:
        return
    
    # Get top 8 authors by total karma
    author_karma = df.groupby('author')['karma'].agg(['sum', 'count']).reset_index()
    author_karma.columns = ['author', 'total_karma', 'comment_count']
    author_karma = author_karma[author_karma['comment_count'] >= 3]
    top_authors = author_karma.nlargest(8, 'total_karma')['author'].tolist()
    
    # Add our bot if not in top 8
    if 'Darkmatter2222' not in top_authors:
        top_authors = top_authors[:7] + ['Darkmatter2222']
    
    # Get mean LLM scores per author (only for analyzed comments)
    sub = df[df['author'].isin(top_authors)].dropna(subset=llm_dims[:1])
    
    if len(sub) < 5:
        return
    
    # Pick top 10 most variable dimensions
    dim_vars = sub[llm_dims].var().nlargest(10).index.tolist()
    
    author_profiles = sub.groupby('author')[dim_vars].mean()
    
    fig, ax = plt.subplots(figsize=(14, 8))
    author_profiles.T.plot(kind='bar', ax=ax, width=0.8)
    ax.set_ylabel('Average Score (1-5)')
    ax.set_title('🏆 Top Author LLM Dimension Profiles', fontsize=13, fontweight='bold')
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
    ax.set_ylim(1, 5)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    path = os.path.join(BASE_DIR, filename)
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"   📊 Saved: {path}")


# ============================================================
# INSIGHTS & RECIPE FINDING
# ============================================================

def compare_high_vs_low(df, feature_cols, llm_dims):
    """Compare profiles of high-karma vs low-karma comments."""
    print("\n" + "=" * 70)
    print("🔬 HIGH-KARMA vs LOW-KARMA PROFILES")
    print("=" * 70)
    
    high = df[df['karma'] >= 10]
    low = df[df['karma'] == 0]
    
    print(f"\n   High karma (≥10): {len(high):,} comments")
    print(f"   Low karma (=0):   {len(low):,} comments")
    
    high_profile = {}
    low_profile = {}
    
    print(f"\n   {'Feature':<25} {'High Karma':>12} {'Low Karma':>12} {'Δ Diff':>10} {'Direction':>12}")
    print(f"   {'-'*25} {'-'*12} {'-'*12} {'-'*10} {'-'*12}")
    
    comparisons = []
    for col in feature_cols:
        if col not in df.columns:
            continue
        high_mean = high[col].dropna().mean()
        low_mean = low[col].dropna().mean()
        
        if np.isnan(high_mean) or np.isnan(low_mean):
            continue
        
        high_profile[col] = high_mean
        low_profile[col] = low_mean
        
        diff = high_mean - low_mean
        direction = "↑ MORE" if diff > 0.1 else "↓ LESS" if diff < -0.1 else "≈ SAME"
        
        comparisons.append({
            'feature': col,
            'high_mean': high_mean,
            'low_mean': low_mean,
            'diff': diff,
            'abs_diff': abs(diff),
            'direction': direction,
        })
    
    # Sort by absolute difference
    comparisons.sort(key=lambda x: x['abs_diff'], reverse=True)
    
    for c in comparisons[:30]:
        indicator = "🔥" if c['abs_diff'] > 0.5 else "  "
        print(f"   {indicator} {c['feature']:<23} {c['high_mean']:>12.3f} {c['low_mean']:>12.3f} "
              f"{c['diff']:>+10.3f} {c['direction']:>12}")
    
    return high_profile, low_profile


def find_karma_recipe(df, corr_df, llm_dims):
    """Identify the optimal recipe for generating karma."""
    print("\n" + "=" * 70)
    print("🍳 THE KARMA RECIPE")
    print("=" * 70)
    
    # Top positive correlators
    print("\n   🟢 TOP POSITIVE KARMA DRIVERS (do MORE of these):")
    positive = corr_df[corr_df['correlation'] > 0].head(15)
    for _, row in positive.iterrows():
        stars = "⭐" * min(5, int(abs(row['correlation']) * 20))
        print(f"      {stars} {row['feature']:<25} r={row['correlation']:+.4f}  (n={row['n_samples']:,})")
    
    # Top negative correlators
    print("\n   🔴 TOP NEGATIVE KARMA DRIVERS (do LESS of these):")
    negative = corr_df[corr_df['correlation'] < 0].tail(15)
    for _, row in negative.iloc[::-1].iterrows():
        skulls = "💀" * min(5, int(abs(row['correlation']) * 20))
        print(f"      {skulls} {row['feature']:<25} r={row['correlation']:+.4f}  (n={row['n_samples']:,})")
    
    # LLM dimension recipe (optimal values)
    available_llm = [d for d in llm_dims if d in df.columns]
    if available_llm:
        print("\n   🎯 OPTIMAL LLM DIMENSION VALUES (from top karma comments):")
        
        top_karma = df.nlargest(200, 'karma')
        top_sub = top_karma.dropna(subset=available_llm[:1])
        
        if len(top_sub) >= 10:
            print(f"      (Based on top {len(top_sub)} highest-karma comments)")
            print(f"\n      {'Dimension':<25} {'Optimal':>8} {'Distribution':>30}")
            print(f"      {'-'*25} {'-'*8} {'-'*30}")
            
            recipe = {}
            for dim in available_llm:
                vals = top_sub[dim].dropna()
                if len(vals) < 5:
                    continue
                mode = vals.mode().iloc[0] if len(vals.mode()) > 0 else vals.median()
                median = vals.median()
                mean = vals.mean()
                
                recipe[dim] = int(mode)
                
                # Distribution as bar
                dist = vals.value_counts().sort_index()
                bar = ""
                for v in range(1, 6):
                    count = dist.get(v, 0)
                    pct = count / len(vals) * 100
                    bar += f"{v}:{pct:.0f}% "
                
                print(f"      {dim:<25} {int(mode):>8} {bar:>30}")
            
            return recipe
    
    return {}


def analyze_author_strategies(df, llm_dims):
    """Analyze what makes top authors successful."""
    print("\n" + "=" * 70)
    print("🏆 TOP AUTHOR STRATEGY ANALYSIS")
    print("=" * 70)
    
    # Get top authors
    author_stats = df.groupby('author').agg({
        'karma': ['sum', 'mean', 'count', 'max']
    }).round(2)
    author_stats.columns = ['total_karma', 'avg_karma', 'comment_count', 'max_karma']
    author_stats = author_stats[author_stats['comment_count'] >= 3]
    
    # Top by average karma (min 5 comments)
    top_avg = author_stats[author_stats['comment_count'] >= 5].nlargest(10, 'avg_karma')
    
    print(f"\n   Top 10 Authors by Average Karma (min 5 comments):")
    print(f"   {'Rank':<6}{'Author':<25}{'Avg':>8}{'Total':>10}{'Count':>8}{'Max':>8}")
    print(f"   {'-'*6}{'-'*25}{'-'*8}{'-'*10}{'-'*8}{'-'*8}")
    
    for i, (author, row) in enumerate(top_avg.iterrows(), 1):
        marker = " 🤖" if author == 'Darkmatter2222' else ""
        print(f"   {i:<6}{author[:23]:<25}{row['avg_karma']:>8.2f}{row['total_karma']:>10.0f}"
              f"{row['comment_count']:>8.0f}{row['max_karma']:>8.0f}{marker}")
    
    # Our bot's position
    if 'Darkmatter2222' in author_stats.index:
        our_stats = author_stats.loc['Darkmatter2222']
        our_rank = (author_stats['avg_karma'] > our_stats['avg_karma']).sum() + 1
        total_authors = len(author_stats)
        print(f"\n   🤖 Darkmatter2222: Rank #{our_rank}/{total_authors} by avg karma")
    
    # If LLM dimensions available, show what top authors do differently
    available_llm = [d for d in llm_dims if d in df.columns]
    if available_llm:
        top_author_names = top_avg.index[:5].tolist()
        
        print(f"\n   📊 What Top Authors Do Differently (LLM Dimensions):")
        
        top_sub = df[df['author'].isin(top_author_names)].dropna(subset=available_llm[:1])
        rest_sub = df[~df['author'].isin(top_author_names)].dropna(subset=available_llm[:1])
        
        if len(top_sub) >= 5 and len(rest_sub) >= 5:
            diffs = []
            for dim in available_llm:
                top_mean = top_sub[dim].mean()
                rest_mean = rest_sub[dim].mean()
                diff = top_mean - rest_mean
                diffs.append((dim, top_mean, rest_mean, diff))
            
            diffs.sort(key=lambda x: abs(x[3]), reverse=True)
            
            print(f"      {'Dimension':<25} {'Top Authors':>12} {'Everyone Else':>14} {'Δ':>8}")
            print(f"      {'-'*25} {'-'*12} {'-'*14} {'-'*8}")
            
            for dim, top_mean, rest_mean, diff in diffs[:15]:
                marker = "🔥" if abs(diff) > 0.3 else "  "
                print(f"      {marker} {dim:<23} {top_mean:>12.2f} {rest_mean:>14.2f} {diff:>+8.2f}")


def generate_summary_report(corr_df, recipe, high_profile, low_profile, df):
    """Generate the final summary report."""
    print("\n" + "=" * 70)
    print("📋 EXECUTIVE SUMMARY: THE KARMA FORMULA")
    print("=" * 70)
    
    # Top 5 drivers
    top5 = corr_df.head(5)
    bottom5 = corr_df.tail(5)
    
    print("\n   🎯 TOP 5 KARMA BOOSTERS:")
    for i, (_, row) in enumerate(top5.iterrows(), 1):
        print(f"      {i}. {row['feature']:<25} (r={row['correlation']:+.4f})")
    
    print("\n   ⚠️  TOP 5 KARMA KILLERS:")
    for i, (_, row) in enumerate(bottom5.iloc[::-1].iterrows(), 1):
        print(f"      {i}. {row['feature']:<25} (r={row['correlation']:+.4f})")
    
    # Recipe
    if recipe:
        print("\n   🍳 OPTIMAL COMMENT RECIPE (scale 1-5):")
        for dim, val in sorted(recipe.items(), key=lambda x: x[1], reverse=True):
            bar = "█" * val + "░" * (5 - val)
            print(f"      {dim:<25} [{bar}] {val}/5")
    
    # Actionable recommendations
    print("\n   💡 ACTIONABLE RECOMMENDATIONS:")
    recommendations = []
    
    for _, row in corr_df.iterrows():
        feat = row['feature']
        corr = row['correlation']
        
        if corr > 0.1:
            recommendations.append(f"✅ Increase {feat} (r={corr:+.3f})")
        elif corr < -0.1:
            recommendations.append(f"❌ Decrease {feat} (r={corr:+.3f})")
    
    for i, rec in enumerate(recommendations[:12], 1):
        print(f"      {i:>2}. {rec}")
    
    # Save recipe as JSON
    recipe_data = {
        'generated_at': datetime.now().isoformat() if 'datetime' in dir() else 'unknown',
        'top_karma_drivers': [
            {'feature': r['feature'], 'correlation': round(r['correlation'], 4), 'n': r['n_samples']}
            for _, r in top5.iterrows()
        ],
        'karma_killers': [
            {'feature': r['feature'], 'correlation': round(r['correlation'], 4), 'n': r['n_samples']}
            for _, r in bottom5.iloc[::-1].iterrows()
        ],
        'optimal_recipe': recipe,
        'recommendations': recommendations[:12],
    }
    
    recipe_path = os.path.join(BASE_DIR, 'karma_recipe.json')
    with open(recipe_path, 'w') as f:
        json.dump(recipe_data, f, indent=2)
    print(f"\n   💾 Recipe saved to: {recipe_path}")


# ============================================================
# MAIN
# ============================================================

def main():
    from datetime import datetime
    
    print("=" * 70)
    print("🔍 MOLTBOOK KARMA RECIPE FINDER")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Load data
    df, trad_features, llm_dims, meta_features = load_data()
    
    all_features = trad_features + llm_dims + meta_features
    
    # ---- Correlation Analysis ----
    print("\n" + "=" * 70)
    print("📊 CORRELATION ANALYSIS")
    print("=" * 70)
    
    # For LLM features, use only the rows that have them
    if llm_dims:
        llm_df = df.dropna(subset=llm_dims[:1])
        print(f"\n   Using {len(llm_df):,} rows with LLM features for LLM correlations")
        llm_corr = build_karma_correlations(llm_df, llm_dims)
    else:
        llm_corr = pd.DataFrame()
    
    # Traditional features use all rows
    trad_corr = build_karma_correlations(df, trad_features + meta_features)
    
    # Merge all correlations
    all_corr = pd.concat([trad_corr, llm_corr]).sort_values('correlation', ascending=False)
    all_corr = all_corr.drop_duplicates(subset='feature')
    
    # Print all correlations ranked
    print(f"\n   📈 ALL FEATURE CORRELATIONS WITH KARMA (Spearman):")
    print(f"   {'Rank':<6}{'Feature':<28}{'Correlation':>14}{'p-value':>12}{'N':>10}{'Sig?':>6}")
    print(f"   {'-'*6}{'-'*28}{'-'*14}{'-'*12}{'-'*10}{'-'*6}")
    
    for i, (_, row) in enumerate(all_corr.iterrows(), 1):
        sig = "★" if row.get('significant', True) and abs(row['correlation']) > 0.02 else ""
        indicator = "🔥" if abs(row['correlation']) > 0.1 else "  "
        print(f"   {indicator}{i:<4}{row['feature']:<28}{row['correlation']:>+14.4f}"
              f"{row['p_value']:>12.2e}{row['n_samples']:>10,}{sig:>6}")
    
    # ---- Visualizations ----
    print("\n" + "=" * 70)
    print("📊 GENERATING VISUALIZATIONS")
    print("=" * 70)
    
    if HAS_VIZ:
        # 1. Karma drivers bar chart
        plot_karma_drivers_bar(all_corr, 'karma_drivers.png')
        
        # 2. Full correlation heatmap (use LLM subset if available)
        if llm_dims:
            heatmap_cols = llm_dims + ['karma']
            heatmap_df = df.dropna(subset=llm_dims[:1])
            if len(heatmap_df) >= 30:
                corr_matrix = heatmap_df[[c for c in heatmap_cols if c in heatmap_df.columns]].corr(method='spearman')
                plot_correlation_heatmap(corr_matrix, 'correlation_heatmap_llm.png')
        
        # 3. Traditional features heatmap
        trad_heatmap_cols = trad_features + meta_features + ['karma']
        trad_corr_matrix = df[[c for c in trad_heatmap_cols if c in df.columns]].corr(method='spearman')
        plot_correlation_heatmap(trad_corr_matrix, 'correlation_heatmap_traditional.png')
        
        # 4. Focused karma correlation bar
        full_cols = trad_features + llm_dims + meta_features
        if llm_dims:
            focus_df = df.dropna(subset=llm_dims[:1])
        else:
            focus_df = df
        full_matrix = focus_df[[c for c in full_cols + ['karma'] if c in focus_df.columns]].corr(method='spearman')
        plot_karma_heatmap_focused(full_matrix, 'karma_correlations_focused.png')
        
        # 5. Top author comparison
        if llm_dims:
            plot_top_author_comparison(df, llm_dims, 'author_comparison.png')
    
    # ---- High vs Low Karma Comparison ----
    high_profile, low_profile = compare_high_vs_low(df, all_features, llm_dims)
    
    # Radar chart
    if HAS_VIZ and llm_dims:
        # Need LLM features for meaningful radar
        high_karma_df = df[df['karma'] >= 10].dropna(subset=llm_dims[:1])
        low_karma_df = df[df['karma'] == 0].dropna(subset=llm_dims[:1])
        
        if len(high_karma_df) >= 5 and len(low_karma_df) >= 5:
            h_profile = {d: high_karma_df[d].mean() for d in llm_dims}
            l_profile = {d: low_karma_df[d].mean() for d in llm_dims}
            plot_high_vs_low_radar(h_profile, l_profile, llm_dims, 'karma_profile_radar.png')
    
    # ---- Author Strategy Analysis ----
    analyze_author_strategies(df, llm_dims)
    
    # ---- Find the Recipe ----
    recipe = find_karma_recipe(df, all_corr, llm_dims)
    
    # ---- Final Summary ----
    generate_summary_report(all_corr, recipe, high_profile, low_profile, df)
    
    # Save correlation data
    corr_path = os.path.join(BASE_DIR, 'correlations.csv')
    all_corr.to_csv(corr_path, index=False)
    print(f"\n   💾 Correlations saved to: {corr_path}")
    
    print("\n" + "=" * 70)
    print("✅ ANALYSIS COMPLETE!")
    print("=" * 70)
    
    output_files = [
        'karma_drivers.png',
        'correlation_heatmap_llm.png',
        'correlation_heatmap_traditional.png', 
        'karma_correlations_focused.png',
        'karma_profile_radar.png',
        'author_comparison.png',
        'correlations.csv',
        'karma_recipe.json',
    ]
    
    print("\n   📁 Generated files:")
    for f in output_files:
        path = os.path.join(BASE_DIR, f)
        exists = "✅" if os.path.exists(path) else "⏳"
        print(f"      {exists} {f}")
    
    print("\n   💡 Re-run after LLM analysis completes for full 30-dimension results!")
    print()


if __name__ == '__main__':
    main()
