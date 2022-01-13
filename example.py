from .serialization import *
from io import BytesIO
from dataclasses import dataclass

# C ALIASES (for LP64)
# [note that you still need to handle alignment explicitely]

Bool = U8
Char = S8; UChar = U8
Short = S16; UShort = U16
Int = S32; UInt = U32
Long = S64; ULong = U64
IntPtr = S64; UIntPtr = U64
Ptr = Size = U64

# Define some structs

@dataclass
class Foo(Struct):
    yeet: Bool
    ping: Bool

@dataclass
class MyStruct(Struct):
    foo: Foo
    bar: UInt
    three_bazs: tuple[Long, Long, Long]

# Decode with __load__(), passing an IO

data = b'\x01\x00\x00\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x03\x00\x00\x00\x00\x00\x00\x00'
parsed = MyStruct.__load__(BytesIO(data))

assert parsed == MyStruct(foo=Foo(yeet=1, ping=0), bar=1280, three_bazs=(1, 2, 3))

# Encode back with __save__()

parsed.__save__(st := BytesIO())
assert data == st.getvalue()
