#!/usr/bin/env python3
"""
Randomness Data Logger
Captures serial data from Wemos D1 + ADS1115 randomness experiment
Stores data in SQLite database for long-term analysis
"""

try:
    import serial
except ImportError as e:
    print(f"Import error: {e}")
    print("Please install pyserial: pip install pyserial")
    exit(1)

import sqlite3
import time
import signal
import sys
import argparse
from datetime import datetime
import logging
from collections import deque

try:
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Rich not available. Install with: pip install rich")

class RandomnessLogger:
    def __init__(self, args):
        self.args = args
        self.ser = None
        self.conn = None
        self.running = True
        self.samples_logged = 0
        self.errors = 0
        self.start_time = time.time()
        
        # Batching for performance
        self.batch_size = args.batch_size
        self.pending_data = []
        
        # Stats tracking
        self.last_cycle = 0
        self.samples_per_second = 0
        self.recent_rates = deque(maxlen=10)
        
        # Rich console if available
        self.console = Console() if RICH_AVAILABLE else None
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, args.log_level.upper()),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(args.log_file),
                logging.StreamHandler() if not RICH_AVAILABLE else logging.NullHandler()
            ]
        )
        
    def setup_database(self):
        """Initialize SQLite database with proper schema"""
        try:
            self.conn = sqlite3.connect(self.args.database)
            cursor = self.conn.cursor()
            
            # Enable WAL mode for concurrent reads during writes
            cursor.execute('PRAGMA journal_mode=WAL')
            cursor.execute('PRAGMA synchronous=NORMAL')  # Faster writes with WAL
            cursor.execute('PRAGMA cache_size=10000')     # Larger cache for better performance
            cursor.execute('PRAGMA temp_store=memory')    # Use memory for temp tables
            
            # Create table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS randomness_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    cycle INTEGER,
                    ch0_walk INTEGER,
                    ch1_walk INTEGER,
                    ch2_walk INTEGER,
                    ch3_walk INTEGER,
                    ch0_raw INTEGER,
                    ch1_raw INTEGER,
                    ch2_raw INTEGER,
                    ch3_raw INTEGER,
                    combined_word INTEGER
                )
            ''')
            
            # Indexes for faster queries
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON randomness_data(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cycle ON randomness_data(cycle)')
            
            self.conn.commit()
            
            # Check WAL mode was enabled
            wal_result = cursor.execute('PRAGMA journal_mode').fetchone()[0]
            logging.info(f"Database initialized: {self.args.database} (Journal mode: {wal_result})")
            
        except Exception as e:
            logging.error(f"Database setup error: {e}")
            sys.exit(1)
    
    def setup_serial(self):
        """Initialize serial connection with retry logic"""
        for attempt in range(self.args.retry_attempts):
            try:
                if self.ser and self.ser.is_open:
                    self.ser.close()
                
                self.ser = serial.Serial(
                    self.args.port, 
                    self.args.baud, 
                    timeout=2,
                    xonxoff=False,
                    rtscts=False,
                    dsrdtr=False
                )
                
                time.sleep(1)
                if self.ser.is_open:
                    logging.info(f"Serial connected: {self.args.port}")
                    return True
                    
            except Exception as e:
                logging.warning(f"Serial connection attempt {attempt+1} failed: {e}")
                time.sleep(2)
        
        logging.error("Failed to establish serial connection")
        return False
    
    def parse_data_line(self, line):
        """Parse CSV line and return data tuple"""
        try:
            parts = line.strip().split(',')
            
            if len(parts) != 10 or parts[0].startswith('#'):
                return None
                
            timestamp = time.time()
            cycle = int(parts[0])
            ch0_walk = int(parts[1])
            ch1_walk = int(parts[2])
            ch2_walk = int(parts[3])
            ch3_walk = int(parts[4])
            ch0_raw = int(parts[5])
            ch1_raw = int(parts[6])
            ch2_raw = int(parts[7])
            ch3_raw = int(parts[8])
            combined_word = int(parts[9])
            
            return (timestamp, cycle, ch0_walk, ch1_walk, ch2_walk, ch3_walk,
                   ch0_raw, ch1_raw, ch2_raw, ch3_raw, combined_word)
                   
        except (ValueError, IndexError) as e:
            logging.warning(f"Failed to parse line: {line.strip()} - {e}")
            return None
    
    def batch_commit(self, force=False):
        """Commit pending data in batches"""
        if not self.pending_data or (len(self.pending_data) < self.batch_size and not force):
            return
            
        try:
            cursor = self.conn.cursor()
            cursor.executemany('''
                INSERT INTO randomness_data 
                (timestamp, cycle, ch0_walk, ch1_walk, ch2_walk, ch3_walk,
                 ch0_raw, ch1_raw, ch2_raw, ch3_raw, combined_word)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', self.pending_data)
            
            self.conn.commit()
            self.samples_logged += len(self.pending_data)
            self.pending_data.clear()
            
        except Exception as e:
            logging.error(f"Database batch insert error: {e}")
            self.errors += 1
    
    def create_stats_display(self):
        """Create Rich display layout"""
        if not RICH_AVAILABLE:
            return None
            
        layout = Layout()
        
        # Calculate stats
        runtime = time.time() - self.start_time
        avg_rate = self.samples_logged / runtime if runtime > 0 else 0
        
        # Create stats table
        table = Table(title="Randomness Logger Stats")
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Runtime", f"{runtime:.1f}s")
        table.add_row("Samples Logged", f"{self.samples_logged:,}")
        table.add_row("Pending Batch", f"{len(self.pending_data)}")
        table.add_row("Current Rate", f"{self.samples_per_second:.1f} samples/sec")
        table.add_row("Average Rate", f"{avg_rate:.1f} samples/sec")
        table.add_row("Last Cycle", f"{self.last_cycle:,}")
        table.add_row("Errors", f"{self.errors}")
        table.add_row("Batch Size", f"{self.batch_size}")
        
        return Panel(table, title="Live Statistics", border_style="blue")
    
    def run(self):
        """Main data collection loop"""
        logging.info("Starting randomness data logger...")
        
        # Setup
        self.setup_database()
        if not self.setup_serial():
            return
        
        last_status = time.time()
        last_rate_update = time.time()
        samples_at_last_update = 0
        
        if RICH_AVAILABLE:
            with Live(self.create_stats_display(), refresh_per_second=2) as live:
                self._data_loop(live, last_status, last_rate_update, samples_at_last_update)
        else:
            self._data_loop(None, last_status, last_rate_update, samples_at_last_update)
    
    def _data_loop(self, live, last_status, last_rate_update, samples_at_last_update):
        """Core data collection loop"""
        try:
            while self.running:
                try:
                    line = self.ser.readline().decode('utf-8', errors='ignore')
                    
                    if line:
                        data = self.parse_data_line(line)
                        if data:
                            self.pending_data.append(data)
                            self.last_cycle = data[1]  # cycle number
                            
                            # Batch commit when needed
                            self.batch_commit()
                    
                    current_time = time.time()
                    
                    # Update rate calculation
                    if current_time - last_rate_update >= 1.0:
                        samples_this_period = self.samples_logged - samples_at_last_update
                        self.samples_per_second = samples_this_period / (current_time - last_rate_update)
                        self.recent_rates.append(self.samples_per_second)
                        
                        last_rate_update = current_time
                        samples_at_last_update = self.samples_logged
                    
                    # Update display
                    if live and RICH_AVAILABLE:
                        live.update(self.create_stats_display())
                    
                    # Status logging (less frequent when using Rich)
                    if current_time - last_status > (300 if RICH_AVAILABLE else 60):
                        logging.info(f"Status: {self.samples_logged} samples logged, {self.errors} errors")
                        last_status = current_time
                        
                except serial.SerialException as e:
                    logging.error(f"Serial error: {e}")
                    self.errors += 1
                    time.sleep(5)
                    if not self.setup_serial():
                        break
                        
                except KeyboardInterrupt:
                    logging.info("Keyboard interrupt received")
                    break
                    
        finally:
            # Ensure all pending data is committed
            self.batch_commit(force=True)
            self.cleanup()
    
    def cleanup(self):
        """Clean shutdown"""
        runtime = time.time() - self.start_time
        avg_rate = self.samples_logged / runtime if runtime > 0 else 0
        
        logging.info(f"Shutting down. Runtime: {runtime:.1f}s")
        logging.info(f"Final stats: {self.samples_logged} samples, {avg_rate:.1f} samples/sec, {self.errors} errors")
        
        if self.ser:
            self.ser.close()
        if self.conn:
            self.conn.close()
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logging.info(f"Received signal {signum}")
        self.running = False

def main():
    parser = argparse.ArgumentParser(description='Randomness Data Logger')
    
    # Connection settings
    parser.add_argument('--port', default='COM6', 
                       help='Serial port (default: COM6)')
    parser.add_argument('--baud', type=int, default=115200,
                       help='Baud rate (default: 115200)')
    
    # Database settings  
    parser.add_argument('--database', default='randomness_data.db',
                       help='SQLite database file (default: randomness_data.db)')
    parser.add_argument('--batch-size', type=int, default=100,
                       help='Batch size for database commits (default: 100)')
    
    # Logging settings
    parser.add_argument('--log-file', default='randomness_logger.log',
                       help='Log file (default: randomness_logger.log)')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Log level (default: INFO)')
    
    # Connection retry
    parser.add_argument('--retry-attempts', type=int, default=10,
                       help='Serial connection retry attempts (default: 10)')
    
    args = parser.parse_args()
    
    # Create logger instance
    logger = RandomnessLogger(args)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, logger.signal_handler)
    signal.signal(signal.SIGTERM, logger.signal_handler)
    
    logger.run()

if __name__ == "__main__":
    main()