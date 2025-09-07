#!/usr/bin/env python3
"""
Phase 1: Data Exploration & Basic Statistics
============================================

This script performs the initial exploration of hardware-generated randomness data
from a Wemos D1 + ADS1115 four-channel ADC setup. It analyzes basic statistical
properties and creates visualizations to understand the data characteristics.

Hardware Setup:
- CH0, CH1, CH2: Ground connections through different resistors (thermal noise)
- CH3: Dedicated noise circuit output (primary entropy source)

Author: Randomness Analysis Team
Created: 2025-09-07
"""

import sqlite3
from pathlib import Path
from typing import Dict

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats


class RandomnessDataExplorer:
    """
    A class to explore and analyze randomness data from hardware ADC channels.

    This class provides methods to load data, compute statistics, and create
    visualizations for understanding the quality of hardware-generated entropy.
    """

    def __init__(self, database_path: str):
        """
        Initialize the data explorer.

        Args:
            database_path: Path to the SQLite database containing randomness data
        """
        self.database_path = database_path
        self.channel_names = {
            'ch0_raw': 'CH0 (Thermal A0)',
            'ch1_raw': 'CH1 (Thermal A1)',
            'ch2_raw': 'CH2 (Thermal A2)',
            'ch3_raw': 'CH3 (Noise Circuit)'
        }

    def load_sample_data(self, sample_rate: int = 100) -> pd.DataFrame:
        """
        Load a representative sample of the data for analysis.

        Args:
            sample_rate: Take every Nth record (default: 100 for 1% sample)

        Returns:
            DataFrame containing sampled data
        """
        conn = sqlite3.connect(self.database_path)
        query = f"""
        SELECT ch0_raw, ch1_raw, ch2_raw, ch3_raw, combined_word, timestamp
        FROM randomness_data
        WHERE id % {sample_rate} = 0
        ORDER BY timestamp
        """

        data_frame = pd.read_sql_query(query, conn)
        conn.close()

        print(f"Loaded sample: {len(data_frame):,} records (1:{sample_rate} sampling)")
        return data_frame

    def _compute_channel_statistics(self, data: np.ndarray) -> Dict:
        """
        Compute comprehensive statistics for a single channel.

        Args:
            data: NumPy array of channel values

        Returns:
            Dictionary containing channel statistics
        """
        # Basic statistics
        channel_stats = {
            'count': len(data),
            'mean': float(np.mean(data)),
            'std': float(np.std(data)),
            'min': int(np.min(data)),
            'max': int(np.max(data)),
            'range': int(np.max(data) - np.min(data)),
            'skewness': float(stats.skew(data)),
            'kurtosis': float(stats.kurtosis(data))
        }

        # Normality test
        jb_stat, jb_pvalue = stats.jarque_bera(data)
        channel_stats['jarque_bera'] = {
            'statistic': float(jb_stat),
            'p_value': float(jb_pvalue),
            'is_normal': jb_pvalue > 0.05
        }

        # LSB analysis (critical for randomness)
        lsbs = data & 1  # Extract least significant bits
        lsb_ones = int(np.sum(lsbs))
        lsb_zeros = len(lsbs) - lsb_ones
        lsb_bias = abs(0.5 - (lsb_ones / len(lsbs)))

        channel_stats['lsb_analysis'] = {
            'ones_count': lsb_ones,
            'zeros_count': lsb_zeros,
            'ones_percentage': float(100 * lsb_ones / len(lsbs)),
            'bias_from_50pct': float(lsb_bias),
            'bias_percentage': float(100 * lsb_bias)
        }

        return channel_stats

    def compute_basic_statistics(self) -> Dict:
        """
        Compute comprehensive statistics for all channels.

        Returns:
            Dictionary containing statistics for each channel
        """
        conn = sqlite3.connect(self.database_path)

        # Get basic dataset info
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM randomness_data')
        total_records, min_ts, max_ts = cursor.fetchone()
        duration_hours = (max_ts - min_ts) / 3600

        # Load full data for statistics (memory permitting)
        query = 'SELECT ch0_raw, ch1_raw, ch2_raw, ch3_raw, combined_word FROM randomness_data'
        data_frame = pd.read_sql_query(query, conn)
        conn.close()

        statistics_dict = {
            'dataset_info': {
                'total_records': total_records,
                'duration_hours': duration_hours,
                'sample_rate_hz': total_records / (duration_hours * 3600)
            }
        }

        # Analyze each channel
        channels = ['ch0_raw', 'ch1_raw', 'ch2_raw', 'ch3_raw']

        for channel in channels:
            data = data_frame[channel].values
            statistics_dict[channel] = self._compute_channel_statistics(data)

        # Combined word analysis
        cw_data = data_frame['combined_word'].values
        unique_count = len(np.unique(cw_data))

        # Test bit balance across different positions
        bit_balance = {}
        test_positions = [0, 7, 15, 23, 31]  # Sample key bit positions

        for bit_pos in test_positions:
            bits = (cw_data >> bit_pos) & 1
            ones = int(np.sum(bits))
            bias = abs(0.5 - (ones / len(bits)))

            bit_balance[f'bit_{bit_pos}'] = {
                'ones_count': ones,
                'ones_percentage': float(100 * ones / len(bits)),
                'bias_percentage': float(100 * bias)
            }

        statistics_dict['combined_word'] = {
            'total_values': len(cw_data),
            'unique_values': unique_count,
            'uniqueness_percentage': float(100 * unique_count / len(cw_data)),
            'mean': float(np.mean(cw_data)),
            'std': float(np.std(cw_data)),
            'bit_balance': bit_balance
        }

        return statistics_dict

    def _create_channel_distributions_plot(self, sample_data: pd.DataFrame,
                                         output_path: Path) -> None:
        """Create channel distributions and LSB analysis plots."""
        channels = ['ch0_raw', 'ch1_raw', 'ch2_raw', 'ch3_raw']
        colors = ['blue', 'green', 'orange', 'red']

        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        fig.suptitle('Hardware Randomness Generator - Channel Analysis',
                     fontsize=16, fontweight='bold')

        # Plot raw value distributions
        for i, (channel, color) in enumerate(zip(channels, colors)):
            row, col = divmod(i, 2)
            channel_name = self.channel_names[channel]

            axes[row, col].hist(sample_data[channel], bins=50, alpha=0.7,
                              color=color, edgecolor='black', density=True)
            axes[row, col].set_title(f'{channel_name}\nRaw Value Distribution')
            axes[row, col].set_xlabel('ADC Value')
            axes[row, col].set_ylabel('Density')
            axes[row, col].grid(True, alpha=0.3)

            # Add statistics text
            mean_val = np.mean(sample_data[channel])
            std_val = np.std(sample_data[channel])
            axes[row, col].text(0.02, 0.98, f'μ={mean_val:.1f}\nσ={std_val:.1f}',
                              transform=axes[row, col].transAxes,
                              verticalalignment='top',
                              bbox={'boxstyle': 'round', 'facecolor': 'white', 'alpha': 0.8})

        # LSB balance comparison
        lsb_ones_pct = []
        labels = []

        for channel in channels:
            lsbs = sample_data[channel] & 1
            ones_pct = 100 * np.mean(lsbs)
            lsb_ones_pct.append(ones_pct)
            labels.append(self.channel_names[channel])

        axes[1, 2].bar(range(len(channels)), lsb_ones_pct, alpha=0.7,
                      color=colors, edgecolor='black')
        axes[1, 2].axhline(y=50, color='red', linestyle='--',
                          alpha=0.7, label='Perfect 50%')
        axes[1, 2].set_title('LSB Balance Comparison\n(% of 1 bits)')
        axes[1, 2].set_ylabel('Percentage of 1s')
        axes[1, 2].set_xticks(range(len(channels)))
        axes[1, 2].set_xticklabels(['CH0', 'CH1', 'CH2', 'CH3'], rotation=45)
        axes[1, 2].set_ylim(49, 51)
        axes[1, 2].legend()
        axes[1, 2].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path / 'phase1_channel_distributions.png',
                   dpi=150, bbox_inches='tight')
        plt.close()

    def _create_combined_analysis_plot(self, sample_data: pd.DataFrame,
                                     output_path: Path) -> None:
        """Create combined word and correlation analysis plots."""
        channels = ['ch0_raw', 'ch1_raw', 'ch2_raw', 'ch3_raw']

        fig, axes = plt.subplots(1, 3, figsize=(18, 6))
        fig.suptitle('Combined Word and Channel Correlation Analysis',
                     fontsize=16, fontweight='bold')

        # Combined word histogram
        axes[0].hist(sample_data['combined_word'], bins=50, alpha=0.7,
                    color='purple', edgecolor='black', density=True)
        axes[0].set_title('Combined Word Distribution')
        axes[0].set_xlabel('32-bit Combined Word Value')
        axes[0].set_ylabel('Density')
        axes[0].grid(True, alpha=0.3)

        # Bit position balance in combined words
        bit_positions = [0, 1, 2, 3, 4, 5, 6, 7, 15, 23, 31]
        bit_ones_pct = []

        for bit_pos in bit_positions:
            bits = (sample_data['combined_word'].values >> bit_pos) & 1
            ones_pct = 100 * np.mean(bits)
            bit_ones_pct.append(ones_pct)

        axes[1].bar(range(len(bit_positions)), bit_ones_pct, alpha=0.7,
                   color='teal', edgecolor='black')
        axes[1].axhline(y=50, color='red', linestyle='--',
                       alpha=0.7, label='Perfect 50%')
        axes[1].set_title('Bit Position Balance\nin Combined Words')
        axes[1].set_xlabel('Bit Position')
        axes[1].set_ylabel('Percentage of 1s')
        axes[1].set_xticks(range(len(bit_positions)))
        axes[1].set_xticklabels(bit_positions)
        axes[1].set_ylim(49, 51)
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)

        # Channel correlation heatmap
        corr_matrix = sample_data[channels].corr()
        sns.heatmap(corr_matrix, annot=True, cmap='RdBu_r', center=0,
                   square=True, ax=axes[2], cbar_kws={'shrink': 0.8},
                   xticklabels=['CH0', 'CH1', 'CH2', 'CH3'],
                   yticklabels=['CH0', 'CH1', 'CH2', 'CH3'])
        axes[2].set_title('Inter-Channel Correlation\n(Raw Values)')

        plt.tight_layout()
        plt.savefig(output_path / 'phase1_combined_analysis.png',
                   dpi=150, bbox_inches='tight')
        plt.close()

    def create_visualizations(self, sample_data: pd.DataFrame, output_dir: str = '.'):
        """
        Create comprehensive visualizations of the data.

        Args:
            sample_data: DataFrame with sampled data
            output_dir: Directory to save plots
        """
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        # Set up plotting style
        plt.style.use('default')
        sns.set_palette('husl')
        plt.rcParams['figure.figsize'] = (12, 8)
        plt.rcParams['font.size'] = 10

        # Create plots
        self._create_channel_distributions_plot(sample_data, output_path)
        self._create_combined_analysis_plot(sample_data, output_path)

        print(f"Visualizations saved to {output_path}/")

    def print_statistics_report(self, statistics_data: Dict) -> None:
        """
        Print a formatted statistics report.

        Args:
            statistics_data: Statistics dictionary from compute_basic_statistics()
        """
        print("\n" + "="*60)
        print("HARDWARE RANDOMNESS GENERATOR - STATISTICAL ANALYSIS")
        print("="*60)

        # Dataset overview
        info = statistics_data['dataset_info']
        print("\nDataset Overview:")
        print(f"  Total Records: {info['total_records']:,}")
        print(f"  Duration: {info['duration_hours']:.1f} hours")
        print(f"  Effective Sample Rate: {info['sample_rate_hz']:.1f} Hz")

        # Channel analysis
        channels = ['ch0_raw', 'ch1_raw', 'ch2_raw', 'ch3_raw']

        print("\nChannel Analysis:")
        print(f"{'Channel':<20} {'Range':<12} {'Mean':<8} {'Std':<8} {'LSB Bias':<10}")
        print("-" * 70)

        for channel in channels:
            ch_stats = statistics_data[channel]
            channel_name = self.channel_names[channel]
            lsb_bias = ch_stats['lsb_analysis']['bias_percentage']

            print(f"{channel_name:<20} "
                  f"{ch_stats['range']:<12,} "
                  f"{ch_stats['mean']:<8.1f} "
                  f"{ch_stats['std']:<8.1f} "
                  f"{lsb_bias:<10.3f}%")

        # Combined word analysis
        cw_stats = statistics_data['combined_word']
        print("\nCombined Word Analysis:")
        print(f"  Unique Values: {cw_stats['unique_values']:,} / "
              f"{cw_stats['total_values']:,} "
              f"({cw_stats['uniqueness_percentage']:.3f}%)")

        print("\n  Bit Position Balance:")
        for bit_key, bit_data in cw_stats['bit_balance'].items():
            bit_pos = bit_key.split('_')[1]
            print(f"    Bit {bit_pos:>2}: "
                  f"{bit_data['ones_percentage']:.3f}% ones "
                  f"(bias: {bit_data['bias_percentage']:.3f}%)")


def main():
    """Main execution function."""
    # Initialize the explorer
    db_path = '../randomness_optimized.db'
    explorer = RandomnessDataExplorer(db_path)

    print("Phase 1: Data Exploration & Basic Statistics")
    print("=" * 50)

    # Compute comprehensive statistics
    print("Computing comprehensive statistics...")
    analysis_stats = explorer.compute_basic_statistics()

    # Print detailed report
    explorer.print_statistics_report(analysis_stats)

    # Load sample data for visualizations
    print("\nLoading sample data for visualizations...")
    sample_df = explorer.load_sample_data(sample_rate=100)

    # Create visualizations
    print("Creating visualizations...")
    explorer.create_visualizations(sample_df, output_dir='.')

    print("\nPhase 1 analysis complete!")
    print("Generated files:")
    print("  - phase1_channel_distributions.png")
    print("  - phase1_combined_analysis.png")
    print("\nReady to proceed to Phase 2: Individual Channel Randomness Assessment")


if __name__ == "__main__":
    main()
