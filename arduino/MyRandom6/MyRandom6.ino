/***************************************************************************
  Multi-Channel Random Walk Tracker with Two Modes
  
  MODE 1: Simple plotter output (4 random walk positions)
  MODE 2: Detailed datalog (walks, raw values, 32-bit LSB words)
  
  This version is optimized for speed in MODE 2 by removing unnecessary
  software delays.
***************************************************************************/

#include <ADS1115_WE.h>
#include <Wire.h>
#define I2C_ADDRESS 0x48
#define MODE 2  // Change to 1 for plotter, 2 for datalog

ADS1115_WE adc(I2C_ADDRESS);
ADS1115_MUX channels[] = {ADS1115_COMP_0_GND, ADS1115_COMP_1_GND, ADS1115_COMP_2_GND, ADS1115_COMP_3_GND};

// Arrays to track each channel separately
int32_t walkPosition[4] = {0, 0, 0, 0};  // Random walk position for each channel
uint32_t sampleCount[4] = {0, 0, 0, 0};  // Sample count for each channel
uint32_t onesCount[4] = {0, 0, 0, 0};    // Count of 1s for each channel

// For Mode 2: Single 32-bit word construction from all 4 channels
uint32_t combinedWord = 0;               // Single 32-bit word from all channels
int totalBits = 0;                       // Total bits collected (4 per cycle)
uint32_t totalCycles = 0;

void setup() {
  Wire.begin();
  // Set I2C clock to 400kHz for faster communication
  Wire.setClock(400000);
  Serial.begin(115200);
  if (!adc.init()) {
    Serial.println("ADS1115 not connected!");
  }
  adc.setVoltageRange_mV(ADS1115_RANGE_4096);
  adc.setMeasureMode(ADS1115_SINGLE);
  adc.setConvRate(ADS1115_860_SPS);
  
  if (MODE == 1) {
    // Simple header for Arduino plotter
    Serial.println("CH0_Walk CH1_Walk CH2_Walk CH3_Walk");
  } else if (MODE == 2) {
    // Detailed header for datalog
    Serial.println("# Cycle,CH0_Walk,CH1_Walk,CH2_Walk,CH3_Walk,CH0_Raw,CH1_Raw,CH2_Raw,CH3_Raw,Combined_32bit_Word");
  }
}

void loop() {
  int32_t  rawValues[4];
  
  // Loop through each of the four analog input channels
  for (int i = 0; i < 4; i++) {
    adc.setCompareChannels(channels[i]);
    adc.startSingleMeasurement();
    while (adc.isBusy()){}
    
    // Get the raw 16-bit result
    int32_t  rawResult = adc.getRawResult();
    rawValues[i] = rawResult;

    // Get the least significant bit (use unsigned for bit operations)
    uint8_t lsb = bitRead((uint32_t)rawResult, 0);

    // Update random walk for this channel
    sampleCount[i]++;
    if (lsb == 1) {
      walkPosition[i] += 1;  // Move up by 1
      onesCount[i]++;
    } else {
      walkPosition[i] -= 1;  // Move down by 1
    }
    
    // For Mode 2: Build single 32-bit word from all 4 channels
    if (MODE == 2) {
      // Add this channel's LSB to the combined word
      if (totalBits < 32) {
        if (totalBits == 0) {
          combinedWord = lsb;  // First bit
        } else {
          combinedWord = (combinedWord << 1) | lsb;  // Shift and add new bit
        }
        totalBits++;
      }
    }
  }
  
  totalCycles++;
  
  if (MODE == 1) {
    // Simple output for Arduino plotter - every cycle
    // Note: Delay is kept for plotter stability
    Serial.print(walkPosition[0]); Serial.print(" ");
    Serial.print(walkPosition[1]); Serial.print(" ");
    Serial.print(walkPosition[2]); Serial.print(" ");
    Serial.println(walkPosition[3]);
    delayMicroseconds(500);
    
  } else if (MODE == 2) {
    // Detailed datalog - output every 8 cycles when we have a complete 32-bit word
    // The delayMicroseconds(50) has been removed here for maximum speed.
    if (totalBits >= 32) {
      Serial.print(totalCycles); Serial.print(",");
      
      // Print walk positions
      for (int i = 0; i < 4; i++) {
        Serial.print(walkPosition[i]);
        Serial.print(",");
      }
      
      // Print raw ADC values
      for (int i = 0; i < 4; i++) {
        Serial.print(rawValues[i]);
        Serial.print(",");
      }
      
      // Print single combined 32-bit word and reset
      Serial.println(combinedWord);
      
      // Reset for next 32-bit word
      combinedWord = 0;
      totalBits = 0;
    }
  }
}

// The unused u2s() function has been removed.