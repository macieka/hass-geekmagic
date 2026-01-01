"""ESPHome API Client for Geek Magic."""
import asyncio
import base64
import logging
from typing import Optional

import aioesphomeapi
from PIL import Image
import io

_LOGGER = logging.getLogger(__name__)


class GeekMagicESPHomeClient:
    """ESPHome API Client for Geek Magic display integration."""

    def __init__(self, host: str, port: int = 6053, password: Optional[str] = None) -> None:
        """Initialize the ESPHome API client.
        
        Args:
            host: The hostname or IP address of the ESPHome device
            port: The port number (default: 6053)
            password: Optional password for authentication
        """
        self._host = host
        self._port = port
        self._password = password
        self._client: Optional[aioesphomeapi.APIClient] = None
        self._connected = False

    async def connect(self) -> None:
        """Connect to the ESPHome device."""
        try:
            self._client = aioesphomeapi.APIClient(
                self._host,
                self._port,
                self._password or ""
            )
            await self._client.connect(login=True)
            self._connected = True
            _LOGGER.info("Connected to ESPHome device at %s:%s", self._host, self._port)
        except Exception as err:
            _LOGGER.error("Failed to connect to ESPHome device: %s", err)
            self._connected = False
            raise

    async def disconnect(self) -> None:
        """Disconnect from the ESPHome device."""
        if self._client and self._connected:
            try:
                await self._client.disconnect()
                self._connected = False
                _LOGGER.info("Disconnected from ESPHome device")
            except Exception as err:
                _LOGGER.error("Error disconnecting from ESPHome device: %s", err)
        self._client = None

    def _convert_to_rgb565(self, image_data: bytes) -> bytes:
        """Convert image data to RGB565 format.
        
        Args:
            image_data: Raw image bytes (JPEG, PNG, etc.)
            
        Returns:
            RGB565 encoded image data as bytes
        """
        # Open image and convert to RGB
        img = Image.open(io.BytesIO(image_data))
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        # Resize to 240x240 if needed
        if img.size != (240, 240):
            img = img.resize((240, 240), Image.Resampling.LANCZOS)
        
        # Convert to RGB565
        rgb565_data = bytearray()
        pixels = list(img.getdata())
        
        for r, g, b in pixels:
            # RGB565: 5 bits red, 6 bits green, 5 bits blue
            # Pack into 16 bits: RRRRR GGGGGG BBBBB
            rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            # Write as big endian (MSB first)
            rgb565_data.append((rgb565 >> 8) & 0xFF)
            rgb565_data.append(rgb565 & 0xFF)
        
        return bytes(rgb565_data)

    async def upload_image(self, image_data: bytes) -> None:
        """Upload image to display with RGB565 conversion and line-by-line streaming.
        
        Args:
            image_data: Raw image bytes (JPEG, PNG, etc.)
        """
        if not self._connected or not self._client:
            raise Exception("Not connected to ESPHome device")
        
        try:
            # Convert image to RGB565
            rgb565_data = self._convert_to_rgb565(image_data)
            
            # Stream line by line (240 pixels * 2 bytes per pixel = 480 bytes per line)
            line_size = 240 * 2  # 240 pixels, 2 bytes each (RGB565)
            num_lines = 240
            
            for line_num in range(num_lines):
                start_pos = line_num * line_size
                end_pos = start_pos + line_size
                line_data = rgb565_data[start_pos:end_pos]
                
                # Encode line as base64 for transmission
                line_base64 = base64.b64encode(line_data).decode('ascii')
                
                # Send line to display via custom service
                # Note: This assumes the ESPHome device has a custom service defined
                # to receive and display line data
                await self._client.execute_service(
                    service="display_image_line",
                    data={
                        "line_number": line_num,
                        "line_data": line_base64
                    }
                )
            
            _LOGGER.info("Successfully uploaded image to display")
            
        except Exception as err:
            _LOGGER.error("Error uploading image: %s", err)
            raise

    async def clear_display(self) -> None:
        """Clear the display."""
        if not self._connected or not self._client:
            raise Exception("Not connected to ESPHome device")
        
        try:
            # Call the clear_display service on the ESPHome device
            await self._client.execute_service(
                service="clear_display",
                data={}
            )
            _LOGGER.info("Display cleared successfully")
        except Exception as err:
            _LOGGER.error("Error clearing display: %s", err)
            raise

    async def set_brightness(self, value: int) -> None:
        """Set the backlight brightness.
        
        Args:
            value: Brightness value (0-100)
        """
        if not self._connected or not self._client:
            raise Exception("Not connected to ESPHome device")
        
        if not 0 <= value <= 100:
            raise ValueError("Brightness must be between 0 and 100")
        
        try:
            # Call the set_brightness service on the ESPHome device
            await self._client.execute_service(
                service="set_brightness",
                data={"brightness": value}
            )
            _LOGGER.info("Brightness set to %d", value)
        except Exception as err:
            _LOGGER.error("Error setting brightness: %s", err)
            raise
