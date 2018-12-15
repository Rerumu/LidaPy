import struct
import sutil


class OpMode:
	def __init__(
			self,
			name: str,
			a: str="OpArgN",
			b: str="OpArgN",
			c: str="OpArgN",
			o: str="iABC",
			cb=None):
		self.name: str = name
		self.a: str = a  # Modes
		self.b: str = b
		self.c: str = c
		self.o: str = o
		self.cmt = cb


class LuaKTypes:
	TNIL = 0
	TBOOLEAN = 1
	TNUMBER = 3
	TSTRING = 4


BITRK = 0x100

SIZE_C = 9
SIZE_B = 9
SIZE_Bx = SIZE_C + SIZE_B
SIZE_A = 8
SIZE_Ax = SIZE_Bx + SIZE_A
SIZE_OP = 6

POS_OP = 0
POS_A = POS_OP + SIZE_OP
POS_C = POS_A + SIZE_A
POS_B = POS_C + SIZE_C
POS_Bx = POS_C
POS_Ax = POS_A

MAXARG_Bx = ((1 << SIZE_Bx) - 1)
MAXARG_sBx = MAXARG_Bx >> 1


class Instruction:
	def __init__(self, val: int, dt: list):
		self.value: int = val
		opcode = self.val_op()

		if opcode < len(dt):
			self.data: OpMode = dt[opcode]

	def extract_bits(self, ln: int, off: int) -> int:
		return (self.value >> off) & ((1 << ln) - 1)

	def val_op(self) -> int:
		return self.extract_bits(SIZE_OP, POS_OP)

	def ext_a(self) -> int:
		return self.extract_bits(SIZE_A, POS_A)

	def ext_ax(self) -> int:
		return self.extract_bits(SIZE_Ax, POS_Ax)

	def ext_b(self) -> int:
		return self.extract_bits(SIZE_B, POS_B)

	def ext_bx(self) -> int:
		return self.extract_bits(SIZE_Bx, POS_Bx)

	def ext_sbx(self) -> int:
		return self.ext_bx() - MAXARG_sBx

	def ext_c(self) -> int:
		return self.extract_bits(SIZE_C, POS_C)

	def val_a(self) -> int:
		mdo = self.data.o
		if mdo == 'iX':
			res = self.value
		elif mdo == 'iAx':
			res = self.ext_ax()
		else:
			res = self.ext_a()

		return res

	def val_b(self) -> int:
		mdo = self.data.o
		if mdo == 'iABC':
			res = self.ext_b()
		elif mdo == 'iABx':
			res = self.ext_bx()
		elif mdo == 'iAsBx':
			res = self.ext_sbx()
		else:
			res = 0

		return res

	def val_c(self) -> int:
		if self.data.o == 'iABC':
			res = self.ext_c()
		else:
			res = 0

		return res


class TValue:
	def __init__(self):
		self.uid: str = None
		self.tt: int = 0
		self.vbool: bool = False
		self.vflt: float = 0.0
		self.vint: int = 0
		self.vstr: str = None

	def get_fmt(self) -> str:
		retvr: str = "nil"

		if self.tt != LuaKTypes.TNIL:
			if self.tt == LuaKTypes.TBOOLEAN:
				retvr = str(self.vbool).lower()
			elif self.tt == LuaKTypes.TNUMBER:
				retvr = str(self.vflt)
			elif self.tt == LuaKTypes.TSTRING:
				retvr = sutil.get_safe(self.vstr)

		return retvr

	@staticmethod
	def get_info() -> None:
		return None


class LocVar:
	def __init__(self):
		self.uid: str = None
		self.varname: str = None
		self.startpc: int = 0
		self.endpc: int = 0

	def get_fmt(self) -> str:
		return sutil.get_safe(self.varname)

	def get_info(self) -> str:
		return f"{self.startpc} {self.endpc}"


class Upvalue:
	def __init__(self):
		self.uid: str = None
		self.name: str = None
		self.idx: int = -1
		self.stack: int = -1

	def get_fmt(self) -> str:
		return sutil.get_safe(self.name)

	def get_info(self):
		if self.idx == -1 and self.stack == -1:
			return None
		else:
			return f"{self.idx} f{self.stack}"


class Proto:
	def __init__(self):
		# Internal tracking
		self.uid: str = None

		# Proto metadata
		self.nups = 0
		self.numparams = 0

		# Proto parts
		self.source: str = None
		self.linedefined: int = 0
		self.lastlinedefined: int = 0
		self.k: list = []
		self.code: list = []
		self.p: list = []
		self.lineinfo: list = []
		self.locvars: list = []
		self.upvalues: list = []

	@staticmethod
	def get_fmt():
		return "Func"


class LFunction:
	def __init__(self, bt: bytes):
		# Loading
		self.pos: int = 0
		self.proto: Proto = None
		self.bytecode: bytes = bt

		# Header
		self.version: int = 0
		self.format: int = 0
		self.endian: int = 0
		self.int: int = 0
		self.size_t: int = 0
		self.Instruction: int = 0
		self.lua_Number: int = 0
		self.lua_Integer: int = 0
		self.integral: int = 0

		# Readers
		self.read_int = None
		self.read_size_t = None
		self.read_Instruction = None
		self.read_lua_Number = None
		self.read_lua_Integer = None

	def a_reader(self, size: int, fmt: str):
		res = struct.unpack_from(fmt, self.bytecode, self.pos)
		self.pos += size
		return res[0]

	def q_reader(self, integral: bool, signed: bool, size: int):
		little: bool = self.endian != 0
		fmt: str = ''

		if little:
			fmt += '<'
		else:
			fmt += '>'

		if size == 4:
			fmt += 'i' if integral else 'f'
		elif size == 8:
			fmt += 'q' if integral else 'd'

		if not signed:
			fmt = fmt.upper()

		return lambda: self.a_reader(size, fmt)

	def read_byte(self) -> int:
		return self.a_reader(1, 'B')

	def read_string(self, ln: int) -> str:
		return self.a_reader(ln, str(ln) + 's').decode(sutil.ASCII_ISO)

	def set_readers(self):
		self.read_int = self.q_reader(True, True, self.int)
		self.read_size_t = self.q_reader(True, False, self.size_t)
		self.read_Instruction = self.q_reader(True, False, self.Instruction)
		self.read_lua_Number = self.q_reader(self.integral != 0, True, self.lua_Number)
		self.read_lua_Integer = self.q_reader(True, True, self.lua_Integer)

	def read_header(self):
		raise NotImplementedError()

	def read_proto(self) -> Proto:
		raise NotImplementedError()

	def read_function(self):
		self.pos: int = 0
		self.proto: Proto = None
		self.read_header()
		self.set_readers()
		self.proto = self.read_proto()

	def set_target(self, bt: bytes):
		self.__init__(bt)
