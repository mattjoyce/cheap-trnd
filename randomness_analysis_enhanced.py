#!/usr/bin/env python3
"""
Hardware Randomness Analysis - Enhanced Comprehensive Statistical Analysis
Analyzes randomness quality from hardware randomness generators with flexible schema support
"""

import sqlite3
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from scipy.stats import kstest, chi2_contingency, jarque_bera
import warnings
import sys
import struct
import zlib
from collections import Counter
import os
import argparse
from datetime import datetime

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

class RandomnessAnalyzer:
    def __init__(self, db_path, table_name='randomness_data', column_mapping=None, max_rows=None, dry_run=False):
        self.db_path = db_path
        self.table_name = table_name
        self.max_rows = max_rows
        self.dry_run = dry_run
        self.data = None
        self.results = {}
        
        # Default column mapping
        self.column_mapping = {
            'timestamp': 'timestamp',
            'ch0': 'ch0_raw',
            'ch1': 'ch1_raw', 
            'ch2': 'ch2_raw',
            'ch3': 'ch3_raw',
            'combined_word': 'combined_word'
        }
        
        # Override with provided mapping
        if column_mapping:
            self.column_mapping.update(column_mapping)
            
    def detect_schema(self):
        """Detect and validate database schema"""
        print(f"Analyzing database schema: {self.db_path}")
        print(f"Table: {self.table_name}")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get table info
            cursor.execute(f"PRAGMA table_info({self.table_name})")
            columns = [row[1] for row in cursor.fetchall()]
            print(f"Available columns: {columns}")
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            total_rows = cursor.fetchone()[0]
            print(f"Total rows: {total_rows:,}")
            
            # Auto-detect column names if not explicitly provided
            detected_mapping = {}
            
            # Look for timestamp column
            for col in ['timestamp', 'time', 'ts']:
                if col in columns:
                    detected_mapping['timestamp'] = col
                    break
                    
            # Look for channel columns
            for i in range(4):
                for pattern in [f'ch{i}_raw', f'ch{i}_value', f'channel{i}', f'ch{i}']:
                    if pattern in columns:
                        detected_mapping[f'ch{i}'] = pattern
                        break
                        
            # Look for combined word column
            for col in ['combined_word', 'word', 'combined', 'result']:
                if col in columns:
                    detected_mapping['combined_word'] = col
                    break
                    
            # Update mapping with detected columns
            for key, value in detected_mapping.items():
                if key not in self.column_mapping or self.column_mapping[key] not in columns:
                    self.column_mapping[key] = value
                    
            print(f"Column mapping: {self.column_mapping}")
            
            # Validate required columns exist
            missing_columns = []
            for logical_name, physical_name in self.column_mapping.items():
                if physical_name not in columns:
                    missing_columns.append(f"{logical_name} -> {physical_name}")
                    
            if missing_columns:
                print(f"WARNING: Missing columns: {missing_columns}")
                return False
                
            conn.close()
            return True
            
        except Exception as e:
            print(f"Error analyzing schema: {e}")
            return False
            
    def load_data(self):
        """Load data from SQLite database with flexible schema support"""
        if not self.detect_schema():
            return False
            
        print(f"\nLoading data from {self.db_path}...")
        conn = sqlite3.connect(self.db_path)
        
        # Build query with flexible column names
        columns_to_select = [
            self.column_mapping['timestamp'],
            self.column_mapping['ch0'],
            self.column_mapping['ch1'], 
            self.column_mapping['ch2'],
            self.column_mapping['ch3'],
            self.column_mapping['combined_word']
        ]
        
        query = f"""
        SELECT {', '.join(columns_to_select)}
        FROM {self.table_name} 
        ORDER BY id
        """
        
        if self.max_rows:
            query += f" LIMIT {self.max_rows}"
            
        print(f"Query: {query}")
        
        if self.dry_run:
            print("DRY RUN: Would execute query above")
            conn.close()
            return True
            
        try:
            self.data = pd.read_sql_query(query, conn)
            
            # Rename columns to standard names for analysis
            rename_mapping = {
                self.column_mapping['timestamp']: 'timestamp',
                self.column_mapping['ch0']: 'ch0_raw',
                self.column_mapping['ch1']: 'ch1_raw',
                self.column_mapping['ch2']: 'ch2_raw', 
                self.column_mapping['ch3']: 'ch3_raw',
                self.column_mapping['combined_word']: 'combined_word'
            }
            self.data = self.data.rename(columns=rename_mapping)
            
            conn.close()
            
            print(f"Loaded {len(self.data)} records")
            if 'timestamp' in self.data.columns:
                print(f"Data spans from {datetime.fromtimestamp(self.data['timestamp'].min())} "
                      f"to {datetime.fromtimestamp(self.data['timestamp'].max())}")
            
            return True
            
        except Exception as e:
            print(f"Error loading data: {e}")
            conn.close()
            return False
        
    def basic_statistics(self):
        """Calculate basic statistical properties"""
        if self.dry_run:
            print("DRY RUN: Would calculate basic statistics")
            return
            
        print("\n" + "="*60)
        print("BASIC STATISTICS")
        print("="*60)
        
        stats_dict = {}
        
        # Combined word statistics
        combined_words = self.data['combined_word'].values
        stats_dict['combined_word'] = {
            'count': len(combined_words),
            'min': np.min(combined_words),
            'max': np.max(combined_words),
            'mean': np.mean(combined_words),
            'std': np.std(combined_words),
            'median': np.median(combined_words),
            'unique_values': len(np.unique(combined_words)),
            'theoretical_max': 2**32 - 1
        }
        
        print(f"Combined Word Analysis:")
        print(f"  Records: {stats_dict['combined_word']['count']:,}")
        print(f"  Range: {stats_dict['combined_word']['min']:,} to {stats_dict['combined_word']['max']:,}")
        print(f"  Theoretical Max: {stats_dict['combined_word']['theoretical_max']:,}")
        print(f"  Mean: {stats_dict['combined_word']['mean']:,.2f}")
        print(f"  Std Dev: {stats_dict['combined_word']['std']:,.2f}")
        print(f"  Unique Values: {stats_dict['combined_word']['unique_values']:,}")
        print(f"  Coverage: {stats_dict['combined_word']['unique_values']/stats_dict['combined_word']['count']*100:.2f}%")
        
        # Channel statistics
        for i in range(4):
            channel_name = f'ch{i}_raw'
            if channel_name in self.data.columns:
                channel_data = self.data[channel_name].values
                stats_dict[channel_name] = {
                    'min': np.min(channel_data),
                    'max': np.max(channel_data),
                    'mean': np.mean(channel_data),
                    'std': np.std(channel_data),
                    'range': np.max(channel_data) - np.min(channel_data),
                    'unique_values': len(np.unique(channel_data))
                }
            
        print(f"\nChannel Analysis:")
        for i in range(4):
            channel_name = f'ch{i}_raw'
            if channel_name in stats_dict:
                ch = stats_dict[channel_name]
                print(f"  CH{i}: Range={ch['range']}, Unique={ch['unique_values']}, "
                      f"Mean={ch['mean']:.1f}, Std={ch['std']:.3f}")
        
        self.results['basic_stats'] = stats_dict

    def frequency_analysis(self):
        """Analyze bit and byte frequency distributions"""
        if self.dry_run:
            print("DRY RUN: Would perform frequency analysis")
            return
            
        print("\n" + "="*60)
        print("FREQUENCY ANALYSIS")
        print("="*60)
        
        combined_words = self.data['combined_word'].values
        
        # Convert to bytes for analysis
        byte_data = []
        for word in combined_words:
            # Convert 32-bit word to 4 bytes
            byte_data.extend(struct.pack('>I', int(word)))
        
        byte_array = np.array(byte_data, dtype=np.uint8)
        
        # Bit frequency analysis
        total_bits = len(byte_array) * 8
        bit_count = np.unpackbits(byte_array)
        zeros = np.sum(bit_count == 0)
        ones = np.sum(bit_count == 1)
        
        print(f"Bit Frequency Analysis:")
        print(f"  Total bits analyzed: {total_bits:,}")
        print(f"  Bit 0 frequency: {zeros/total_bits:.6f} (expected: 0.5)")
        print(f"  Bit 1 frequency: {ones/total_bits:.6f} (expected: 0.5)")
        print(f"  Bias: {abs(0.5 - ones/total_bits):.6f}")
        
        # Byte frequency analysis
        byte_counts = Counter(byte_array)
        total_bytes = len(byte_array)
        expected_freq = total_bytes / 256
        
        print(f"\nByte Frequency Analysis:")
        print(f"  Total bytes: {total_bytes:,}")
        print(f"  Unique byte values: {len(byte_counts)}/256")
        print(f"  Expected frequency per byte: {expected_freq:.2f}")
        
        # Chi-square test for uniformity
        observed_frequencies = [byte_counts.get(i, 0) for i in range(256)]
        expected_frequencies = [expected_freq] * 256
        chi2_stat, p_value = stats.chisquare(observed_frequencies, expected_frequencies)
        
        print(f"  Chi-square test for uniformity:")
        print(f"    Chi-square statistic: {chi2_stat:.4f}")
        print(f"    p-value: {p_value:.6f}")
        print(f"    Uniform at α=0.05: {'PASS' if p_value > 0.05 else 'FAIL'}")
        
        self.results['frequency_analysis'] = {
            'total_bits': total_bits,
            'bit_0_freq': zeros/total_bits,
            'bit_1_freq': ones/total_bits,
            'bias': abs(0.5 - ones/total_bits),
            'total_bytes': total_bytes,
            'unique_bytes': len(byte_counts),
            'chi2_statistic': chi2_stat,
            'chi2_p_value': p_value
        }

    def runs_test(self):
        """Perform runs test for independence"""
        if self.dry_run:
            print("DRY RUN: Would perform runs test")
            return
            
        print("\n" + "="*60)
        print("RUNS TEST FOR INDEPENDENCE") 
        print("="*60)
        
        # Use LSB of combined words as binary sequence
        combined_words = self.data['combined_word'].values
        binary_sequence = combined_words % 2
        
        n = len(binary_sequence)
        n_zeros = np.sum(binary_sequence == 0)
        n_ones = np.sum(binary_sequence == 1)
        
        # Count runs
        runs = 1
        for i in range(1, n):
            if binary_sequence[i] != binary_sequence[i-1]:
                runs += 1
                
        # Expected runs and variance
        expected_runs = (2 * n_zeros * n_ones) / n + 1
        variance_runs = (2 * n_zeros * n_ones * (2 * n_zeros * n_ones - n)) / (n**2 * (n - 1))
        
        # Z-statistic
        z_statistic = (runs - expected_runs) / np.sqrt(variance_runs) if variance_runs > 0 else 0
        p_value = 2 * (1 - stats.norm.cdf(abs(z_statistic)))
        
        print(f"Runs Test Analysis:")
        print(f"  Sequence length: {n:,}")
        print(f"  Zeros: {n_zeros:,}, Ones: {n_ones:,}")
        print(f"  Observed runs: {runs:,}")
        print(f"  Expected runs: {expected_runs:.2f}")
        print(f"  Z-statistic: {z_statistic:.4f}")
        print(f"  p-value: {p_value:.6f}")
        print(f"  Independent at α=0.05: {'PASS' if p_value > 0.05 else 'FAIL'}")
        
        self.results['runs_test'] = {
            'sequence_length': n,
            'n_zeros': n_zeros,
            'n_ones': n_ones,
            'observed_runs': runs,
            'expected_runs': expected_runs,
            'z_statistic': z_statistic,
            'p_value': p_value
        }

    def generate_summary_report(self):
        """Generate comprehensive summary report"""
        if self.dry_run:
            print("DRY RUN: Would generate summary report")
            return
            
        print("\n" + "="*80)
        print("COMPREHENSIVE RANDOMNESS ANALYSIS REPORT")
        print("="*80)
        
        print(f"\nAnalysis conducted on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Database: {self.db_path}")
        print(f"Table: {self.table_name}")
        if hasattr(self, 'data') and self.data is not None:
            print(f"Total samples analyzed: {len(self.data):,}")

def parse_column_mapping(column_string):
    """Parse column mapping from command line argument"""
    if not column_string:
        return {}
        
    mapping = {}
    pairs = column_string.split(',')
    for pair in pairs:
        if '=' in pair:
            key, value = pair.split('=', 1)
            mapping[key.strip()] = value.strip()
        else:
            print(f"Warning: Invalid column mapping format: {pair}")
    return mapping

def main():
    parser = argparse.ArgumentParser(
        description='Hardware Randomness Analysis - Enhanced Comprehensive Statistical Analysis',
        epilog="""
Examples:
  %(prog)s --database randomness_sample.db
  %(prog)s --database data.db --table measurements --max-rows 50000
  %(prog)s --database data.db --columns "ch0=channel_0,ch1=channel_1,combined_word=result"
  %(prog)s --database data.db --dry-run
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Required arguments
    parser.add_argument('--database', '-d', required=True,
                       help='SQLite database file path')
    
    # Optional arguments  
    parser.add_argument('--table', '-t', default='randomness_data',
                       help='Table name to analyze (default: randomness_data)')
    
    parser.add_argument('--max-rows', '-m', type=int, 
                       help='Maximum number of rows to analyze (default: all rows)')
    
    parser.add_argument('--columns', '-c', type=str,
                       help='Column mapping as key=value pairs, comma-separated. '
                            'Keys: timestamp,ch0,ch1,ch2,ch3,combined_word')
    
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be analyzed without running full analysis')
    
    parser.add_argument('--output-prefix', '-o', default='analysis',
                       help='Prefix for output files (default: analysis)')
    
    args = parser.parse_args()
    
    # Validate database file exists
    if not os.path.exists(args.database):
        print(f"Error: Database file '{args.database}' not found")
        sys.exit(1)
    
    # Parse column mapping
    column_mapping = parse_column_mapping(args.columns)
    
    print("Hardware Randomness Analysis - Enhanced Version")
    print("=" * 50)
    print(f"Database: {args.database}")
    print(f"Table: {args.table}")
    print(f"Max rows: {args.max_rows or 'unlimited'}")
    print(f"Column mapping: {column_mapping or 'auto-detect'}")
    print(f"Dry run: {args.dry_run}")
    print(f"Output prefix: {args.output_prefix}")
    
    # Create analyzer
    analyzer = RandomnessAnalyzer(
        db_path=args.database,
        table_name=args.table, 
        column_mapping=column_mapping,
        max_rows=args.max_rows,
        dry_run=args.dry_run
    )
    
    # Run analysis
    try:
        if not analyzer.load_data():
            print("Failed to load data. Exiting.")
            sys.exit(1)
            
        if not args.dry_run:
            analyzer.basic_statistics()
            analyzer.frequency_analysis()
            analyzer.runs_test()
            analyzer.generate_summary_report()
        
        print(f"\nAnalysis complete!")
        
    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()