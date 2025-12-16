#!/usr/bin/env python3
"""
Weather Station Receiver
Raspberry Pi receiver for NRF24L01 weather station data
Forwards sensor data to OpenHAB via REST API
"""

import time
import json
import logging
import sys
from typing import Optional, Dict, Any
import requests
from RF24 import RF24, RF24_PA_MAX, RF24_250KBPS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('weather_station.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class WeatherStationReceiver:
    """Receiver for weather station sensor data via NRF24L01"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the receiver
        
        Args:
            config: Configuration dictionary with:
                - radio_ce_pin: CE pin for NRF24L01 (default: 22)
                - radio_csn_pin: CSN pin for NRF24L01 (default: 0)
                - radio_channel: Radio channel (default: 76)
                - openhab_url: OpenHAB REST API URL (default: http://localhost:8080)
                - openhab_items: Dictionary mapping sensor names to OpenHAB item names
        """
        self.config = config
        self.radio = RF24(config.get('radio_ce_pin', 22), config.get('radio_csn_pin', 0))
        self.openhab_url = config.get('openhab_url', 'http://localhost:8080')
        self.openhab_items = config.get('openhab_items', {
            'temp': 'WeatherStation_Temperature',
            'pressure': 'WeatherStation_Pressure',
            'altitude': 'WeatherStation_Altitude',
            'humidity': 'WeatherStation_Humidity',
            'wind_direction_deg': 'WeatherStation_WindDirection',
            'wind_speed': 'WeatherStation_WindSpeed'
        })
        
        # Sea level pressure for altitude calculation
        self.sea_level_pressure = config.get('sea_level_pressure', 1013.25)
        
        # Initialize radio
        if not self.radio.begin():
            raise RuntimeError("NRF24L01 hardware not responding!")
        
        # Configure radio
        self.radio.setChannel(config.get('radio_channel', 76))
        self.radio.setDataRate(RF24_250KBPS)
        self.radio.setPALevel(RF24_PA_MAX)
        
        # Set pipe address (must match transmitter)
        address = b"00001"
        self.radio.openReadingPipe(1, address)
        self.radio.startListening()
        
        logger.info("NRF24L01 initialized successfully")
        logger.info(f"Listening on channel {config.get('radio_channel', 76)}")
    
    def receive_data(self, timeout: float = 1.0) -> Optional[str]:
        """
        Receive data from NRF24L01
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            Received data string or None if timeout
        """
        if self.radio.available():
            # Read payload
            payload_size = self.radio.getDynamicPayloadSize()
            if payload_size > 0:
                buffer = bytearray(payload_size)
                self.radio.read(buffer, payload_size)
                try:
                    data = buffer.decode('utf-8')
                    logger.debug(f"Received data: {data}")
                    return data
                except UnicodeDecodeError:
                    logger.warning("Failed to decode received data")
                    return None
        return None
    
    def parse_sensor_data(self, data_str: str) -> Optional[Dict[str, Any]]:
        """
        Parse JSON sensor data
        
        Args:
            data_str: JSON string from transmitter
            
        Returns:
            Parsed sensor data dictionary or None if parsing fails
        """
        try:
            data = json.loads(data_str)
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON data: {e}")
            return None
    
    def calculate_pressure_hpa(self, pressure_pa: float) -> float:
        """
        Convert pressure from Pascals to hectopascals (hPa)
        
        Args:
            pressure_pa: Pressure in Pascals
            
        Returns:
            Pressure in hectopascals (hPa)
        """
        return pressure_pa / 100.0
    
    def calculate_altitude(self, pressure_hpa: float, sea_level_hpa: float = 1013.25) -> float:
        """
        Calculate altitude from pressure using the barometric formula
        
        Args:
            pressure_hpa: Current pressure in hPa
            sea_level_hpa: Sea level pressure in hPa (default: 1013.25)
            
        Returns:
            Altitude in meters
        """
        # Barometric formula: h = 44330 * (1 - (P/P0)^(1/5.255))
        return 44330.0 * (1.0 - pow(pressure_hpa / sea_level_hpa, 1.0 / 5.255))
    
    def calculate_wind_direction_deg(self, raw_angle: int) -> float:
        """
        Convert raw AS5600 angle to degrees
        
        Args:
            raw_angle: Raw angle value (0-4095)
            
        Returns:
            Wind direction in degrees (0-360)
        """
        return (raw_angle / 4096.0) * 360.0
    
    def process_sensor_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process raw sensor data to calculate derived values
        
        Args:
            raw_data: Dictionary with raw sensor values (temp, pressure, humidity, 
                     wind_direction, wind_speed)
            
        Returns:
            Dictionary with both raw and calculated values
        """
        processed_data = raw_data.copy()
        
        # Calculate pressure in hPa from Pascals
        if 'pressure' in raw_data and raw_data['pressure'] != -999.0:
            pressure_hpa = self.calculate_pressure_hpa(raw_data['pressure'])
            processed_data['pressure_hpa'] = pressure_hpa
            
            # Calculate altitude from pressure
            processed_data['altitude'] = self.calculate_altitude(
                pressure_hpa, 
                self.sea_level_pressure
            )
        
        # Calculate wind direction in degrees from raw angle
        if 'wind_direction' in raw_data:
            processed_data['wind_direction_deg'] = self.calculate_wind_direction_deg(
                raw_data['wind_direction']
            )
        
        # Wind speed is already calculated on Arduino side
        # No additional processing needed
        
        logger.debug(f"Processed data: {processed_data}")
        return processed_data
    
    def send_to_openhab(self, sensor_data: Dict[str, Any]) -> bool:
        """
        Send sensor data to OpenHAB via REST API
        
        Args:
            sensor_data: Dictionary containing sensor readings
            
        Returns:
            True if successful, False otherwise
        """
        success = True
        
        # Send each sensor value to its corresponding OpenHAB item
        for sensor_key, item_name in self.openhab_items.items():
            if sensor_key in sensor_data:
                value = sensor_data[sensor_key]
                
                # Skip error values
                if isinstance(value, float) and value == -999.0:
                    logger.warning(f"Skipping invalid {sensor_key} value")
                    continue
                
                # Send to OpenHAB REST API
                url = f"{self.openhab_url}/rest/items/{item_name}/state"
                try:
                    response = requests.put(url, data=str(value), timeout=5)
                    if response.status_code == 200:
                        logger.debug(f"Sent {sensor_key}={value} to {item_name}")
                    else:
                        logger.warning(
                            f"Failed to send {sensor_key} to OpenHAB: "
                            f"HTTP {response.status_code}"
                        )
                        success = False
                except requests.exceptions.RequestException as e:
                    logger.error(f"Error sending {sensor_key} to OpenHAB: {e}")
                    success = False
        
        return success
    
    def run(self):
        """Main receiver loop"""
        logger.info("Starting receiver loop...")
        
        try:
            while True:
                # Try to receive data
                data_str = self.receive_data(timeout=0.1)
                
                if data_str:
                    # Parse sensor data
                    sensor_data = self.parse_sensor_data(data_str)
                    
                    if sensor_data:
                        logger.info(f"Received raw sensor data: {sensor_data}")
                        
                        # Process raw data to calculate derived values
                        processed_data = self.process_sensor_data(sensor_data)
                        logger.info(f"Processed sensor data: {processed_data}")
                        
                        # Send processed data to OpenHAB
                        if self.send_to_openhab(processed_data):
                            logger.info("Data successfully sent to OpenHAB")
                        else:
                            logger.warning("Failed to send some data to OpenHAB")
                
                # Small delay to prevent CPU spinning
                time.sleep(0.01)
                
        except KeyboardInterrupt:
            logger.info("Receiver stopped by user")
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
        finally:
            self.radio.powerDown()
            logger.info("Radio powered down")


def load_config(config_path: str = 'config.json') -> Dict[str, Any]:
    """
    Load configuration from JSON file
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Config file {config_path} not found, using defaults")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}")
        return {}


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Weather Station Receiver')
    parser.add_argument(
        '--config',
        default='config.json',
        help='Path to configuration file (default: config.json)'
    )
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Create and run receiver
    try:
        receiver = WeatherStationReceiver(config)
        receiver.run()
    except Exception as e:
        logger.error(f"Failed to start receiver: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()










