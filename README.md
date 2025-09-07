# Hardware Randomness Generator

A hardware-based randomness generation system using Arduino and high-precision ADC for entropy collection and analysis.

## Overview

This project implements a complete hardware randomness generation pipeline consisting of:

- **Arduino firmware** (`arduino/MyRandom6.ino`) - Wemos D1 + ADS1115 ADC entropy collector
- **Python data logger** (`rndcap.py`) - Serial capture and SQLite storage system
- **Analysis tools** (`randomness_analysis/`) - Statistical testing and NIST validation

## Hardware Setup

- **Microcontroller**: Wemos D1 (ESP8266-based)
- **ADC**: ADS1115 4-channel 16-bit ADC (I2C address 0x48)
- **Entropy sources**: 4 analog noise channels feeding ADC inputs

## Quick Start

### Prerequisites

```bash
# Create and activate Python virtual environment
python -m venv venv.linux
source venv.linux/bin/activate  # Linux/WSL
# Install dependencies
pip install pyserial rich
```

### Running the Data Logger

```bash
# Activate virtual environment
source venv.linux/bin/activate

# Run with default settings (COM6, 115200 baud)
python rndcap.py

# Custom configuration
python rndcap.py --port /dev/ttyUSB0 --baud 115200 --batch-size 100
```

### Arduino Firmware

1. Open `arduino/MyRandom6.ino` in Arduino IDE
2. Set `MODE = 2` for data logging (line 14)
3. Upload to Wemos D1 board

## Data Flow

```
Analog Noise → ADS1115 ADC → Wemos D1 → Serial → Python Logger → SQLite DB
```

The system tracks random walk positions using LSB extraction from each ADC channel and constructs 32-bit words from channel combinations.

## Database Schema

- **timestamp**: Unix timestamp
- **cycle**: Arduino cycle counter  
- **ch0-3_walk**: Random walk positions per channel
- **ch0-3_raw**: Raw ADC values per channel
- **combined_word**: 32-bit word from channel LSBs

## Analysis Tools

- `phase1_data_exploration.py` - Data distribution analysis
- `phase2_statistical_tests.py` - Statistical randomness tests
- `phase3_nist_testing.py` - NIST SP 800-22 test suite

## Configuration

See `CLAUDE.md` for detailed development instructions and configuration options.

## License

MIT License - see LICENSE file for details.