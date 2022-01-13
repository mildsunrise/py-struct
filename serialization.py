from typing import ClassVar, Literal, Optional, Protocol, TypeVar, Annotated, Any, BinaryIO, NamedTuple, get_args, get_origin
import struct
from math import gcd, lcm

__all__ = [
    'FixedSerializable',
    'U8', 'U16', 'U32', 'U64', 'S8', 'S16', 'S32', 'S64', 'F32', 'F64',
    'Struct', 'FixedSize',
]

S = TypeVar('S', bound='FixedSerializable')

class FixedSerializable(Protocol):
    ''' Protocol class for things that can be serialized with a fixed size '''
    __size__: ClassVar[int]
    __align__: ClassVar[int]
    @classmethod
    def __load__(cls: type[S], st: BinaryIO) -> S: ...
    def __save__(self, st: BinaryIO) -> None: ...

is_serializable = lambda cls: hasattr(cls, '__load__') and hasattr(cls, '__save__') and hasattr(cls, '__size__')


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

class StructMeta(type):
    def __new__(cls, name, bases, namespace,
        align: Literal['no', 'discard', 'zeros', 'explicit']='discard', **kwds,
    ):
        assert align in {'no', 'discard', 'zeros', 'explicit'}

        hints = namespace.get('__annotations__', {})
        hints = [ (k, parse_hint(v)) for k, v in hints.items() ]

        def insert_padding(k: str, n: int):
            if align == 'no': return __size__, __align__
            if pad := (-__size__) % n:
                if align == 'explicit':
                    raise AssertionError(f'unannotated {pad} byte padding before [{n}]')
                fields.append(( None, Padding(pad, align) ))
            return __size__ + pad, lcm(__align__, n)

        fields = []; __size__ = 0; __align__ = 1
        for k, t in hints:
            __size__, __align__ = insert_padding(k, t.__align__)
            fields.append((k, t))
            __size__ += t.__size__
        __size__, __align__ = insert_padding('<end>', __align__)

        @classmethod
        def __load__(cls, st: BinaryIO):
            values = { k: t.__load__(st) for k, t in fields }
            del values[None]
            return cls(**values)
        def __save__(self, st: BinaryIO):
            assert type(self) is dcls
            for k, t in fields:
                t.__save__(getattr(self, k) if k != None else k, st)
        namespace['__align__'] = __align__
        namespace['__size__'] = __size__
        namespace['__load__'] = __load__
        namespace['__save__'] = __save__

        return (dcls := super().__new__(cls, name, bases, namespace, **kwds))

class Struct(metaclass=StructMeta):
    @classmethod
    def __size__(cls) -> int: ...
    @classmethod
    def __load__(cls: type[S], st: BinaryIO) -> S: ...
    def __save__(self, st: BinaryIO) -> None: ...

class Padding(object):
    __align__ = 1
    def __init__(self, size: int, mode: str):
        self.__size__ = size
        self.mode = mode
        self.contents = bytes([0]) * size
    def __load__(self, st: BinaryIO):
        got = st.read(self.__size__)
        if self.mode != 'discard':
            assert got == self.contents, 'incorrect padding'
    def __save__(self, x, st: BinaryIO):
        st.write(self.contents)

class FixedSizeTupleSerializer(object):
    def __init__(self, base: Any, size: int):
        self.base, self.size = base, size
        self.__size__ = self.base.__size__ * self.size
        self.__align__ = self.base.__align__
    def __load__(self, st: BinaryIO):
        return tuple(self.base.__load__(st) for _ in range(self.size))
    def __save__(self, x, st: BinaryIO):
        assert type(x) is tuple and len(x) == self.size
        for v in x: self.base.__save__(v, st)

class TupleSerializer(object):
    def __init__(self, args: list[Any]):
        self.args = args
        self.__size__ = sum(t.__size__ for t in self.args)
        self.__align__ = gcd(*(t.__align__ for t in self.args))
    def __load__(self, st: BinaryIO):
        return tuple(t.__load__(st) for t in self.args)
    def __save__(self, x, st: BinaryIO):
        assert type(x) is tuple and len(x) == len(self.args)
        for v, t in zip(x, self.args): t.__save__(v, st)

class FixedSizeBytesSerializer(object):
    __align__ = 1
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
        self.__size__ = self.__align__ = self.struct.size
    def __load__(self, st: BinaryIO):
        return self.struct.unpack(st.read(self.__size__))[0]
    def __save__(self, x, st: BinaryIO):
        st.write(self.struct.pack(x))

class FixedSize(NamedTuple):
    size: int

# warning: you need to manage alignment yourself (FIXME: we could check for alignment, maybe)
# FIXME: we could optimize by bundling fields in Struct
def parse_hint(hint: Any) -> Any:
    ''' Parses a type hint and returns a Serializer object for it '''
    metadata = []
    while get_origin(hint) is Annotated:
        hint, *__metadata = get_args(hint)
        metadata += __metadata
    find_metadata = lambda cls: next(filter(lambda x: isinstance(x, cls), metadata), None)

    # if class is already serializable, return it
    if is_serializable(hint): return hint

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
