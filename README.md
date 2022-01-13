# py-struct

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


## Getting started

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

data = b'\x01\x00\x00\x00\x00\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x03\x00\x00\x00\x00\x00\x00\x00'
parsed = MyStruct.__load__(BytesIO(data))

assert parsed == MyStruct(foo=Foo(yeet=1, ping=0), bar=1280, three_bazs=(1, 2, 3))

# Encode back with __save__()

parsed.__save__(st := BytesIO())
assert data == st.getvalue()
~~~


## Usage

### Serializable protocol

A serializable class is one that implements the `FixedSerializable` protocol:

 - `__load__(cls, st: BinaryIO) -> cls`: class method that deserializes a readable binary stream into an instance
 - `__save__(self, st: BinaryIO)`: instance method that serializes the instance into a writeable binary stream
 - `__size__: int`: class attribute that indicates total serialized size
 - `__align__: int`: align factor (1 if no alignment)

`__size__` is expected to be a multiple of `__align__` i.e. it includes any trailing alignment as needed.

~~~ python
class Color(NamedTuple):
    r: int
    g: int
    b: int

    __size__ = 3
    __align__ = 1
    @classmethod
    def __load__(cls, st):
        return cls(*st.read(3))
    def __save__(self, st):
        st.write(bytes(self))
~~~

### Structs

Most times you'll just derive from `Struct`, which implements the serializable protocol for you, based on the property annotations of the class. As in C, fields are serialized in order of declaration.

~~~ python
@dataclass
class Color(Struct):
    r: U8
    g: U8
    b: U8
~~~

The implemented `__load__` will construct an instance of the class passsing in keyword arguments according to the property annotations. In this example, the class will be constructed like `Color(r=0, g=21, b=10)`. To avoid implementing the constructor and other methods yourself, Python's [`dataclass` decorator](https://docs.python.org/3/library/dataclasses.html) can be used.

For the annotated properties, the following types are allowed:
 - A class implementing the serializable protocol, such as another struct.
 - One of the provided integer / float primitives: `U8`, `S8`, `U16`, `S16`, `U32`, `S32`, `U64`, `S64`, `F32`, `F64`.
   These are aliases of `int` with custom metadata consumed by `Struct`.
 - `bytes`, `list[T]` or `tuple[T, ...]` (where `T` is itself an allowed type).
 - A `tuple` with allowed types as elements.
   However, it must be annotated with `FixedSize` metadata like so: `Annotated[list[U8], FixedSize(20)]`

`Struct` is a metaclass, so it must be the first parent. Inheritace (subclassing the struct class, or more parents in addition to `Struct`) is discouraged and will probably not work correctly.

### Alignment

`Struct` can automatically insert padding to align fields according to their `__align__` attribute (or for primitives, their size). In this case, the struct itself is aligned to the LCM of the field alignments (and its `__size__` is padded accordingly).

The `align` metaclass attribute controls how alignment is handled:

 - `discard` (default): When decoding, any bytes are accepted as padding (and discarded). When encoding, zeroes are inserted. (This is the only alignment mode that introduces malleability.)
 - `zeros`: Like `discard`, but only zeroes are accepted as padding when decoding.
 - `explicit`: Don't actually insert any padding, just check that all fields are aligned and that `__size__` is aligned too. This mode expects you to explicitly declare padding as (for example) `bytes`.
 - `no`: No alignment at all. Field alignments are ignored and `__align__` is set to 1. This is equivalent to a packed / unaligned struct.

For example, to create a packed struct:

~~~ python
@dataclass
class Address(Struct, align='no'):
    port: U16
    # without align='no', 2 bytes of padding would be inserted here
    host: U32
~~~

**Caveat:** `tuple` (last case in allowed types) will not verify or insert alignment between its elements. Its alignment will be the GCD of the alignments of its elements, and the size will be the sum of the sizes. This means `tuple[U64, U64]` will probably do what you want (align to 8 bytes), but `tuple[U64, U32]` will only align to 4 bytes. If you need alignment, use a nested Struct instead of a tuple.

### Malleability

Serialization is non-malleable (that is, there's a bijection between serialized and unserialized values) if all the following conditions are met:

 - Structs use an alignment setting other than the default `align='discard'`.

Of course, if serialization is implemented manually at some point, malleability has to be checked there as well.


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
 - Generics in struct classes
