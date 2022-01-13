## py-struct

**Fixed-size struct serialization, using Python 3.9 annotated type hints**

This was originally uploaded as a Gist because it's not intended as a serious
project, but I decided to take it a bit further and add some features.

Features:
 - One file, zero dependencies
 - Easy to use, just annotate your fields and use the decorator
 - Overridable (just define `__load__`, `__save__`, `__size__`, `__align__`)
 - Compatible with dataclasses
 - Integer / float primitives
 - Fixed size arrays
 - Raw chunks (`bytes`)
 - Static checking / size calculation
 - Packed or aligned structs, with 3 padding handling modes


## Example

~~~ python
from .serialization import *
from io import BytesIO
from dataclasses import dataclass

# C ALIASES (for LP64)

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
~~~


## Wishlist

 - Bit fields
 - Post validation / transform (enums, booleans, string buffers, sets)
 - Endianness control
   - At annotation time, or at runtime?
 - Unions (? not clear how I'd implement those)
 - Optimization and laziness

Higher level:

 - Pointer newtype / wrapper class
   - Ideally annotated with target hint
   - Call to dereference, optionally passing index
