# Hardware Randomness Analysis Plan
## Wemos D1 + ADS1115 Four-Channel Entropy Assessment

### Hardware Setup Overview
- **Device**: Wemos D1 (ESP8266) + ADS1115 4-channel 16-bit ADC
- **Channel Configuration**:
  - **A0, A1, A2**: Ground connections through different resistors (thermal noise sources)
  - **A3**: Dedicated noise circuit output (primary entropy source)
- **Data Collection**: ~32.5 hours continuous operation, ~860 SPS per channel
- **Dataset**: 1,357,528 records in `randomness_optimized.db`

### Data Structure
```sql
Schema: id, timestamp, cycle, ch0_raw, ch1_raw, ch2_raw, ch3_raw, combined_word
- ch0-ch3_raw: 16-bit signed ADC values from channels A0-A3
- combined_word: 32-bit word from channel LSBs
- Value ranges: ch0(-822,160), ch1(-377,162), ch2(-858,172), ch3(-2643,11305)
```

## Analysis Plan

### Phase 1: Data Exploration & Basic Statistics
1. **Channel Comparison**
   - Distribution analysis for each channel
   - Mean, variance, skewness, kurtosis per channel  
   - Identify which channels show best entropy characteristics
   - Compare thermal noise (A0-A2) vs dedicated circuit (A3)

2. **Temporal Analysis**
   - Check for time-based patterns or drift
   - Analyze correlation between consecutive samples
   - Look for periodic behaviors or environmental influences

### Phase 2: Individual Channel Randomness Assessment

#### Statistical Tests per Channel
1. **Chi-Square Goodness of Fit**
   - Test uniformity of LSB distributions
   - Test uniformity of raw value distributions

2. **Kolmogorov-Smirnov Test**
   - Compare against uniform and normal distributions
   - Assess distribution normality

3. **Runs Tests**
   - Test for independence in LSB sequences
   - Detect patterns in consecutive bits

4. **Serial Correlation**
   - Autocorrelation analysis at various lags
   - Cross-correlation between channels

### Phase 3: Combined Word Analysis

#### 32-bit Word Quality Assessment
1. **Bit-Level Uniformity**
   - Test each bit position for bias
   - Verify equal distribution of 0s and 1s

2. **Entropy Measurements**
   - Shannon entropy calculation
   - Min-entropy assessment
   - Compression ratio testing

3. **NIST SP 800-22 Test Suite**
   - Frequency (Monobit) Test
   - Block Frequency Test
   - Runs Test
   - Longest Run of Ones Test
   - Binary Matrix Rank Test
   - Discrete Fourier Transform Test
   - Non-overlapping Template Matching
   - Overlapping Template Matching
   - Maurer's Universal Statistical Test
   - Linear Complexity Test
   - Serial Test
   - Approximate Entropy Test
   - Cumulative Sums Test
   - Random Excursions Test
   - Random Excursions Variant Test

### Phase 4: Advanced Cryptographic Assessment

1. **Diehard Battery Tests**
   - Birthday spacings
   - Overlapping permutations
   - Ranks of matrices
   - Monkey tests
   - Count the 1s tests
   - Parking lot test
   - Minimum distance test
   - Random spheres test
   - Squeeze test
   - Overlapping sums test
   - Craps test

2. **TestU01 Components**
   - SmallCrush test battery
   - Selected tests from Crush battery
   - Spectral analysis

### Phase 5: Hardware-Specific Analysis

1. **Channel Performance Ranking**
   - Score each channel's randomness quality
   - Identify best performing entropy sources
   - Assess thermal noise vs circuit noise effectiveness

2. **LSB Extraction Validation**
   - Verify LSB extraction maintains entropy
   - Compare LSB randomness to full-word randomness
   - Test for correlation between channel LSBs

3. **Combined Word Construction Efficacy**
   - Analyze if 4-channel LSB combination improves randomness
   - Test for weakness in bit combination method
   - Recommend optimal extraction strategies

### Phase 6: Practical Applications Assessment

1. **Cryptographic Suitability**
   - Assess fitness for key generation
   - Evaluate for cryptographic nonce generation
   - Test resistance to prediction attacks

2. **Real-World Performance**
   - Calculate effective entropy rate (bits/second)
   - Assess post-processing requirements
   - Recommend conditioning algorithms if needed

### Phase 7: Reporting & Recommendations

#### Deliverables
1. **Channel Quality Report**
   - Ranking of A0-A3 performance
   - Thermal vs circuit noise comparison
   - Optimal channel selection recommendations

2. **System Performance Assessment**
   - Overall randomness quality score
   - Entropy rate calculations
   - Cryptographic fitness evaluation

3. **Improvement Recommendations**
   - Hardware modifications for better entropy
   - Software post-processing suggestions
   - Operational parameter optimization

#### Test Acceptance Criteria
- **NIST SP 800-22**: ≥142/150 tests pass (95% confidence)
- **Entropy**: >0.99 bits per bit for combined words
- **Bias**: <0.01 deviation from uniform distribution
- **Correlation**: <0.01 between independent samples

### Implementation Notes
- Use `./venv.linux` Python environment
- Install required packages: `numpy`, `scipy`, `matplotlib`, `cryptographic libraries`
- Process data in chunks to manage memory with 1.35M records
- Generate visualizations for all major findings
- Document all statistical test parameters and results
- Provide reproducible analysis scripts

This comprehensive analysis will definitively answer whether the Wemos D1 + ADS1115 setup produces cryptographically secure randomness and identify the optimal configuration for maximum entropy generation.