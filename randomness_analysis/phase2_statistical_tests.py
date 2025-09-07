#!/usr/bin/env python3
"""
Phase 2: Individual Channel Randomness Assessment
=================================================

This script performs comprehensive statistical tests on individual channels to assess
randomness quality. Tests include classical statistical methods used in randomness
evaluation: chi-square tests, Kolmogorov-Smirnov tests, runs tests, and autocorrelation.

Statistical Tests Applied:
- Chi-Square Goodness of Fit (LSB uniformity)
- Kolmogorov-Smirnov Test (distribution assessment)
- Runs Test (independence of consecutive bits)
- Serial Correlation Analysis (temporal dependencies)
- Frequency Analysis (bit pattern distributions)

Author: Randomness Analysis Team
Created: 2025-09-07
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import acf


class StatisticalRandomnessAnalyzer:
    """
    Comprehensive statistical analysis of individual channel randomness quality.
    
    This class implements classical statistical tests used to evaluate random
    number generators and hardware entropy sources.
    """
    
    def __init__(self, database_path: str):
        """
        Initialize the statistical analyzer.
        
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
        
    def load_channel_data(self, channel: str, sample_size: int = None) -> np.ndarray:
        """
        Load data for a specific channel with optional sampling.
        
        Args:
            channel: Channel name (e.g., 'ch0_raw')
            sample_size: Maximum number of samples to load (None for all data)
            
        Returns:
            NumPy array containing channel data
        """
        conn = sqlite3.connect(self.database_path)
        
        if sample_size is None:
            query = f"SELECT {channel} FROM randomness_data ORDER BY timestamp"
        else:
            # Use systematic sampling for representative data
            query = f"""
            SELECT {channel} FROM randomness_data 
            WHERE id % (SELECT COUNT(*) / {sample_size} FROM randomness_data) = 0
            ORDER BY timestamp
            LIMIT {sample_size}
            """
            
        cursor = conn.cursor()
        cursor.execute(query)
        data = np.array([row[0] for row in cursor.fetchall()])
        conn.close()
        
        print(f"Loaded {len(data):,} samples for {channel}")
        return data
        
    def chi_square_lsb_test(self, data: np.ndarray) -> Dict:
        """
        Perform chi-square goodness of fit test on LSB distribution.
        
        This test evaluates whether the least significant bits follow a uniform
        distribution (50% zeros, 50% ones) as expected for random data.
        
        Args:
            data: Channel data array
            
        Returns:
            Dictionary containing test results
        """
        # Extract LSBs
        lsbs = data & 1
        
        # Count zeros and ones
        ones_count = np.sum(lsbs)
        zeros_count = len(lsbs) - ones_count
        observed = np.array([zeros_count, ones_count])
        
        # Expected frequencies for uniform distribution
        expected = np.array([len(lsbs) / 2, len(lsbs) / 2])
        
        # Perform chi-square test
        chi2_stat, p_value = stats.chisquare(observed, expected)
        
        return {
            'test_name': 'Chi-Square LSB Uniformity',
            'chi2_statistic': float(chi2_stat),
            'p_value': float(p_value),
            'degrees_of_freedom': 1,
            'critical_value_95': 3.841,  # Chi-square critical value at 95% confidence
            'passes_95': p_value > 0.05,
            'observed_counts': observed.tolist(),
            'expected_counts': expected.tolist(),
            'ones_percentage': float(100 * ones_count / len(lsbs))
        }
        
    def kolmogorov_smirnov_test(self, data: np.ndarray) -> Dict:
        """
        Perform Kolmogorov-Smirnov test against uniform and normal distributions.
        
        Tests whether the raw ADC values follow expected statistical distributions.
        For hardware noise, we expect deviation from uniform but not from normal.
        
        Args:
            data: Channel data array
            
        Returns:
            Dictionary containing KS test results
        """
        # Test against uniform distribution
        data_normalized = (data - np.min(data)) / (np.max(data) - np.min(data))
        ks_uniform_stat, ks_uniform_p = stats.kstest(data_normalized, 'uniform')
        
        # Test against normal distribution
        data_standardized = (data - np.mean(data)) / np.std(data)
        ks_normal_stat, ks_normal_p = stats.kstest(data_standardized, 'norm')
        
        return {
            'test_name': 'Kolmogorov-Smirnov Distribution Tests',
            'uniform_test': {
                'statistic': float(ks_uniform_stat),
                'p_value': float(ks_uniform_p),
                'passes_95': ks_uniform_p > 0.05,
                'interpretation': 'PASS means data is uniform (unexpected for ADC noise)'
            },
            'normal_test': {
                'statistic': float(ks_normal_stat),
                'p_value': float(ks_normal_p),
                'passes_95': ks_normal_p > 0.05,
                'interpretation': 'PASS means data is normally distributed (expected for noise)'
            }
        }
        
    def runs_test(self, data: np.ndarray, max_samples: int = 100000) -> Dict:
        """
        Perform runs test on LSB sequence for independence.
        
        A "run" is a sequence of consecutive identical bits. For random data,
        the number and length of runs should follow specific statistical patterns.
        
        Args:
            data: Channel data array
            max_samples: Maximum samples to use (for performance)
            
        Returns:
            Dictionary containing runs test results
        """
        # Use sample if data is too large
        if len(data) > max_samples:
            sample_indices = np.linspace(0, len(data)-1, max_samples, dtype=int)
            test_data = data[sample_indices]
        else:
            test_data = data.copy()
            
        # Extract LSBs
        lsbs = test_data & 1
        n_samples = len(lsbs)
        
        # Count runs
        runs = []
        current_run_length = 1
        
        for i in range(1, len(lsbs)):
            if lsbs[i] == lsbs[i-1]:
                current_run_length += 1
            else:
                runs.append(current_run_length)
                current_run_length = 1
        runs.append(current_run_length)  # Add final run
        
        n_runs = len(runs)
        
        # Calculate expected runs for random sequence
        n_ones = np.sum(lsbs)
        n_zeros = n_samples - n_ones
        
        if n_ones == 0 or n_zeros == 0:
            return {
                'test_name': 'Runs Test (LSB Independence)',
                'error': 'All bits are identical - no randomness detected'
            }
            
        expected_runs = (2 * n_ones * n_zeros / n_samples) + 1
        variance_runs = (2 * n_ones * n_zeros * (2 * n_ones * n_zeros - n_samples)) / \
                       (n_samples ** 2 * (n_samples - 1))
                       
        # Z-score for runs test
        if variance_runs > 0:
            z_score = (n_runs - expected_runs) / np.sqrt(variance_runs)
            p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))  # Two-tailed test
        else:
            z_score = float('inf')
            p_value = 0.0
            
        return {
            'test_name': 'Runs Test (LSB Independence)',
            'observed_runs': n_runs,
            'expected_runs': float(expected_runs),
            'z_score': float(z_score),
            'p_value': float(p_value),
            'passes_95': p_value > 0.05,
            'samples_tested': n_samples,
            'ones_count': int(n_ones),
            'zeros_count': int(n_zeros),
            'average_run_length': float(np.mean(runs)),
            'max_run_length': int(np.max(runs))
        }
        
    def serial_correlation_analysis(self, data: np.ndarray, 
                                  max_lags: int = 50,
                                  max_samples: int = 50000) -> Dict:
        """
        Analyze serial correlation in LSB sequence.
        
        Serial correlation measures whether current bits are correlated with
        previous bits at various time lags. Random data should show no correlation.
        
        Args:
            data: Channel data array  
            max_lags: Maximum number of lags to test
            max_samples: Maximum samples for performance
            
        Returns:
            Dictionary containing correlation analysis results
        """
        # Sample data if too large
        if len(data) > max_samples:
            sample_indices = np.linspace(0, len(data)-1, max_samples, dtype=int)
            test_data = data[sample_indices]
        else:
            test_data = data.copy()
            
        # Extract LSBs
        lsbs = test_data & 1
        
        # Calculate autocorrelation function
        autocorr_coeffs = acf(lsbs, nlags=max_lags, fft=True)
        
        # Ljung-Box test for serial correlation
        lb_stat, lb_p_value = acorr_ljungbox(lsbs, lags=min(20, max_lags//2), 
                                           return_df=False)
        
        # Find maximum correlation (excluding lag 0)
        max_corr_idx = np.argmax(np.abs(autocorr_coeffs[1:]))
        max_correlation = autocorr_coeffs[max_corr_idx + 1]
        
        # Significance bounds (95% confidence)
        significance_bound = 1.96 / np.sqrt(len(lsbs))
        
        return {
            'test_name': 'Serial Correlation Analysis',
            'samples_analyzed': len(lsbs),
            'max_lags_tested': max_lags,
            'autocorr_coefficients': autocorr_coeffs.tolist(),
            'ljung_box_statistic': float(lb_stat.iloc[-1]),
            'ljung_box_p_value': float(lb_p_value.iloc[-1]),
            'passes_ljung_box_95': float(lb_p_value.iloc[-1]) > 0.05,
            'max_correlation': float(max_correlation),
            'max_correlation_lag': int(max_corr_idx + 1),
            'significance_bound_95': float(significance_bound),
            'correlations_within_bounds': bool(np.all(np.abs(autocorr_coeffs[1:]) < significance_bound))
        }
        
    def frequency_analysis(self, data: np.ndarray, block_size: int = 8) -> Dict:
        """
        Analyze frequency patterns in bit blocks.
        
        Tests the distribution of bit patterns in consecutive blocks.
        Random data should show uniform distribution of all possible patterns.
        
        Args:
            data: Channel data array
            block_size: Size of bit blocks to analyze
            
        Returns:
            Dictionary containing frequency analysis results
        """
        # Extract LSBs and group into blocks
        lsbs = data & 1
        
        # Create blocks
        n_complete_blocks = len(lsbs) // block_size
        blocks_data = lsbs[:n_complete_blocks * block_size].reshape(-1, block_size)
        
        # Convert each block to integer value
        block_values = []
        for block in blocks_data:
            value = sum(bit * (2**i) for i, bit in enumerate(reversed(block)))
            block_values.append(value)
            
        block_values = np.array(block_values)
        
        # Count frequency of each possible pattern
        max_pattern_value = 2**block_size - 1
        pattern_counts = np.bincount(block_values, minlength=max_pattern_value + 1)
        
        # Expected frequency for uniform distribution
        expected_freq = len(block_values) / (2**block_size)
        expected_counts = np.full(2**block_size, expected_freq)
        
        # Chi-square test on pattern frequencies
        chi2_stat, chi2_p = stats.chisquare(pattern_counts, expected_counts)
        
        return {
            'test_name': f'{block_size}-bit Block Frequency Analysis',
            'block_size': block_size,
            'total_blocks': len(block_values),
            'possible_patterns': 2**block_size,
            'pattern_counts': pattern_counts.tolist(),
            'expected_frequency': float(expected_freq),
            'chi2_statistic': float(chi2_stat),
            'chi2_p_value': float(chi2_p),
            'chi2_degrees_freedom': 2**block_size - 1,
            'passes_chi2_95': chi2_p > 0.05,
            'most_frequent_pattern': int(np.argmax(pattern_counts)),
            'least_frequent_pattern': int(np.argmin(pattern_counts)),
            'frequency_range': [int(np.min(pattern_counts)), int(np.max(pattern_counts))]
        }
        
    def comprehensive_channel_analysis(self, channel: str, 
                                     sample_size: int = 100000) -> Dict:
        """
        Perform complete statistical analysis on a single channel.
        
        Args:
            channel: Channel name (e.g., 'ch0_raw')
            sample_size: Number of samples to analyze
            
        Returns:
            Dictionary containing all test results
        """
        print(f"\n{'='*60}")
        print(f"ANALYZING {self.channel_names[channel]}")
        print(f"{'='*60}")
        
        # Load data
        data = self.load_channel_data(channel, sample_size)
        
        results = {
            'channel': channel,
            'channel_name': self.channel_names[channel],
            'samples_analyzed': len(data),
            'data_range': [int(np.min(data)), int(np.max(data))],
            'mean': float(np.mean(data)),
            'std': float(np.std(data))
        }
        
        # Perform all statistical tests
        print("Running Chi-Square LSB test...")
        results['chi_square_lsb'] = self.chi_square_lsb_test(data)
        
        print("Running Kolmogorov-Smirnov tests...")
        results['kolmogorov_smirnov'] = self.kolmogorov_smirnov_test(data)
        
        print("Running Runs test...")
        results['runs_test'] = self.runs_test(data)
        
        print("Running Serial Correlation analysis...")
        results['serial_correlation'] = self.serial_correlation_analysis(data)
        
        print("Running Frequency analysis...")
        results['frequency_analysis'] = self.frequency_analysis(data)
        
        return results
        
    def analyze_all_channels(self, sample_size: int = 100000) -> Dict:
        """
        Analyze all four channels comprehensively.
        
        Args:
            sample_size: Number of samples per channel
            
        Returns:
            Dictionary containing results for all channels
        """
        channels = ['ch0_raw', 'ch1_raw', 'ch2_raw', 'ch3_raw']
        results = {}
        
        for channel in channels:
            results[channel] = self.comprehensive_channel_analysis(channel, sample_size)
            
        return results
        
    def create_statistical_visualizations(self, results: Dict, output_dir: str = '.'):
        """
        Create visualizations of statistical test results.
        
        Args:
            results: Results dictionary from analyze_all_channels()
            output_dir: Directory to save plots
        """
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        channels = ['ch0_raw', 'ch1_raw', 'ch2_raw', 'ch3_raw']
        channel_names = [results[ch]['channel_name'] for ch in channels]
        
        # Set up plotting
        plt.style.use('default')
        sns.set_palette('husl')
        
        # Figure 1: Test Results Summary
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Phase 2: Statistical Test Results Summary', fontsize=16, fontweight='bold')
        
        # Chi-Square LSB Test Results
        chi2_p_values = [results[ch]['chi_square_lsb']['p_value'] for ch in channels]
        colors = ['green' if p > 0.05 else 'red' for p in chi2_p_values]
        
        axes[0, 0].bar(range(len(channels)), chi2_p_values, color=colors, alpha=0.7, edgecolor='black')
        axes[0, 0].axhline(y=0.05, color='red', linestyle='--', alpha=0.7, label='95% Significance')
        axes[0, 0].set_title('Chi-Square LSB Uniformity Test\n(Higher p-values = Better)')
        axes[0, 0].set_ylabel('p-value')
        axes[0, 0].set_xticks(range(len(channels)))
        axes[0, 0].set_xticklabels(['CH0', 'CH1', 'CH2', 'CH3'])
        axes[0, 0].set_yscale('log')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # Runs Test Results
        runs_p_values = [results[ch]['runs_test']['p_value'] for ch in channels]
        colors = ['green' if p > 0.05 else 'red' for p in runs_p_values]
        
        axes[0, 1].bar(range(len(channels)), runs_p_values, color=colors, alpha=0.7, edgecolor='black')
        axes[0, 1].axhline(y=0.05, color='red', linestyle='--', alpha=0.7, label='95% Significance')
        axes[0, 1].set_title('Runs Test (Independence)\n(Higher p-values = Better)')
        axes[0, 1].set_ylabel('p-value')
        axes[0, 1].set_xticks(range(len(channels)))
        axes[0, 1].set_xticklabels(['CH0', 'CH1', 'CH2', 'CH3'])
        axes[0, 1].set_yscale('log')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # Serial Correlation Test Results  
        ljung_p_values = [results[ch]['serial_correlation']['ljung_box_p_value'] for ch in channels]
        colors = ['green' if p > 0.05 else 'red' for p in ljung_p_values]
        
        axes[1, 0].bar(range(len(channels)), ljung_p_values, color=colors, alpha=0.7, edgecolor='black')
        axes[1, 0].axhline(y=0.05, color='red', linestyle='--', alpha=0.7, label='95% Significance')
        axes[1, 0].set_title('Ljung-Box Serial Correlation\n(Higher p-values = Better)')
        axes[1, 0].set_ylabel('p-value')
        axes[1, 0].set_xticks(range(len(channels)))
        axes[1, 0].set_xticklabels(['CH0', 'CH1', 'CH2', 'CH3'])
        axes[1, 0].set_yscale('log')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        
        # Frequency Analysis Results
        freq_p_values = [results[ch]['frequency_analysis']['chi2_p_value'] for ch in channels]
        colors = ['green' if p > 0.05 else 'red' for p in freq_p_values]
        
        axes[1, 1].bar(range(len(channels)), freq_p_values, color=colors, alpha=0.7, edgecolor='black')
        axes[1, 1].axhline(y=0.05, color='red', linestyle='--', alpha=0.7, label='95% Significance')
        axes[1, 1].set_title('8-bit Block Frequency Test\n(Higher p-values = Better)')
        axes[1, 1].set_ylabel('p-value')
        axes[1, 1].set_xticks(range(len(channels)))
        axes[1, 1].set_xticklabels(['CH0', 'CH1', 'CH2', 'CH3'])
        axes[1, 1].set_yscale('log')
        axes[1, 1].legend()
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_path / 'phase2_statistical_test_summary.png', 
                   dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"Statistical visualization saved to {output_path}/phase2_statistical_test_summary.png")
        
    def generate_statistical_report(self, results: Dict) -> None:
        """
        Generate comprehensive statistical analysis report.
        
        Args:
            results: Results dictionary from analyze_all_channels()
        """
        print("\n" + "="*80)
        print("PHASE 2: STATISTICAL RANDOMNESS ASSESSMENT - COMPREHENSIVE REPORT")
        print("="*80)
        
        channels = ['ch0_raw', 'ch1_raw', 'ch2_raw', 'ch3_raw']
        
        # Summary table
        print(f"\n{'Channel':<20} {'Chi²-LSB':<10} {'Runs':<10} {'LjungBox':<12} {'FreqAnal':<10} {'Overall':<8}")
        print("-" * 82)
        
        for channel in channels:
            r = results[channel]
            
            # Collect p-values
            chi2_pass = "PASS" if r['chi_square_lsb']['passes_95'] else "FAIL"
            runs_pass = "PASS" if r['runs_test']['passes_95'] else "FAIL"
            ljung_pass = "PASS" if r['serial_correlation']['passes_ljung_box_95'] else "FAIL"
            freq_pass = "PASS" if r['frequency_analysis']['passes_chi2_95'] else "FAIL"
            
            # Overall assessment
            all_pass = all([r['chi_square_lsb']['passes_95'], 
                           r['runs_test']['passes_95'],
                           r['serial_correlation']['passes_ljung_box_95'],
                           r['frequency_analysis']['passes_chi2_95']])
            overall = "PASS" if all_pass else "FAIL"
            
            channel_name = r['channel_name']
            print(f"{channel_name:<20} {chi2_pass:<10} {runs_pass:<10} {ljung_pass:<12} {freq_pass:<10} {overall:<8}")
            
        # Detailed results
        for channel in channels:
            r = results[channel]
            print(f"\n{'-'*60}")
            print(f"DETAILED RESULTS: {r['channel_name']}")
            print(f"{'-'*60}")
            
            print(f"Data Summary:")
            print(f"  Samples analyzed: {r['samples_analyzed']:,}")
            print(f"  Value range: {r['data_range'][0]:,} to {r['data_range'][1]:,}")
            print(f"  Mean: {r['mean']:.2f}, Std: {r['std']:.2f}")
            
            # Chi-square LSB test
            chi2 = r['chi_square_lsb']
            print(f"\nChi-Square LSB Uniformity Test:")
            print(f"  Statistic: {chi2['chi2_statistic']:.4f}")
            print(f"  p-value: {chi2['p_value']:.6f}")
            print(f"  Result: {'PASS' if chi2['passes_95'] else 'FAIL'} (95% confidence)")
            print(f"  LSB ones: {chi2['ones_percentage']:.3f}%")
            
            # Runs test
            runs = r['runs_test']
            print(f"\nRuns Test (LSB Independence):")
            print(f"  Observed runs: {runs['observed_runs']}")
            print(f"  Expected runs: {runs['expected_runs']:.1f}")
            print(f"  Z-score: {runs['z_score']:.4f}")
            print(f"  p-value: {runs['p_value']:.6f}")
            print(f"  Result: {'PASS' if runs['passes_95'] else 'FAIL'} (95% confidence)")
            print(f"  Max run length: {runs['max_run_length']}")
            
            # Serial correlation
            corr = r['serial_correlation']
            print(f"\nSerial Correlation Analysis:")
            print(f"  Ljung-Box statistic: {corr['ljung_box_statistic']:.4f}")
            print(f"  Ljung-Box p-value: {corr['ljung_box_p_value']:.6f}")
            print(f"  Result: {'PASS' if corr['passes_ljung_box_95'] else 'FAIL'} (95% confidence)")
            print(f"  Max correlation: {corr['max_correlation']:.4f} at lag {corr['max_correlation_lag']}")
            print(f"  All correlations within bounds: {'YES' if corr['correlations_within_bounds'] else 'NO'}")
            
            # Frequency analysis
            freq = r['frequency_analysis']
            print(f"\n8-bit Block Frequency Analysis:")
            print(f"  Blocks analyzed: {freq['total_blocks']:,}")
            print(f"  Chi-square statistic: {freq['chi2_statistic']:.4f}")
            print(f"  Chi-square p-value: {freq['chi2_p_value']:.6f}")
            print(f"  Result: {'PASS' if freq['passes_chi2_95'] else 'FAIL'} (95% confidence)")
            print(f"  Frequency range: {freq['frequency_range'][0]} - {freq['frequency_range'][1]}")


def main():
    """Main execution function for Phase 2 analysis."""
    print("Phase 2: Individual Channel Randomness Assessment")
    print("=" * 55)
    
    # Initialize analyzer
    db_path = '../randomness_optimized.db'
    analyzer = StatisticalRandomnessAnalyzer(db_path)
    
    # Perform comprehensive analysis
    print("Beginning comprehensive statistical analysis...")
    print("This may take several minutes depending on sample size...")
    
    results = analyzer.analyze_all_channels(sample_size=100000)
    
    # Generate report
    analyzer.generate_statistical_report(results)
    
    # Create visualizations
    print("\nCreating statistical visualizations...")
    analyzer.create_statistical_visualizations(results)
    
    print("\nPhase 2 statistical analysis complete!")
    print("Generated files:")
    print("  - phase2_statistical_test_summary.png")
    print("\nReady to proceed to Phase 3: Combined Word Analysis (NIST SP 800-22)")


if __name__ == "__main__":
    main()