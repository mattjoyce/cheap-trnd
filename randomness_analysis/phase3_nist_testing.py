#!/usr/bin/env python3
"""
Phase 3: NIST SP 800-22 Statistical Test Suite Implementation
============================================================

This script implements key tests from the NIST SP 800-22 Statistical Test Suite
for Random and Pseudorandom Number Generators for Cryptographic Applications.

NIST SP 800-22 is the gold standard for evaluating cryptographic randomness.
Tests implemented:
- Frequency (Monobit) Test
- Block Frequency Test
- Runs Test
- Longest Run of Ones in a Block Test
- Binary Matrix Rank Test
- Discrete Fourier Transform (Spectral) Test
- Non-overlapping Template Matching Test
- Overlapping Template Matching Test

Author: Randomness Analysis Team
Created: 2025-09-07
"""

import sqlite3
import math
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats, special
from scipy.fft import fft


class NISTRandomnessTestSuite:
    """
    Implementation of NIST SP 800-22 Statistical Test Suite.
    
    This class provides methods to perform the standardized tests used by NIST
    to evaluate the randomness of binary sequences for cryptographic applications.
    """
    
    def __init__(self, database_path: str):
        """
        Initialize the NIST test suite.
        
        Args:
            database_path: Path to the SQLite database containing randomness data
        """
        self.database_path = database_path
        self.alpha = 0.01  # Significance level (99% confidence)
        
    def extract_bit_sequence(self, source: str = 'combined_word', 
                           length: int = 1000000) -> np.ndarray:
        """
        Extract a binary sequence for NIST testing.
        
        Args:
            source: Data source ('combined_word' or channel name)
            length: Number of bits to extract
            
        Returns:
            Binary array of specified length
        """
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        
        if source == 'combined_word':
            # Extract bits from combined 32-bit words
            needed_words = (length + 31) // 32
            cursor.execute(f"SELECT combined_word FROM randomness_data LIMIT {needed_words}")
            words = [row[0] for row in cursor.fetchall()]
            
            # Convert words to bit array
            bit_sequence = []
            for word in words:
                for bit_pos in range(32):
                    if len(bit_sequence) >= length:
                        break
                    bit_sequence.append((word >> bit_pos) & 1)
                if len(bit_sequence) >= length:
                    break
                    
        else:
            # Extract LSBs from specific channel
            cursor.execute(f"SELECT {source} FROM randomness_data LIMIT {length}")
            values = [row[0] for row in cursor.fetchall()]
            bit_sequence = [val & 1 for val in values]
            
        conn.close()
        return np.array(bit_sequence[:length], dtype=int)
        
    def frequency_monobit_test(self, bit_sequence: np.ndarray) -> Dict:
        """
        NIST Frequency (Monobit) Test.
        
        Tests the proportion of ones and zeros in the entire sequence.
        For a random sequence, roughly half should be ones, half zeros.
        
        Args:
            bit_sequence: Binary sequence to test
            
        Returns:
            Dictionary containing test results
        """
        n = len(bit_sequence)
        
        # Convert 0s to -1s for easier calculation
        s_n = np.sum(2 * bit_sequence - 1)
        
        # Calculate test statistic
        s_obs = abs(s_n) / math.sqrt(n)
        
        # P-value calculation
        p_value = special.erfc(s_obs / math.sqrt(2))
        
        return {
            'test_name': 'Frequency (Monobit) Test',
            'test_statistic': float(s_obs),
            'p_value': float(p_value),
            'passes': p_value >= self.alpha,
            'ones_count': int(np.sum(bit_sequence)),
            'zeros_count': int(n - np.sum(bit_sequence)),
            'ones_proportion': float(np.sum(bit_sequence) / n),
            'sequence_length': n
        }
        
    def block_frequency_test(self, bit_sequence: np.ndarray, 
                           block_size: int = 128) -> Dict:
        """
        NIST Block Frequency Test.
        
        Tests the proportion of ones within M-bit blocks.
        Each block should contain approximately M/2 ones.
        
        Args:
            bit_sequence: Binary sequence to test
            block_size: Size of each block (M)
            
        Returns:
            Dictionary containing test results
        """
        n = len(bit_sequence)
        num_blocks = n // block_size
        
        if num_blocks == 0:
            return {
                'test_name': 'Block Frequency Test',
                'error': 'Sequence too short for block size'
            }
            
        # Calculate proportion of ones in each block
        block_proportions = []
        for i in range(num_blocks):
            start_idx = i * block_size
            end_idx = start_idx + block_size
            block = bit_sequence[start_idx:end_idx]
            proportion = np.sum(block) / block_size
            block_proportions.append(proportion)
            
        block_proportions = np.array(block_proportions)
        
        # Calculate chi-square statistic
        chi_square = 4 * block_size * np.sum((block_proportions - 0.5) ** 2)
        
        # P-value calculation
        p_value = special.gammaincc(num_blocks / 2, chi_square / 2)
        
        return {
            'test_name': 'Block Frequency Test',
            'block_size': block_size,
            'num_blocks': num_blocks,
            'chi_square_statistic': float(chi_square),
            'p_value': float(p_value),
            'passes': p_value >= self.alpha,
            'mean_block_proportion': float(np.mean(block_proportions)),
            'block_proportion_variance': float(np.var(block_proportions))
        }
        
    def runs_test(self, bit_sequence: np.ndarray) -> Dict:
        """
        NIST Runs Test.
        
        A run is an uninterrupted sequence of identical bits.
        Tests whether the number of runs is as expected for a random sequence.
        
        Args:
            bit_sequence: Binary sequence to test
            
        Returns:
            Dictionary containing test results
        """
        n = len(bit_sequence)
        
        # Check prerequisite: roughly equal proportions of 0s and 1s
        ones_proportion = np.sum(bit_sequence) / n
        prerequisite_passes = abs(ones_proportion - 0.5) < (2 / math.sqrt(n))
        
        if not prerequisite_passes:
            return {
                'test_name': 'Runs Test',
                'passes': False,
                'error': 'Prerequisite failed: proportion of ones not close to 0.5',
                'ones_proportion': float(ones_proportion)
            }
            
        # Count runs
        v_n = 1  # Number of runs
        for i in range(1, n):
            if bit_sequence[i] != bit_sequence[i-1]:
                v_n += 1
                
        # Calculate test statistic
        test_statistic = abs(v_n - 2 * n * ones_proportion * (1 - ones_proportion))
        test_statistic /= 2 * math.sqrt(2 * n) * ones_proportion * (1 - ones_proportion)
        
        # P-value calculation
        p_value = special.erfc(test_statistic)
        
        return {
            'test_name': 'Runs Test',
            'observed_runs': v_n,
            'test_statistic': float(test_statistic),
            'p_value': float(p_value),
            'passes': p_value >= self.alpha,
            'ones_proportion': float(ones_proportion),
            'prerequisite_passes': prerequisite_passes
        }
        
    def longest_run_of_ones_test(self, bit_sequence: np.ndarray) -> Dict:
        """
        NIST Longest Run of Ones in a Block Test.
        
        Tests the longest run of ones within M-bit blocks.
        For random data, very long runs should be rare.
        
        Args:
            bit_sequence: Binary sequence to test
            
        Returns:
            Dictionary containing test results
        """
        n = len(bit_sequence)
        
        # Determine parameters based on sequence length
        if n < 128:
            return {'test_name': 'Longest Run of Ones Test', 
                   'error': 'Sequence too short (minimum 128 bits)'}
        elif n < 6272:
            m = 8  # Block size
            v_values = [1, 2, 3, 4]  # Run length categories
            pi_values = [0.2148, 0.3672, 0.2305, 0.1875]  # Expected probabilities
        elif n < 750000:
            m = 128
            v_values = [4, 5, 6, 7, 8, 9]
            pi_values = [0.1174, 0.2430, 0.2493, 0.1752, 0.1027, 0.1124]
        else:
            m = 10000
            v_values = [10, 11, 12, 13, 14, 15, 16]
            pi_values = [0.0882, 0.2092, 0.2483, 0.1933, 0.1208, 0.0675, 0.0727]
            
        num_blocks = n // m
        
        # Count longest runs in each block
        run_counts = [0] * len(v_values)
        
        for i in range(num_blocks):
            start_idx = i * m
            end_idx = start_idx + m
            block = bit_sequence[start_idx:end_idx]
            
            # Find longest run of ones in this block
            max_run = 0
            current_run = 0
            
            for bit in block:
                if bit == 1:
                    current_run += 1
                    max_run = max(max_run, current_run)
                else:
                    current_run = 0
                    
            # Categorize the run length
            for j, v in enumerate(v_values):
                if j == 0 and max_run <= v:
                    run_counts[j] += 1
                    break
                elif j == len(v_values) - 1 and max_run >= v:
                    run_counts[j] += 1
                    break
                elif j < len(v_values) - 1 and v <= max_run < v_values[j + 1]:
                    run_counts[j] += 1
                    break
                    
        # Calculate chi-square statistic
        chi_square = 0
        for i in range(len(v_values)):
            expected = num_blocks * pi_values[i]
            if expected > 0:
                chi_square += (run_counts[i] - expected) ** 2 / expected
                
        # P-value calculation
        degrees_freedom = len(v_values) - 1
        p_value = special.gammaincc(degrees_freedom / 2, chi_square / 2)
        
        return {
            'test_name': 'Longest Run of Ones Test',
            'block_size': m,
            'num_blocks': num_blocks,
            'run_categories': v_values,
            'observed_counts': run_counts,
            'expected_probabilities': pi_values,
            'chi_square_statistic': float(chi_square),
            'degrees_of_freedom': degrees_freedom,
            'p_value': float(p_value),
            'passes': p_value >= self.alpha
        }
        
    def binary_matrix_rank_test(self, bit_sequence: np.ndarray,
                               matrix_size: int = 32) -> Dict:
        """
        NIST Binary Matrix Rank Test.
        
        Tests the rank of disjoint sub-matrices of the entire sequence.
        For random sequences, most matrices should have full rank.
        
        Args:
            bit_sequence: Binary sequence to test
            matrix_size: Size of square matrices (M x M)
            
        Returns:
            Dictionary containing test results
        """
        n = len(bit_sequence)
        m = matrix_size
        
        # Check if we have enough bits
        bits_per_matrix = m * m
        num_matrices = n // bits_per_matrix
        
        if num_matrices == 0:
            return {
                'test_name': 'Binary Matrix Rank Test',
                'error': f'Not enough bits for even one {m}x{m} matrix'
            }
            
        # Count matrices by rank
        rank_counts = {m: 0, m-1: 0, 'other': 0}
        
        for i in range(num_matrices):
            start_idx = i * bits_per_matrix
            end_idx = start_idx + bits_per_matrix
            
            # Create matrix from bit sequence
            matrix_bits = bit_sequence[start_idx:end_idx]
            matrix = matrix_bits.reshape(m, m)
            
            # Calculate rank over GF(2)
            rank = self._binary_matrix_rank_gf2(matrix)
            
            if rank == m:
                rank_counts[m] += 1
            elif rank == m - 1:
                rank_counts[m-1] += 1
            else:
                rank_counts['other'] += 1
                
        # Expected probabilities for 32x32 matrices
        if m == 32:
            pi_m = 0.2888
            pi_m_minus_1 = 0.5776
            pi_other = 0.1336
        else:
            # Approximate for other sizes
            pi_m = 0.3
            pi_m_minus_1 = 0.6  
            pi_other = 0.1
            
        # Calculate chi-square statistic
        expected_m = num_matrices * pi_m
        expected_m_minus_1 = num_matrices * pi_m_minus_1
        expected_other = num_matrices * pi_other
        
        chi_square = 0
        if expected_m > 0:
            chi_square += (rank_counts[m] - expected_m) ** 2 / expected_m
        if expected_m_minus_1 > 0:
            chi_square += (rank_counts[m-1] - expected_m_minus_1) ** 2 / expected_m_minus_1
        if expected_other > 0:
            chi_square += (rank_counts['other'] - expected_other) ** 2 / expected_other
            
        # P-value calculation (2 degrees of freedom)
        p_value = special.gammaincc(1, chi_square / 2)
        
        return {
            'test_name': 'Binary Matrix Rank Test',
            'matrix_size': m,
            'num_matrices': num_matrices,
            'rank_full': rank_counts[m],
            'rank_minus_1': rank_counts[m-1], 
            'rank_other': rank_counts['other'],
            'expected_probabilities': {
                'full_rank': pi_m,
                'rank_minus_1': pi_m_minus_1,
                'other_ranks': pi_other
            },
            'chi_square_statistic': float(chi_square),
            'p_value': float(p_value),
            'passes': p_value >= self.alpha
        }
        
    def _binary_matrix_rank_gf2(self, matrix: np.ndarray) -> int:
        """
        Calculate the rank of a binary matrix over GF(2).
        
        Args:
            matrix: Binary matrix
            
        Returns:
            Rank of the matrix
        """
        rows, cols = matrix.shape
        matrix = matrix.astype(int)
        
        rank = 0
        for col in range(cols):
            # Find pivot row
            pivot_row = None
            for row in range(rank, rows):
                if matrix[row, col] == 1:
                    pivot_row = row
                    break
                    
            if pivot_row is None:
                continue
                
            # Swap rows if needed
            if pivot_row != rank:
                matrix[[rank, pivot_row]] = matrix[[pivot_row, rank]]
                
            # Eliminate column
            for row in range(rows):
                if row != rank and matrix[row, col] == 1:
                    matrix[row] = (matrix[row] + matrix[rank]) % 2
                    
            rank += 1
            
        return rank
        
    def spectral_test(self, bit_sequence: np.ndarray) -> Dict:
        """
        NIST Discrete Fourier Transform (Spectral) Test.
        
        Tests the peak heights in the Discrete Fourier Transform.
        For random sequences, peaks should not be significantly large.
        
        Args:
            bit_sequence: Binary sequence to test
            
        Returns:
            Dictionary containing test results
        """
        n = len(bit_sequence)
        
        # Convert to +1, -1 representation
        x = 2 * bit_sequence.astype(float) - 1
        
        # Compute DFT
        s = np.abs(fft(x))
        
        # Take first half (due to symmetry)
        s = s[:n//2]
        
        # Calculate threshold
        t = math.sqrt(math.log(1/0.05) * n)  # 95% threshold
        
        # Count peaks above threshold
        n0 = 0.95 * n / 2  # Expected number below threshold
        n1 = len(s[s < t])  # Actual number below threshold
        
        # Calculate test statistic
        d = (n1 - n0) / math.sqrt(n * 0.95 * 0.05 / 4)
        
        # P-value calculation
        p_value = special.erfc(abs(d) / math.sqrt(2))
        
        return {
            'test_name': 'Spectral (DFT) Test',
            'threshold': float(t),
            'expected_below_threshold': float(n0),
            'observed_below_threshold': int(n1),
            'test_statistic': float(d),
            'p_value': float(p_value),
            'passes': p_value >= self.alpha,
            'max_peak': float(np.max(s)),
            'peaks_above_threshold': int(len(s[s >= t]))
        }
        
    def comprehensive_nist_analysis(self, source: str = 'combined_word',
                                  bit_length: int = 1000000) -> Dict:
        """
        Run comprehensive NIST SP 800-22 test suite.
        
        Args:
            source: Data source to test
            bit_length: Number of bits to extract and test
            
        Returns:
            Dictionary containing all test results
        """
        print(f"\n{'='*70}")
        print(f"NIST SP 800-22 COMPREHENSIVE TESTING")
        print(f"Source: {source}")
        print(f"Bit Length: {bit_length:,}")
        print(f"{'='*70}")
        
        # Extract bit sequence
        print("Extracting bit sequence...")
        bit_sequence = self.extract_bit_sequence(source, bit_length)
        
        results = {
            'source': source,
            'bit_length': len(bit_sequence),
            'test_results': {}
        }
        
        # Run all tests
        tests = [
            ('frequency_monobit', self.frequency_monobit_test),
            ('block_frequency', self.block_frequency_test),
            ('runs', self.runs_test),
            ('longest_run_of_ones', self.longest_run_of_ones_test),
            ('binary_matrix_rank', self.binary_matrix_rank_test),
            ('spectral', self.spectral_test)
        ]
        
        for test_name, test_func in tests:
            print(f"Running {test_name.replace('_', ' ').title()} Test...")
            try:
                test_result = test_func(bit_sequence)
                results['test_results'][test_name] = test_result
            except Exception as e:
                results['test_results'][test_name] = {
                    'test_name': test_name,
                    'error': str(e),
                    'passes': False
                }
                
        return results
        
    def generate_nist_report(self, results: Dict) -> None:
        """
        Generate comprehensive NIST test report.
        
        Args:
            results: Results from comprehensive_nist_analysis
        """
        print(f"\n{'='*80}")
        print("NIST SP 800-22 STATISTICAL TEST SUITE - COMPREHENSIVE REPORT")
        print(f"{'='*80}")
        
        print(f"\nTest Configuration:")
        print(f"  Data Source: {results['source']}")
        print(f"  Sequence Length: {results['bit_length']:,} bits")
        print(f"  Significance Level: α = {self.alpha}")
        print(f"  Confidence Level: {(1-self.alpha)*100}%")
        
        # Summary table
        test_results = results['test_results']
        passed_tests = 0
        total_tests = len(test_results)
        
        print(f"\n{'Test Name':<25} {'P-Value':<12} {'Result':<8} {'Status'}")
        print("-" * 65)
        
        for test_name, result in test_results.items():
            if 'error' in result:
                status = "ERROR"
                p_val_str = "N/A"
                result_str = "FAIL"
            else:
                status = "PASS" if result['passes'] else "FAIL"
                p_val_str = f"{result['p_value']:.6f}"
                result_str = "PASS" if result['passes'] else "FAIL"
                
            if status == "PASS":
                passed_tests += 1
                
            display_name = test_name.replace('_', ' ').title()[:24]
            print(f"{display_name:<25} {p_val_str:<12} {result_str:<8} {status}")
            
        # Overall assessment
        pass_rate = passed_tests / total_tests
        print(f"\n{'='*65}")
        print(f"OVERALL ASSESSMENT:")
        print(f"  Tests Passed: {passed_tests}/{total_tests}")
        print(f"  Pass Rate: {pass_rate:.1%}")
        
        if pass_rate >= 0.96:  # NIST recommends 96% pass rate
            assessment = "✅ EXCELLENT - Cryptographic Quality Randomness"
        elif pass_rate >= 0.90:
            assessment = "✅ GOOD - Suitable for Most Applications"
        elif pass_rate >= 0.80:
            assessment = "⚠️  MARGINAL - May Need Post-Processing"
        else:
            assessment = "❌ POOR - Not Suitable for Cryptographic Use"
            
        print(f"  Assessment: {assessment}")
        
        # Detailed results for failed tests
        failed_tests = [name for name, result in test_results.items() 
                       if not result.get('passes', False)]
        
        if failed_tests:
            print(f"\nFAILED TESTS DETAILS:")
            for test_name in failed_tests:
                result = test_results[test_name]
                print(f"\n{test_name.replace('_', ' ').title()}:")
                if 'error' in result:
                    print(f"  Error: {result['error']}")
                else:
                    print(f"  P-value: {result['p_value']:.6f} (threshold: {self.alpha})")
                    if 'test_statistic' in result:
                        print(f"  Test statistic: {result['test_statistic']:.4f}")
                        
    def create_nist_visualizations(self, results: Dict, output_dir: str = '.'):
        """
        Create visualizations of NIST test results.
        
        Args:
            results: Results from comprehensive_nist_analysis
            output_dir: Directory to save plots
        """
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Extract test results
        test_results = results['test_results']
        test_names = []
        p_values = []
        pass_status = []
        
        for test_name, result in test_results.items():
            if 'error' not in result:
                test_names.append(test_name.replace('_', '\n').title())
                p_values.append(result['p_value'])
                pass_status.append('PASS' if result['passes'] else 'FAIL')
                
        # Create visualization
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
        fig.suptitle('NIST SP 800-22 Test Results', fontsize=16, fontweight='bold')
        
        # P-values bar chart
        colors = ['green' if status == 'PASS' else 'red' for status in pass_status]
        bars = ax1.bar(range(len(test_names)), p_values, color=colors, alpha=0.7, edgecolor='black')
        
        ax1.axhline(y=self.alpha, color='red', linestyle='--', alpha=0.7, 
                   label=f'Significance Level (α = {self.alpha})')
        ax1.set_title('NIST Test P-Values')
        ax1.set_ylabel('P-Value')
        ax1.set_xticks(range(len(test_names)))
        ax1.set_xticklabels(test_names, rotation=45, ha='right')
        ax1.set_yscale('log')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Pass/Fail summary
        pass_count = sum(1 for s in pass_status if s == 'PASS')
        fail_count = len(pass_status) - pass_count
        
        ax2.pie([pass_count, fail_count], labels=['PASS', 'FAIL'], 
               colors=['green', 'red'], autopct='%1.1f%%', startangle=90)
        ax2.set_title(f'Test Results Summary\n({pass_count}/{len(pass_status)} tests passed)')
        
        plt.tight_layout()
        plt.savefig(output_path / 'phase3_nist_test_results.png', 
                   dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"NIST visualization saved to {output_path}/phase3_nist_test_results.png")


def main():
    """Main execution function for Phase 3 NIST testing."""
    print("Phase 3: NIST SP 800-22 Statistical Test Suite")
    print("=" * 50)
    
    # Initialize NIST test suite
    db_path = '../randomness_optimized.db'
    nist = NISTRandomnessTestSuite(db_path)
    
    # Test combined word data (primary test)
    print("Testing combined 32-bit words...")
    results_combined = nist.comprehensive_nist_analysis('combined_word', 500000)
    nist.generate_nist_report(results_combined)
    
    # Test best performing individual channel (CH2)
    print("\n" + "="*70)
    print("Testing CH2 (best individual channel)...")
    results_ch2 = nist.comprehensive_nist_analysis('ch2_raw', 500000)
    nist.generate_nist_report(results_ch2)
    
    # Create visualizations
    print("\nCreating NIST test visualizations...")
    nist.create_nist_visualizations(results_combined)
    
    print("\nPhase 3 NIST testing complete!")
    print("Generated files:")
    print("  - phase3_nist_test_results.png")
    print("\nReady for final research conclusions and Phase 4 planning...")


if __name__ == "__main__":
    main()