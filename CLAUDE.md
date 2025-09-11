# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a hardware randomness generation and data logging project consisting of:

1. **Arduino firmware** (`MyRandom6/MyRandom6.ino`) - Wemos D1 + ADS1115 ADC randomness generator
2. **Python data logger** (`rndcap.py`) - Serial data capture and SQLite storage system
3. **SQLite database** (`randomness_data.db`) - Time-series storage of randomness measurements

## Development Environment

- **Python Virtual Environment**: Always use `./venv/` for Python development
- **Required Python packages**: Available via pip freeze (includes pyserial, rich, sqlite3)
- **Hardware**: Wemos D1 microcontroller with ADS1115 4-channel 16-bit ADC

## Common Development Commands

### Python Data Logger
```bash
# Activate virtual environment (required for all Python work)
source venv/Scripts/activate  # Windows WSL2
# or
source venv/bin/activate      # Linux/Mac

# Run data logger with default settings
python rndcap.py

# Run with custom settings
python rndcap.py --port COM6 --baud 115200 --batch-size 100 --database randomness_data.db

# View all options
python rndcap.py --help
```

### Arduino Development
- Use Arduino IDE or PlatformIO to compile and upload `MyRandom6/MyRandom6.ino`
- Change `MODE` constant (line 14): 1 for plotter output, 2 for detailed datalog
- Target: Wemos D1 (ESP8266-based)

### Database Operations
```bash
# Check database status
sqlite3 randomness_data.db ".schema"
sqlite3 randomness_data.db "SELECT COUNT(*) FROM randomness_data;"

# View recent samples
sqlite3 randomness_data.db "SELECT * FROM randomness_data ORDER BY id DESC LIMIT 10;"
```

## Architecture

### Hardware Data Flow
```
4x Analog Noise Sources → ADS1115 ADC (4 channels) → Wemos D1 → USB Serial → Python Logger → SQLite DB
```

### Arduino Firmware (`MyRandom6.ino`)
- **Core functionality**: Multi-channel random walk tracking using ADC LSB extraction
- **Two modes**: 
  - Mode 1: Simple plotter output (4 walk positions)
  - Mode 2: Detailed datalog (walks, raw values, 32-bit words)
- **Key components**:
  - ADS1115 4-channel 16-bit ADC interface
  - Random walk position tracking per channel
  - LSB extraction for randomness
  - 32-bit word construction from channel LSBs

### Python Data Logger (`rndcap.py`)
- **Core class**: `RandomnessLogger` - handles serial communication and data storage
- **Key features**:
  - Serial data parsing and validation
  - Batched database writes for performance
  - SQLite with WAL mode for concurrent access
  - Rich terminal UI with live statistics
  - Graceful shutdown with signal handling
  - Comprehensive logging and error handling

### Database Schema
```sql
randomness_data:
  - id: Primary key
  - timestamp: Unix timestamp
  - cycle: Arduino cycle counter
  - ch0_walk, ch1_walk, ch2_walk, ch3_walk: Random walk positions
  - ch0_raw, ch1_raw, ch2_raw, ch3_raw: Raw ADC values
  - combined_word: 32-bit word from channel LSBs
```

## Key Configuration Options

### Arduino Firmware
- `MODE`: 1 (plotter) or 2 (datalog)
- `I2C_ADDRESS`: ADS1115 address (default: 0x48)
- ADC settings: 4096mV range, 860 SPS, single-shot mode

### Python Logger
- `--port`: Serial port (default: COM6)
- `--baud`: Baud rate (default: 115200)
- `--batch-size`: Database commit batch size (default: 100)
- `--database`: SQLite database file (default: randomness_data.db)
- `--log-level`: Logging verbosity (DEBUG/INFO/WARNING/ERROR)

## Data Flow and File Relationships

1. **Arduino** generates randomness data and outputs CSV via serial
2. **Python logger** captures serial data and stores in SQLite database
3. **Database files**: 
   - `randomness_data.db` - main database
   - `randomness_data.db-wal` - write-ahead log
   - `randomness_data.db-shm` - shared memory
4. **Log file**: `randomness_logger.log` - application logs

## Testing and Validation

- Monitor live statistics via Rich terminal interface when running data logger
- Check log files for connection issues or parsing errors
- Validate data integrity by examining recent database entries
- Test serial connection by running logger with `--log-level DEBUG`
- always use venv.linux