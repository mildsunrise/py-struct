from typing import Annotated, Any, BinaryIO, Callable, NamedTuple, get_args, get_origin, get_type_hints
import struct

__all__ = [
    'U8', 'U16', 'U32', 'U64', 'S8', 'S16', 'S32', 'S64', 'F32', 'F64',
    'serialized_struct', 'FixedSize',
]

# PRIMITIVE TYPES

class __PrimitiveField(NamedTuple):
    fmt: str

U8 = Annotated[int, __PrimitiveField('B')]
U16 = Annotated[int, __PrimitiveField('H')]
U32 = Annotated[int, __PrimitiveField('I')]
U64 = Annotated[int, __PrimitiveField('Q')]
S8 = Annotated[int, __PrimitiveField('b')]
S16 = Annotated[int, __PrimitiveField('h')]
S32 = Annotated[int, __PrimitiveField('i')]
S64 = Annotated[int, __PrimitiveField('q')]
F32 = Annotated[float, __PrimitiveField('f')]
F64 = Annotated[float, __PrimitiveField('d')]

# CORE PARSING

is_serializer = lambda cls: hasattr(cls, '__load__') and hasattr(cls, '__save__') and hasattr(cls, '__size__')

def serialized_struct(cls):
    hints = cls.__dict__.get('__annotations__', {})
    # hints = get_type_hints(cls, include_extras=True)
    hints = { k: parse_hint(v) for k, v in hints.items() }

    def __load__(st: BinaryIO):
        return cls(**{ k: t.__load__(st) for k, t in hints.items() })
    def __save__(self, st: BinaryIO):
        assert type(self) is cls
        for k, t in hints.items(): t.__save__(getattr(self, k), st)
    cls.__size__ = sum(t.__size__ for t in hints.values())
    cls.__load__ = __load__
    cls.__save__ = __save__
    return cls

class FixedSizeTupleSerializer(object):
    def __init__(self, base, size):
        self.base, self.size = base, size
        self.__size__ = self.base.__size__ * self.size
    def __load__(self, st: BinaryIO):
        return tuple(self.base.__load__(st) for _ in range(self.size))
    def __save__(self, x, st: BinaryIO):
        assert type(x) is tuple and len(x) == self.size
        for v in x: self.base.__save__(v, st)

class TupleSerializer(object):
    def __init__(self, args):
        self.args = args
        self.__size__ = sum(t.__size__ for t in self.args)
    def __load__(self, st: BinaryIO):
        return tuple(t.__load__(st) for t in self.args)
    def __save__(self, x, st: BinaryIO):
        assert type(x) is tuple and len(x) == len(self.args)
        for v, t in zip(x, self.args): t.__save__(v, st)

class FixedSizeBytesSerializer(object):
    def __init__(self, size: int):
        self.__size__ = size
    def __load__(self, st: BinaryIO):
        return st.read(self.__size__)
    def __save__(self, x, st: BinaryIO):
        assert type(x) is bytes and len(x) == self.__size__
        st.write(x)

class PrimitiveSerializer(object):
    def __init__(self, fmt: str):
        self.struct = struct.Struct(fmt)
        self.__size__ = self.struct.size
    def __load__(self, st: BinaryIO):
        return self.struct.unpack(st.read(self.__size__))[0]
    def __save__(self, x, st: BinaryIO):
        st.write(self.struct.pack(x))

class FixedSize(NamedTuple):
    size: int

# warning: you need to manage alignment yourself (FIXME: we could check for alignment, maybe)
# FIXME: we could optimize by bundling fields in Struct
def parse_hint(hint: Any) -> tuple[Callable[[BinaryIO], Any], Callable[[Any, BinaryIO], None]]:
    ''' Parses a type hint and returns a Serializer object for it '''
    metadata = []
    while get_origin(hint) is Annotated:
        hint, *__metadata = get_args(hint)
        metadata += __metadata
    find_metadata = lambda cls: next(filter(lambda x: isinstance(x, cls), metadata), None)

    # if class is already serializable, return it
    if is_serializer(hint): return hint

    if get_origin(hint) is tuple:
        if len(get_args(hint)) == 2 and get_args(hint)[1] is Ellipsis:
            base = get_args(hint)[0]
            if fixed_size := find_metadata(FixedSize):
                return FixedSizeTupleSerializer(parse_hint(base), fixed_size.size)
            raise Exception(f"I don't know how to handle variadic tuple of {base} ({metadata})")

        return TupleSerializer(list(map(parse_hint, get_args(hint))))

    if primitive := find_metadata(__PrimitiveField):
        return PrimitiveSerializer(primitive.fmt)

    if hint is bytes and (fixed_size := find_metadata(FixedSize)):
        return FixedSizeBytesSerializer(fixed_size.size)

    raise Exception(f"I don't know how to handle {hint} ({metadata})")
