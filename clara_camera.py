"""Validate one ephemeral, bounded JPEG frame. Never write camera bytes to disk."""
import base64
import binascii
import re
import struct


def validate_frame(value):
    if value is None:
        return None
    if not isinstance(value,str) or len(value)>360000 or not re.fullmatch(r'data:image/jpeg;base64,[A-Za-z0-9+/=]+',value):
        raise ValueError('Provide one JPEG camera frame under 260 KB')
    try:
        raw=base64.b64decode(value.split(',',1)[1],validate=True)
    except (binascii.Error,ValueError):
        raise ValueError('Invalid JPEG camera frame') from None
    if len(raw)>260000 or not raw.startswith(b'\xff\xd8') or not raw.endswith(b'\xff\xd9'):
        raise ValueError('Invalid JPEG camera frame')
    offset=2
    while offset+4<len(raw):
        if raw[offset]!=255: break
        while offset<len(raw) and raw[offset]==255: offset+=1
        if offset>=len(raw): break
        marker=raw[offset];offset+=1
        if marker in (0xd8,0xd9) or 0xd0<=marker<=0xd7: continue
        if marker==0xda: break
        length=struct.unpack('>H',raw[offset:offset+2])[0]
        if length<2 or offset+length>len(raw): break
        if marker in (0xc0,0xc1,0xc2):
            if length<8: break
            height,width=struct.unpack('>HH',raw[offset+3:offset+7])
            if not 1<=width<=1280 or not 1<=height<=1280:
                raise ValueError('Camera frame must be at most 1280 pixels per side')
            return value
        offset+=length
    raise ValueError('Invalid JPEG camera dimensions')
