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
import struct
from typing import Optional, Dict, Any
import requests

# Use pyRF24 library (https://github.com/nRF24/pyRF24)
from pyrf24 import RF24, RF24_PA_MAX, RF24_250KBPS  # type: ignore

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

# Global flag to control agent debug logging (disabled by default)
_agent_debug_enabled = False


def agent_debug_log(hypothesis_id: str, location: str, message: str, data: Dict[str, Any]) -> None:
    """Append a single NDJSON debug log line for this debug session."""
    if not _agent_debug_enabled:
        return
    try:
        log_entry = {
            "sessionId": "debug-session",
            "runId": "pre-fix",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with open(r"debug.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry))
            f.write("\n")
    except Exception:
        # Never let debug logging break the main flow
        pass


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
    
    def receive_data(self, timeout: float = 1.0) -> Optional[bytes]:
        """
        Receive data from NRF24L01
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            Raw payload bytes or None if timeout
        """
        # #region agent log
        agent_debug_log("H1", "receiver.py:receive_data:entry", "receive_data called", {"timeout": timeout})
        # #endregion
        if self.radio.available():
            # #region agent log
            agent_debug_log("H1", "receiver.py:receive_data:available", "Radio has data available", {})
            # #endregion
            # Read payload
            payload_size = self.radio.getDynamicPayloadSize()
            # #region agent log
            agent_debug_log("H1", "receiver.py:receive_data:payload_size", "Got payload size", {"payload_size": payload_size, "type": str(type(payload_size))})
            # #endregion
            if payload_size > 0:
                # #region agent log
                agent_debug_log("H2", "receiver.py:receive_data:before_read", "Before read() call", {"payload_size": payload_size, "read_method": str(type(self.radio.read))})
                # #endregion
                buffer = bytearray(payload_size)
                # #region agent log
                agent_debug_log("H2", "receiver.py:receive_data:buffer_created", "Buffer created", {"buffer_len": len(buffer), "buffer_type": str(type(buffer))})
                # #endregion
                try:
                    # #region agent log
                    agent_debug_log("H3", "receiver.py:receive_data:read_attempt", "Attempting read with buffer", {"calling_with": "buffer, payload_size"})
                    # #endregion
                    self.radio.read(buffer, payload_size)
                    # #region agent log
                    agent_debug_log("H3", "receiver.py:receive_data:read_success", "Read succeeded with buffer method", {"buffer_after": buffer.hex()})
                    # #endregion
                except TypeError as e:
                    # #region agent log
                    agent_debug_log("H4", "receiver.py:receive_data:read_error", "Read failed with buffer method", {"error": str(e), "error_type": type(e).__name__})
                    # #endregion
                    # Try alternative API: read(length) -> bytearray
                    # #region agent log
                    agent_debug_log("H4", "receiver.py:receive_data:read_alt_attempt", "Trying read(length) API", {"payload_size": payload_size})
                    # #endregion
                    result = self.radio.read(payload_size)
                    # #region agent log
                    agent_debug_log("H4", "receiver.py:receive_data:read_alt_success", "Read succeeded with length-only API", {"result_type": str(type(result)), "result_len": len(result), "result_hex": result.hex()})
                    # #endregion
                    buffer = result
                data_bytes = bytes(buffer)
                # #region agent log
                agent_debug_log("H1", "receiver.py:receive_data:return", "Returning payload bytes", {"payload_size": len(data_bytes), "payload_hex": data_bytes.hex()})
                # #endregion
                logger.debug(f"Received {payload_size} bytes from RF24")
                return data_bytes
        # #region agent log
        agent_debug_log("H1", "receiver.py:receive_data:no_data", "No data available or payload_size <= 0", {"available": self.radio.available() if hasattr(self.radio, 'available') else 'N/A'})
        # #endregion
        return None
    
    def parse_sensor_data(self, data_bytes: bytes) -> Optional[Dict[str, Any]]:
        """
        Parse compact binary sensor data struct from NRF24L01
        
        Args:
            data_bytes: Raw bytes from transmitter
            
        Returns:
            Parsed sensor data dictionary or None if parsing fails
        """
        try:
            expected_size = struct.calcsize("<fffHf")
            if len(data_bytes) < expected_size:
                logger.error(
                    f"Received payload too short for SensorData struct: "
                    f"{len(data_bytes)} bytes (expected {expected_size})"
                )
                agent_debug_log(
                    hypothesis_id="H2",
                    location="receiver.py:parse_sensor_data",
                    message="Payload too short for binary struct",
                    data={"payload_size": len(data_bytes)},
                )
                return None

            temperature, pressure_pa, humidity, wind_direction_raw, wind_speed = struct.unpack(
                "<fffHf", data_bytes[:expected_size]
            )

            data: Dict[str, Any] = {
                "temp": float(temperature),
                "pressure": float(pressure_pa),
                "humidity": float(humidity),
                "wind_direction": int(wind_direction_raw),
                "wind_speed": float(wind_speed),
            }

            agent_debug_log(
                hypothesis_id="H2",
                location="receiver.py:parse_sensor_data",
                message="Parsed binary sensor data",
                data=data,
            )

            return data
        except struct.error as e:
            logger.error(f"Failed to unpack binary sensor data: {e}")
            agent_debug_log(
                hypothesis_id="H2",
                location="receiver.py:parse_sensor_data",
                message="Struct unpack failed",
                data={"error": str(e), "payload_hex": data_bytes.hex()},
            )
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
                    response = requests.put(
                        url, 
                        data=str(value), 
                        headers={'Content-Type': 'text/plain'}, 
                        timeout=5
                    )
                    if response.ok:  # Accepts any 2xx status code (200, 202, etc.)
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
                payload = self.receive_data(timeout=0.1)
                
                if payload:
                    # Parse sensor data
                    sensor_data = self.parse_sensor_data(payload)
                    
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
    global _agent_debug_enabled
    import argparse
    
    parser = argparse.ArgumentParser(description='Weather Station Receiver')
    parser.add_argument(
        '--config',
        default='config.json',
        help='Path to configuration file (default: config.json)'
    )
    parser.add_argument(
        '--debug-log',
        action='store_true',
        help='Enable agent debug logging to debug.log (disabled by default)'
    )
    args = parser.parse_args()
    
    # Set agent debug logging flag
    _agent_debug_enabled = args.debug_log
    if _agent_debug_enabled:
        logger.info("Agent debug logging enabled (writing to debug.log)")
    
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










