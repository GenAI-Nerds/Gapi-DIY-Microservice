import struct
import json

class GapiMicroServiceMessage:
    HEADER = b'\x14\x0A\x05\x11'  # Header with values 20, 10, 5, 17

    def __init__(self, json_data, bin_data=None):
        self.json_data = json_data
        self.bin_data = bin_data or b''

    def encode(self):
        json_bytes = self.json_data.encode('utf-8')
        json_len = len(json_bytes)
        encoded_message = GapiMicroServiceMessage.HEADER + struct.pack('<I', json_len) + json_bytes + self.bin_data
        return encoded_message

    @staticmethod
    def decode(byte_array):
        if byte_array[:4] != GapiMicroServiceMessage.HEADER:
            raise ValueError('Invalid header')

        json_len = struct.unpack('<I', byte_array[4:8])[0]
        json_data = byte_array[8:8+json_len].decode('utf-8')

        if len(byte_array) > 8 + json_len:
            bin_data = byte_array[8+json_len:]
        else:
            bin_data = b''

        return GapiMicroServiceMessage(json_data, bin_data)

    def to_dict(self):
        return {
            'header': list(GapiMicroServiceMessage.HEADER),
            'json_data': self.json_data,
            'bin_data': self.bin_data
        }
