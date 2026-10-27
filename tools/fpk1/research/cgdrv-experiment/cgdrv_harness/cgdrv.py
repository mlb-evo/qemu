"""Run the firmware's own Tegra Cg driver so a lift can be checked by recompiling it.

Every AR20 shader in the cluster ships as a compiled binary; no GLSL survives in any KZB.
That leaves the lifter with nothing to check itself against for the 242 of 335 binaries that
have no recovered source, which is exactly where the frame is still wrong. `libcgdrv.so` is
the compiler that produced those binaries, so compiling a candidate source and comparing the
result byte for byte turns "the lift looks plausible" into a decision.

The library is absent from the cluster image (libGLESv2 dlopens it by name and prints
"Can not load the compiler!"), so it is vendored from the MHI2 head unit — same Tegra driver
stack. It needs only libc, libm and ten NvOs entry points, all emulated here.

ABI, read out of CgDrv_Create / CgDrv_Compile / CgDrv_GetCgBin:

    void *handle = CgDrv_Create(void);
    int rc = CgDrv_Compile(handle, language, target, source, length, flags, opts);
    void CgDrv_GetCgBin(handle, uint32_t *binary, uint32_t *size);

    language 1 selects ["-ogles","-glslWerror","-inline","all","-ifcvt","all","-O3"],
    language 2 selects ["-unroll","none","-inline","all","-ifcvt","all"];
    target 1 = "ar20vp", target 2 = "ar20fp"; the entry point is "main"; `defines` is a
    pointer, not a flag word. rc is 0 on success; handle[0] is the error string, handle[1]
    the compile log and handle[2] the diagnostics.

Current state: the front end runs — it parses the source and reports diagnostics with
correct line numbers and identifiers — but code generation stops at semantic binding with
"unknown semantics COLOR/POSITION" and "cannot locate suitable resource to bind variable",
identically for both stages and both languages, so the profile's resource bindings are not
being established. Measured and ruled out: the profile name strings are looked up; the
compiler instance is created with exactly the production option vector; there is no file
I/O; the static profile registry in .rodata is never read; the default callback installed by
CgDrv_Create is the allocator, not a message sink. Note that seeing COLOR/POSITION go into
the symbol table proves only that they are interned as strings — that table is the string
interner, not a semantics registry.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True

from dataclasses import dataclass
import math
import struct
from pathlib import Path
from typing import Any, Callable, Mapping

from .paths import CGDRV_LIBRARY

IMAGE_BASE = 0x40000000
HEAP_BASE = 0x60000000
HEAP_SIZE = 1536 << 20
STACK_BASE = 0x50000000
STACK_SIZE = 16 << 20
TRAP_BASE = 0xD0000000
TRAP_SIZE = 0x1000
DATA_BASE = 0xD1000000
DATA_SIZE = 0x10000

LANGUAGE_OGLES = 1
TARGET_VERTEX = 1
TARGET_FRAGMENT = 2
TARGETS = {"vertex": TARGET_VERTEX, "fragment": TARGET_FRAGMENT}

GL_ENUM_NAMES = {
    0: "GL_ZERO",
    1: "GL_ONE",
    0x0300: "GL_SRC_COLOR",
    0x0301: "GL_ONE_MINUS_SRC_COLOR",
    0x0302: "GL_SRC_ALPHA",
    0x0303: "GL_ONE_MINUS_SRC_ALPHA",
    0x0304: "GL_DST_ALPHA",
    0x0305: "GL_ONE_MINUS_DST_ALPHA",
    0x0306: "GL_DST_COLOR",
    0x0307: "GL_ONE_MINUS_DST_COLOR",
    0x8006: "GL_FUNC_ADD",
    0x8007: "GL_MIN",
    0x8008: "GL_MAX",
    0x800A: "GL_FUNC_SUBTRACT",
    0x800B: "GL_FUNC_REVERSE_SUBTRACT",
}


class CgDrvError(RuntimeError):
    pass


def source_with_profile_blend(
    source: str,
    blend: Mapping[str, Any] | None,
) -> str:
    """Restore the NVIDIA blend pragma stored separately from recovered GLSL.

    The source cache keeps the shader body and observed blend metadata in separate
    fields. AR20 performs that blend in the fragment program, so recompiling only the
    body necessarily loses its final instruction group. Recombine both pieces before
    asking CgDrv for a byte-exact oracle result.

    CgDrv accepts a short form when RGB and alpha use the same equation and factors.
    Its long form carries independent RGB and alpha triples.
    """
    if blend is None or "#pragma profilepragma blendoperation" in source:
        return source
    rgb = (
        int(blend["equation_rgb"]),
        int(blend["source_rgb"]),
        int(blend["destination_rgb"]),
    )
    alpha = (
        int(blend["equation_alpha"]),
        int(blend["source_alpha"]),
        int(blend["destination_alpha"]),
    )
    values = rgb if rgb == alpha else rgb + alpha
    try:
        arguments = ", ".join(GL_ENUM_NAMES[value] for value in values)
    except KeyError as error:
        raise ValueError(
            f"unsupported Cg profile blend enum {error.args[0]:#x}"
        ) from error
    return (
        "#pragma profilepragma blendoperation("
        f"gl_FragColor, {arguments})\n"
        f"{source}"
    )


@dataclass
class CompileResult:
    ok: bool
    binary: bytes
    log: str
    error: str
    instructions: int
    diagnostics: str = ""

    @property
    def code(self) -> bytes:
        """The target instruction stream, without the Cg container around it.

        The container starts with the profile id and carries the code section's length at
        word 6 and its offset at word 7 — verified on both profiles: fragment 480+120=600,
        vertex 1088+80=1168, each equal to the total at word 2. This is the part that
        corresponds to what a shipped .nvbin embeds.
        """
        if len(self.binary) < 32:
            return b""
        total, length, offset = (
            struct.unpack_from("<I", self.binary, 8)[0],
            struct.unpack_from("<I", self.binary, 24)[0],
            struct.unpack_from("<I", self.binary, 28)[0],
        )
        if total != len(self.binary) or offset + length > len(self.binary):
            return b""
        return self.binary[offset : offset + length]

    def matches(self, shipped_stream: bytes) -> bool:
        """Does this compile reproduce a stream carved out of a shipped .nvbin?

        A shipped vertex stream carries an extra 8-byte header ahead of the instruction
        words; the fragment stream starts at "AR20-BIN" and is compared whole.
        """
        code = self.code
        if not code:
            return False
        if shipped_stream[:8] == b"AR20-BIN":
            return code == shipped_stream
        return code == shipped_stream[8:]


class _Elf:
    """Enough ELF to map a shared object and apply its relocations."""

    def __init__(self, path: Path):
        self.data = path.read_bytes()
        data = self.data
        phoff, = struct.unpack_from("<I", data, 28)
        phentsize, phnum = struct.unpack_from("<HH", data, 42)
        self.loads: list[tuple[int, int, int, int]] = []
        dynamic: tuple[int, int] | None = None
        for index in range(phnum):
            kind, off, vaddr, _pa, filesz, memsz, _fl, _al = struct.unpack_from(
                "<8I", data, phoff + index * phentsize
            )
            if kind == 1:
                self.loads.append((off, vaddr, filesz, memsz))
            elif kind == 2:
                dynamic = (off, filesz)
        if dynamic is None:
            raise CgDrvError("shared object has no dynamic segment")
        self.tags: dict[int, int] = {}
        off, size = dynamic
        for step in range(0, size, 8):
            tag, value = struct.unpack_from("<iI", data, off + step)
            if tag == 0:
                break
            self.tags.setdefault(tag, value)
        self.strtab = self._offset(self.tags[5])
        self.symtab = self._offset(self.tags[6])

    def _offset(self, vaddr: int) -> int | None:
        for off, va, filesz, _memsz in self.loads:
            if va <= vaddr < va + filesz:
                return off + (vaddr - va)
        return None

    def string(self, index: int) -> str:
        end = self.data.find(b"\0", self.strtab + index)
        return self.data[self.strtab + index : end].decode("latin-1")

    def symbols(self):
        _buckets, chains = struct.unpack_from(
            "<II", self.data, self._offset(self.tags[4])
        )
        for index in range(chains):
            name, value, size, _info, _other, shndx = struct.unpack_from(
                "<IIIBBH", self.data, self.symtab + index * 16
            )
            yield index, self.string(name), value, size, shndx

    def relocations(self):
        for addr_tag, size_tag in ((17, 18), (23, 2)):
            if addr_tag not in self.tags or size_tag not in self.tags:
                continue
            start = self._offset(self.tags[addr_tag])
            for step in range(0, self.tags[size_tag], 8):
                offset, info = struct.unpack_from("<II", self.data, start + step)
                yield offset, info >> 8, info & 0xFF


class CgDriver:
    """The Cg compiler running under Unicorn with a host-backed libc."""

    def __init__(
        self, library: Path = CGDRV_LIBRARY, recycle_after: int = 1
    ):
        try:
            from unicorn import Uc, UC_ARCH_ARM, UC_MODE_LITTLE_ENDIAN
        except ImportError as error:  # pragma: no cover - environment dependent
            raise CgDrvError(
                "unicorn is required to run the Cg driver"
            ) from error
        if not library.is_file():
            raise CgDrvError(f"Cg driver not vendored at {library}")
        self._library = library
        # Where the image gets mapped. A shared object carries link-time vaddrs from zero
        # and is rebased here; an ET_EXEC firmware image carries absolute ones and must be
        # mapped where it asks (see arm_oracle.ArmFunctionOracle, which sets this to 0).
        self.image_base = IMAGE_BASE
        self._compiles = 0
        # The emulated compiler is not reusable indefinitely. Measured on this corpus:
        # after roughly sixty compiles in one process it stops producing real code and
        # returns a 108-byte stub for every input, with `ok` true and zero diagnostics.
        # That silently turned healthy lifts into apparent no-ops and, before it was
        # found, made a corpus sweep report 61 shaders as "the lift lost the computation".
        # Booting a fresh emulator costs 0.14 s, so do it per compile and keep every
        # measurement independent of how many ran before it.
        self.recycle_after = recycle_after
        self._boot()

    def _boot(self) -> None:
        from unicorn import Uc, UC_ARCH_ARM, UC_MODE_LITTLE_ENDIAN

        self.elf = _Elf(self._library)
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_LITTLE_ENDIAN)
        self._enable_vfp()
        self._map()
        self._heap = HEAP_BASE
        self._allocations: dict[int, int] = {}
        self._free_blocks: list[tuple[int, int]] = []
        self._data = DATA_BASE
        self._files: dict[int, Any] = {}
        self.unimplemented: list[str] = []
        self.output: list[str] = []
        self._install_handlers()
        self._trap_imports()
        self._relocate()
        self.exports = {
            name: self.image_base + value
            for _i, name, value, _s, shndx in self.elf.symbols()
            if shndx and value
        }
        self._run_initialisers()
        self._compiles = 0

    def _run_initialisers(self) -> None:
        """Run DT_INIT_ARRAY before calling anything.

        The library caches imported data pointers and sets up its own globals in static
        constructors. Skipping them leaves those pointers null, which showed up as a read at
        address 0xbe — the character-class table indexed by '_' with a base of zero.
        """
        array = self.elf.tags.get(25)
        size = self.elf.tags.get(27, 0)
        self.initialisers = 0
        if not array or not size:
            return
        for step in range(0, size, 4):
            entry = self.read32(self.image_base + array + step)
            if entry in (0, 0xFFFFFFFF):
                continue
            self.call(
                self.image_base + entry
                if entry < max(self.image_base, 1)
                else entry
            )
            self.initialisers += 1

    def _enable_vfp(self) -> None:
        """Grant the coprocessor access the compiler's float code assumes.

        libcgdrv is built with hardware floating point; the first VFP load faults as an
        invalid instruction until cp10/cp11 are enabled in CPACR and FPEXC.EN is set.
        """
        from unicorn.arm_const import UC_ARM_REG_C1_C0_2, UC_ARM_REG_FPEXC

        self.uc.reg_write(UC_ARM_REG_C1_C0_2, 0xF00000)
        self.uc.reg_write(UC_ARM_REG_FPEXC, 0x40000000)

    # -- memory ---------------------------------------------------------

    def _map(self) -> None:
        span = max(va + memsz for _o, va, _f, memsz in self.elf.loads)
        self.uc.mem_map(
            self.image_base, (span + 0xFFFFF) & ~0xFFFFF
        )
        for off, va, filesz, _memsz in self.elf.loads:
            self.uc.mem_write(
                self.image_base + va, self.elf.data[off : off + filesz]
            )
        self.uc.mem_map(HEAP_BASE, HEAP_SIZE)
        self.uc.mem_map(STACK_BASE, STACK_SIZE)
        self.uc.mem_map(TRAP_BASE, TRAP_SIZE)
        self.uc.mem_map(DATA_BASE, DATA_SIZE)

    def malloc(self, size: int) -> int:
        """Bump allocator with reuse of freed blocks.

        The compiler grows its arena by doubling — 4 MB, 8, 16, up to half a gigabyte —
        freeing the previous one each round. Without reuse those retries stack up and
        exhaust the heap before the compile finishes.
        """
        size = max(int(size), 1)
        for index, (address, capacity) in enumerate(self._free_blocks):
            if capacity >= size:
                del self._free_blocks[index]
                self._allocations[address] = capacity
                return address
        pointer = self._heap
        self._heap = (self._heap + size + 15) & ~15
        if self._heap >= HEAP_BASE + HEAP_SIZE:
            raise CgDrvError("emulated heap exhausted")
        self._allocations[pointer] = size
        return pointer

    def free(self, address: int) -> None:
        size = self._allocations.pop(address, None)
        if size:
            self._free_blocks.append((address, size))

    def _static(self, payload: bytes) -> int:
        address = self._data
        self._data = (self._data + len(payload) + 15) & ~15
        self.uc.mem_write(address, payload)
        return address

    def read32(self, address: int) -> int:
        return struct.unpack("<I", self.uc.mem_read(address, 4))[0]

    def write32(self, address: int, value: int) -> None:
        self.uc.mem_write(address, struct.pack("<I", value & 0xFFFFFFFF))

    def cstring(self, address: int, limit: int = 1 << 20) -> str:
        """Read a NUL-terminated string without walking off the end of a mapping.

        Bulk reads are faster but a string near the end of a region makes them fault, and
        the exception surfaces from inside an import hook as an emulation error rather than
        as the bad pointer it is. Shrink the window at a fault instead.
        """
        from unicorn import UcError

        if not address:
            return ""
        out = bytearray()
        while len(out) < limit:
            chunk = b""
            for size in (64, 16, 4, 1):
                try:
                    chunk = bytes(self.uc.mem_read(address + len(out), size))
                    break
                except UcError:
                    continue
            if not chunk:
                break
            end = chunk.find(b"\0")
            if end >= 0:
                out += chunk[:end]
                break
            out += chunk
        return out.decode("latin-1")

    # -- imports --------------------------------------------------------

    def _trap_imports(self) -> None:
        from unicorn import UC_HOOK_CODE

        undefined = sorted(
            {
                name
                for _i, name, _v, _s, shndx in self.elf.symbols()
                if shndx == 0 and name
            }
        )
        self.import_slots: dict[str, int] = {}
        for index, name in enumerate(undefined):
            if name in self._data_symbols:
                self.import_slots[name] = self._data_symbols[name]
            else:
                self.import_slots[name] = TRAP_BASE + index * 4
        self._by_slot = {
            slot: name
            for name, slot in self.import_slots.items()
            if TRAP_BASE <= slot < TRAP_BASE + TRAP_SIZE
        }
        # Each slot holds a real `BX LR`. The hook below supplies the result, then the CPU
        # returns on its own: rewriting PC from inside a code hook does not end the current
        # basic block, so the core kept running through the rest of the page.
        self.uc.mem_write(
            TRAP_BASE, struct.pack("<I", 0xE12FFF1E) * (TRAP_SIZE // 4)
        )
        self.uc.hook_add(
            UC_HOOK_CODE,
            self._dispatch,
            begin=TRAP_BASE,
            end=TRAP_BASE + TRAP_SIZE - 1,
        )

    def _dispatch(self, uc, address, _size, _user) -> None:
        name = self._by_slot.get(address)
        if name is None:
            return
        handler = self.handlers.get(name)
        if handler is None:
            self.unimplemented.append(name)
            self.set_return(0)
        else:
            handler()

    def _relocate(self) -> None:
        values: dict[int, int] = {}
        for index, name, value, _size, shndx in self.elf.symbols():
            values[index] = (
                self.image_base + value
                if shndx
                else self.import_slots.get(name, 0)
            )
        for offset, symbol, kind in self.elf.relocations():
            where = self.image_base + offset
            if kind in (21, 22):
                self.write32(where, values.get(symbol, 0))
            elif kind == 23:
                self.write32(where, self.image_base + self.read32(where))
            elif kind == 2:
                self.write32(
                    where, values.get(symbol, 0) + self.read32(where)
                )

    # -- calling --------------------------------------------------------

    def arg(self, index: int) -> int:
        from unicorn.arm_const import (
            UC_ARM_REG_R0,
            UC_ARM_REG_R1,
            UC_ARM_REG_R2,
            UC_ARM_REG_R3,
            UC_ARM_REG_SP,
        )

        registers = (
            UC_ARM_REG_R0,
            UC_ARM_REG_R1,
            UC_ARM_REG_R2,
            UC_ARM_REG_R3,
        )
        if index < 4:
            return self.uc.reg_read(registers[index])
        sp = self.uc.reg_read(UC_ARM_REG_SP)
        return self.read32(sp + (index - 4) * 4)

    def set_return(self, value: int) -> None:
        from unicorn.arm_const import UC_ARM_REG_R0

        self.uc.reg_write(UC_ARM_REG_R0, int(value) & 0xFFFFFFFF)

    def call(self, address: int, *args: int, timeout: int = 0) -> int:
        from unicorn.arm_const import (
            UC_ARM_REG_LR,
            UC_ARM_REG_R0,
            UC_ARM_REG_R1,
            UC_ARM_REG_R2,
            UC_ARM_REG_R3,
            UC_ARM_REG_SP,
        )

        registers = (
            UC_ARM_REG_R0,
            UC_ARM_REG_R1,
            UC_ARM_REG_R2,
            UC_ARM_REG_R3,
        )
        sp = STACK_BASE + STACK_SIZE - 0x10000
        for index, value in enumerate(args[:4]):
            self.uc.reg_write(registers[index], int(value) & 0xFFFFFFFF)
        extra = args[4:]
        if extra:
            sp -= len(extra) * 4
            sp &= ~7
            for index, value in enumerate(extra):
                self.write32(sp + index * 4, int(value))
        self.uc.reg_write(UC_ARM_REG_SP, sp)
        stop = TRAP_BASE + TRAP_SIZE - 4
        self.uc.reg_write(UC_ARM_REG_LR, stop)
        self.uc.emu_start(address, stop, timeout=timeout)
        return self.uc.reg_read(UC_ARM_REG_R0)

    def _call_nested(self, address: int, *args: int) -> int:
        """Call back into the guest from inside an import handler.

        Used by qsort for the caller's comparison function. The whole register file has to
        be saved and restored: the outer emulation is suspended mid-instruction and resumes
        expecting its own state.
        """
        from unicorn.arm_const import (
            UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
            UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
            UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
            UC_ARM_REG_R12, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC,
            UC_ARM_REG_CPSR,
        )

        registers = (
            UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
            UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
            UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
            UC_ARM_REG_R12, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC,
            UC_ARM_REG_CPSR,
        )
        saved = [self.uc.reg_read(register) for register in registers]
        self._nesting = getattr(self, "_nesting", 0) + 1
        try:
            stack = STACK_BASE + STACK_SIZE - 0x20000 - self._nesting * 0x4000
            for index, value in enumerate(args[:4]):
                self.uc.reg_write(registers[index], int(value) & 0xFFFFFFFF)
            self.uc.reg_write(UC_ARM_REG_SP, stack)
            stop = TRAP_BASE + TRAP_SIZE - 4
            self.uc.reg_write(UC_ARM_REG_LR, stop)
            self.uc.emu_start(address, stop)
            result = self.uc.reg_read(UC_ARM_REG_R0)
        finally:
            self._nesting -= 1
            for register, value in zip(registers, saved):
                self.uc.reg_write(register, value)
        return result - 0x100000000 if result >= 0x80000000 else result

    # -- the compiler ---------------------------------------------------

    def compile(
        self,
        source: str,
        target: str = "fragment",
        language: int = LANGUAGE_OGLES,
    ) -> CompileResult:
        if target not in TARGETS:
            raise ValueError(f"target must be one of {sorted(TARGETS)}")
        if self._compiles >= self.recycle_after:
            self._boot()
        self._compiles += 1
        handle = self.call(self.exports["CgDrv_Create"])
        if not handle:
            raise CgDrvError("CgDrv_Create returned NULL")
        payload = source.encode("utf-8")
        text = self.malloc(len(payload) + 1)
        self.uc.mem_write(text, payload + b"\0")
        rc = self.call(
            self.exports["CgDrv_Compile"],
            handle,
            language,
            TARGETS[target],
            text,
            len(payload),
            0,
            0,
        )
        out_pointer = self.malloc(4)
        out_size = self.malloc(4)
        self.call(
            self.exports["CgDrv_GetCgBin"], handle, out_pointer, out_size
        )
        address = self.read32(out_pointer)
        size = self.read32(out_size)
        binary = (
            bytes(self.uc.mem_read(address, size)) if address and size else b""
        )
        instructions = 0
        if "CgDrv_NumInstructions" in self.exports:
            instructions = self.call(
                self.exports["CgDrv_NumInstructions"], handle
            )
        return CompileResult(
            ok=rc == 0 and bool(binary),
            binary=binary,
            log=self.cstring(self.read32(handle + 4)),
            error=self.cstring(self.read32(handle)),
            instructions=instructions,
            # handle[2] carries the line-numbered diagnostics. Without it a failed compile
            # reports nothing at all, which is useless when the input is a lift and the
            # diagnostic is the only description of what the lifter emitted wrongly.
            diagnostics=self.cstring(self.read32(handle + 8)),
        )

    # -- host-backed C library -----------------------------------------

    @property
    def _data_symbols(self) -> dict[str, int]:
        """Imports the compiler reads as data rather than calling.

        These are Dinkumware pointer variables, not the tables themselves: the code loads
        the symbol's address from the GOT and dereferences it once more. The character class
        table holds 16-bit entries and is indexed by a SIGN-EXTENDED byte, so the pointer
        has to sit far enough into the allocation for a negative index to stay inside it.
        """
        if getattr(self, "_data_symbol_cache", None) is None:
            _XD, _UP, _SP, _PU, _LO, _DI, _CN = (
                0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40
            )
            classes = []
            for value in range(256):
                char = chr(value)
                flags = 0
                if char in "0123456789":
                    flags |= _DI | _XD
                if char in "abcdef":
                    flags |= _XD
                if char in "ABCDEF":
                    flags |= _XD
                if "a" <= char <= "z":
                    flags |= _LO
                if "A" <= char <= "Z":
                    flags |= _UP
                if char in " \t\n\v\f\r":
                    flags |= _SP
                if value < 0x20 or value == 0x7F:
                    flags |= _CN
                if 0x21 <= value <= 0x7E and not (flags & (_DI | _LO | _UP)):
                    flags |= _PU
                classes.append(flags)
            bias = 128
            table = bytearray()
            for index in range(-bias, 256):
                table += struct.pack("<H", classes[index & 0xFF] if index >= 0 else 0)
            table_address = self._static(bytes(table)) + bias * 2

            def case_table(mapping) -> int:
                # Signed 16-bit entries, like _Ctype: the guest does `sxtb; lsl #1; ldrsh`,
                # i.e. int16_t table[signed_char]. Byte-wide entries made toupper() return
                # garbage, and the semantic binder uppercases a semantic name before
                # matching it against the profile's resource table — which is why every
                # semantic came back unknown.
                payload = bytearray()
                for index in range(-bias, 256):
                    payload += struct.pack(
                        "<h", mapping(index & 0xFF) if index >= 0 else 0
                    )
                return self._static(bytes(payload)) + bias * 2

            lower = case_table(
                lambda v: v + 0x20 if 0x41 <= v <= 0x5A else v
            )
            upper = case_table(
                lambda v: v - 0x20 if 0x61 <= v <= 0x7A else v
            )
            self._data_symbol_cache = {
                "_Ctype": self._static(struct.pack("<I", table_address)),
                "_Tolotab": self._static(struct.pack("<I", lower)),
                "_Touptab": self._static(struct.pack("<I", upper)),
                "_Stdin": self._static(b"\0" * 8),
                "_Stdout": self._static(b"\0" * 8),
                "_Stderr": self._static(b"\0" * 8),
                "_Multi_threaded": self._static(b"\0" * 4),
            }
        return self._data_symbol_cache

    def _install_handlers(self) -> None:
        self.handlers: dict[str, Callable[[], None]] = {}
        self._data_symbol_cache = None

        def register(*names: str):
            def decorate(function):
                for name in names:
                    self.handlers[name] = function
                return function

            return decorate

        @register("malloc", "valloc", "NvOsAlloc")
        def _malloc() -> None:
            self.set_return(self.malloc(self.arg(0)))

        # C++ allocation and the mutex calls the HMI's own routines make. Without these an
        # import returns 0, and `operator new` returning nullptr is what sent three statechart
        # actions wandering through 10,000 stores until the probe called them runaways. A
        # stub is a claim: these say allocation succeeds and a mutex initialises, which is
        # true of the device and touches no data point either way.
        @register("_Znwj", "_Znaj")
        def _operator_new() -> None:
            self.set_return(self.malloc(self.arg(0)))

        @register("_ZdlPv", "_ZdaPv")
        def _operator_delete() -> None:
            self.free(self.arg(0))
            self.set_return(0)

        @register(
            "pthread_mutexattr_init",
            "pthread_mutexattr_destroy",
            "pthread_mutexattr_setrecursive",
            "pthread_mutexattr_settype",
            "pthread_mutex_init",
            "pthread_mutex_destroy",
            "pthread_mutex_lock",
            "pthread_mutex_unlock",
            "pthread_mutex_trylock",
        )
        def _pthread_mutex() -> None:
            self.set_return(0)

        @register("NvOsFree")
        def _nvos_free() -> None:
            self.free(self.arg(0))
            self.set_return(0)

        @register("NvOsRealloc")
        def _nvos_realloc() -> None:
            old, size = self.arg(0), self.arg(1)
            pointer = self.malloc(size)
            if old and size:
                self.uc.mem_write(pointer, bytes(self.uc.mem_read(old, size)))
            self.set_return(pointer)

        @register("calloc")
        def _calloc() -> None:
            size = self.arg(0) * self.arg(1)
            pointer = self.malloc(size)
            if size:
                self.uc.mem_write(pointer, b"\0" * size)
            self.set_return(pointer)

        @register("realloc")
        def _realloc() -> None:
            old, size = self.arg(0), self.arg(1)
            pointer = self.malloc(size)
            if old and size:
                self.uc.mem_write(
                    pointer, bytes(self.uc.mem_read(old, size))
                )
            self.set_return(pointer)

        @register("free")
        def _free() -> None:
            self.free(self.arg(0))
            self.set_return(0)

        @register("memcpy", "memmove", "NvOsMemcpy")
        def _memcpy() -> None:
            dst, src, size = self.arg(0), self.arg(1), self.arg(2)
            if size:
                self.uc.mem_write(dst, bytes(self.uc.mem_read(src, size)))
            self.set_return(dst)

        @register("memset", "NvOsMemset")
        def _memset() -> None:
            dst, value, size = self.arg(0), self.arg(1), self.arg(2)
            if size:
                self.uc.mem_write(dst, bytes([value & 0xFF]) * size)
            self.set_return(dst)

        @register("memcmp")
        def _memcmp() -> None:
            a, b, size = self.arg(0), self.arg(1), self.arg(2)
            left = bytes(self.uc.mem_read(a, size)) if size else b""
            right = bytes(self.uc.mem_read(b, size)) if size else b""
            self.set_return(0 if left == right else (1 if left > right else -1))

        @register("strlen", "NvOsStrlen")
        def _strlen() -> None:
            self.set_return(len(self.cstring(self.arg(0))))

        @register("strcmp", "NvOsStrcmp")
        def _strcmp() -> None:
            left = self.cstring(self.arg(0))
            right = self.cstring(self.arg(1))
            self.set_return(0 if left == right else (1 if left > right else -1))

        @register("strncmp", "NvOsStrncmp")
        def _strncmp() -> None:
            size = self.arg(2)
            left = self.cstring(self.arg(0))[:size]
            right = self.cstring(self.arg(1))[:size]
            self.set_return(0 if left == right else (1 if left > right else -1))

        @register("strcpy")
        def _strcpy() -> None:
            dst, src = self.arg(0), self.arg(1)
            self.uc.mem_write(dst, self.cstring(src).encode("latin-1") + b"\0")
            self.set_return(dst)

        @register("strncpy", "NvOsStrncpy")
        def _strncpy() -> None:
            dst, src, size = self.arg(0), self.arg(1), self.arg(2)
            payload = self.cstring(src).encode("latin-1")[:size]
            payload += b"\0" * (size - len(payload))
            self.uc.mem_write(dst, payload)
            self.set_return(dst)

        @register("strcat")
        def _strcat() -> None:
            dst, src = self.arg(0), self.arg(1)
            existing = self.cstring(dst).encode("latin-1")
            self.uc.mem_write(
                dst + len(existing),
                self.cstring(src).encode("latin-1") + b"\0",
            )
            self.set_return(dst)

        @register("strchr")
        def _strchr() -> None:
            base, char = self.arg(0), self.arg(1) & 0xFF
            text = self.cstring(base).encode("latin-1")
            index = text.find(bytes([char]))
            self.set_return(base + index if index >= 0 else 0)

        @register("strrchr")
        def _strrchr() -> None:
            base, char = self.arg(0), self.arg(1) & 0xFF
            text = self.cstring(base).encode("latin-1")
            index = text.rfind(bytes([char]))
            self.set_return(base + index if index >= 0 else 0)

        @register("strstr", "NvUStrstr")
        def _strstr() -> None:
            base = self.arg(0)
            text = self.cstring(base)
            index = text.find(self.cstring(self.arg(1)))
            self.set_return(base + index if index >= 0 else 0)

        @register("strtol", "NvUStrtol", "atoi")
        def _strtol() -> None:
            text = self.cstring(self.arg(0)).strip()
            digits = ""
            for char in text:
                if char in "+-" and not digits:
                    digits += char
                elif char.isdigit():
                    digits += char
                else:
                    break
            self.set_return(int(digits) if digits.strip("+-") else 0)

        def _set_r1(value: int) -> None:
            from unicorn.arm_const import UC_ARM_REG_R1

            self.uc.reg_write(UC_ARM_REG_R1, int(value) & 0xFFFFFFFF)

        @register("__aeabi_idiv")
        def _idiv() -> None:
            a, b = self.arg(0), self.arg(1)
            a = a - 0x100000000 if a >= 0x80000000 else a
            b = b - 0x100000000 if b >= 0x80000000 else b
            self.set_return(0 if b == 0 else int(a / b))

        @register("__aeabi_idivmod")
        def _idivmod() -> None:
            # EABI returns the quotient in r0 and the REMAINDER IN R1. Setting only r0 left
            # every hash bucket index reading whatever r1 happened to hold, so the compiler's
            # symbol table never found a free slot and grew without bound.
            a, b = self.arg(0), self.arg(1)
            a = a - 0x100000000 if a >= 0x80000000 else a
            b = b - 0x100000000 if b >= 0x80000000 else b
            if b == 0:
                self.set_return(0)
                _set_r1(0)
                return
            quotient = int(a / b)
            self.set_return(quotient)
            _set_r1(a - quotient * b)

        @register("__aeabi_uidiv")
        def _uidiv() -> None:
            b = self.arg(1)
            self.set_return(0 if b == 0 else self.arg(0) // b)

        @register("__aeabi_uidivmod")
        def _uidivmod() -> None:
            a, b = self.arg(0), self.arg(1)
            if b == 0:
                self.set_return(0)
                _set_r1(0)
                return
            self.set_return(a // b)
            _set_r1(a % b)

        @register("_setjmp", "__sigjmp_prolog")
        def _setjmp() -> None:
            """Save the callee-saved registers so a later longjmp can resume here.

            The compiler uses setjmp/longjmp for error recovery. A stub that merely returns
            zero leaves the buffer empty, and the first error unwinds into whatever the
            memory happened to hold — which surfaced as an invalid instruction rather than
            a compile diagnostic.
            """
            from unicorn.arm_const import (
                UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
                UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
                UC_ARM_REG_SP, UC_ARM_REG_LR,
            )

            buffer = self.arg(0)
            saved = (
                UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
                UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
                UC_ARM_REG_SP, UC_ARM_REG_LR,
            )
            for index, register in enumerate(saved):
                self.write32(buffer + index * 4, self.uc.reg_read(register))
            self.set_return(0)

        @register("siglongjmp", "longjmp")
        def _longjmp() -> None:
            from unicorn.arm_const import (
                UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
                UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
                UC_ARM_REG_SP, UC_ARM_REG_LR,
            )

            buffer, value = self.arg(0), self.arg(1)
            saved = (
                UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
                UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
                UC_ARM_REG_SP, UC_ARM_REG_LR,
            )
            for index, register in enumerate(saved):
                self.uc.reg_write(register, self.read32(buffer + index * 4))
            self.set_return(value or 1)

        @register("__stackavail")
        def _stackavail() -> None:
            self.set_return(STACK_SIZE // 2)

        @register("__get_errno_ptr")
        def _errno() -> None:
            if getattr(self, "_errno_slot", None) is None:
                self._errno_slot = self._static(b"\0" * 4)
            self.set_return(self._errno_slot)

        @register("exit")
        def _exit() -> None:
            raise CgDrvError(f"compiler called exit({self.arg(0)})")

        # -- softfp libm ----------------------------------------------------
        #
        # QNX ARM softfp: a double arrives in a register pair, a float in one register,
        # and results come back the same way. Every one of these was previously left
        # unimplemented, and an unimplemented import returns 0 — which is not a neutral
        # answer here. The compiler calls them while folding constants and while encoding
        # a literal into FP20/FX10, so a stubbed `floorf` produced a *different, shorter*
        # program with `ok` true and zero diagnostics: exactly the silent failure the
        # per-compile reboot above was added for. Implementing them moved the byte-exact
        # score against the 90 known-good shipped binaries from 57 to 74, with no shader
        # losing a match.

        def _double(index: int) -> float:
            return struct.unpack(
                "<d", struct.pack("<II", self.arg(index), self.arg(index + 1))
            )[0]

        def _return_double(value: float) -> None:
            low, high = struct.unpack("<II", struct.pack("<d", value))
            self.set_return(low)
            _set_r1(high)

        def _float_arg(index: int) -> float:
            return struct.unpack("<f", struct.pack("<I", self.arg(index)))[0]

        def _return_float(value: float) -> None:
            self.set_return(struct.unpack("<I", struct.pack("<f", value))[0])

        def _libm(function, *args: float) -> float:
            """Mirror C's out-of-range results, where Python raises instead."""
            try:
                return float(function(*args))
            except OverflowError:
                return math.inf
            except ValueError:
                return math.nan

        def _round_to(function, value: float) -> float:
            return value if not math.isfinite(value) else float(function(value))

        @register("floor")
        def _floor() -> None:
            _return_double(_round_to(math.floor, _double(0)))

        @register("ceil")
        def _ceil() -> None:
            _return_double(_round_to(math.ceil, _double(0)))

        @register("floorf")
        def _floorf() -> None:
            _return_float(_round_to(math.floor, _float_arg(0)))

        @register("ceilf")
        def _ceilf() -> None:
            _return_float(_round_to(math.ceil, _float_arg(0)))

        @register("sqrt")
        def _sqrt() -> None:
            _return_double(_libm(math.sqrt, _double(0)))

        @register("exp")
        def _exp() -> None:
            _return_double(_libm(math.exp, _double(0)))

        @register("pow")
        def _pow() -> None:
            # The exponent is the second double, so it lands in r2:r3.
            _return_double(_libm(math.pow, _double(0), _double(2)))

        @register("fmod")
        def _fmod() -> None:
            _return_double(_libm(math.fmod, _double(0), _double(2)))

        @register("_Log")
        def _log() -> None:
            """Dinkumware's shared logarithm: r2 selects the base.

            Observed: GLSL `log` and `log2` both arrive with r2 == 0, log2 being computed
            as log(x) / log(2.0), so the natural log is the branch that matters.
            """
            value = _double(0)
            if value == 0.0:
                _return_double(-math.inf)
            elif self.arg(2):
                _return_double(_libm(math.log10, value))
            else:
                _return_double(_libm(math.log, value))

        @register("_Sin")
        def _sin() -> None:
            """Dinkumware's shared sine: r2 is a quarter-period offset.

            Observed: GLSL `sin` arrives with r2 == 0 and `cos` with r2 == 1. Selecting
            the function rather than adding pi/2 to the argument keeps cos exact at 0.
            """
            value = _double(0)
            if not math.isfinite(value):
                _return_double(math.nan)
                return
            quadrant = (
                math.sin,
                math.cos,
                lambda v: -math.sin(v),
                lambda v: -math.cos(v),
            )[self.arg(2) & 3]
            _return_double(quadrant(value))

        @register("_Dtest")
        def _dtest() -> None:
            _classify(struct.unpack("<d", self.uc.mem_read(self.arg(0), 8))[0])

        @register("_FDtest")
        def _fdtest() -> None:
            _classify(struct.unpack("<f", self.uc.mem_read(self.arg(0), 4))[0])

        def _classify(value: float) -> None:
            """Dinkumware's `_Dtest(double *)`: 2 NaN, 1 infinite, 0 ZERO, -1 finite.

            Returning 0 for everything told the compiler that every literal in the shader
            was zero, which is how these two came to matter more than their name suggests.
            """
            if math.isnan(value):
                self.set_return(2)
            elif math.isinf(value):
                self.set_return(1)
            else:
                self.set_return(0 if value == 0.0 else -1)

        @register("frexp")
        def _frexp() -> None:
            mantissa, exponent = math.frexp(_double(0))
            if self.arg(2):
                self.write32(self.arg(2), exponent)
            _return_double(mantissa)

        @register("ldexp")
        def _ldexp() -> None:
            exponent = self.arg(2)
            _return_double(
                _libm(
                    math.ldexp,
                    _double(0),
                    exponent - 0x100000000 if exponent >= 0x80000000 else exponent,
                )
            )

        # -- 64-bit helpers the EABI leaves to the runtime -------------------

        def _return_long(value: int) -> None:
            value &= 0xFFFFFFFFFFFFFFFF
            self.set_return(value & 0xFFFFFFFF)
            _set_r1(value >> 32)

        def _signed64(value: int) -> int:
            return value - (1 << 64) if value >= (1 << 63) else value

        @register("__aeabi_d2lz", "__aeabi_d2ulz")
        def _d2lz() -> None:
            value = _double(0)
            _return_long(int(value) if math.isfinite(value) else 0)

        @register("__aeabi_f2lz", "__aeabi_f2ulz")
        def _f2lz() -> None:
            value = _float_arg(0)
            _return_long(int(value) if math.isfinite(value) else 0)

        def _divmod64(left: int, right: int) -> None:
            """Quotient in r0:r1 and remainder in r2:r3, truncating toward zero."""
            from unicorn.arm_const import UC_ARM_REG_R2, UC_ARM_REG_R3

            if right == 0:
                quotient = remainder = 0
            else:
                quotient = abs(left) // abs(right)
                if (left < 0) != (right < 0):
                    quotient = -quotient
                remainder = left - quotient * right
            _return_long(quotient)
            remainder &= 0xFFFFFFFFFFFFFFFF
            self.uc.reg_write(UC_ARM_REG_R2, remainder & 0xFFFFFFFF)
            self.uc.reg_write(UC_ARM_REG_R3, remainder >> 32)

        @register("__aeabi_ldivmod")
        def _ldivmod() -> None:
            _divmod64(
                _signed64(self.arg(0) | (self.arg(1) << 32)),
                _signed64(self.arg(2) | (self.arg(3) << 32)),
            )

        @register("__aeabi_uldivmod")
        def _uldivmod() -> None:
            _divmod64(
                self.arg(0) | (self.arg(1) << 32),
                self.arg(2) | (self.arg(3) << 32),
            )

        def _format(fmt: str, args: "list[int]") -> str:
            """Enough of C's printf for the compiler's diagnostics and identifiers.

            The log is not decoration here: CgDrv_Compile searches it for "0 errors", so a
            stub that produced nothing left the compiler unable to see its own success.
            """
            out: list[str] = []
            index = 0
            position = 0
            while position < len(fmt):
                char = fmt[position]
                if char != "%":
                    out.append(char)
                    position += 1
                    continue
                position += 1
                spec = ""
                while position < len(fmt) and fmt[position] in "-+ #0123456789.*lhz":
                    if fmt[position] == "*":
                        spec += str(args[index] if index < len(args) else 0)
                        index += 1
                    elif fmt[position] not in "lhz":
                        spec += fmt[position]
                    position += 1
                if position >= len(fmt):
                    break
                kind = fmt[position]
                position += 1
                value = args[index] if index < len(args) else 0
                if kind == "%":
                    out.append("%")
                    continue
                index += 1
                if kind == "s":
                    out.append(("%" + spec + "s") % self.cstring(value))
                elif kind == "c":
                    out.append(chr(value & 0xFF))
                elif kind in "di":
                    signed = value - 0x100000000 if value >= 0x80000000 else value
                    out.append(("%" + spec + "d") % signed)
                elif kind == "u":
                    out.append(("%" + spec + "u") % value)
                elif kind in "xX":
                    out.append(("%" + spec + kind) % value)
                elif kind == "o":
                    out.append(("%" + spec + "o") % value)
                elif kind == "p":
                    out.append("0x%x" % value)
                elif kind in "fFgGeE":
                    import struct as _struct

                    raw = _struct.pack("<II", value, args[index] if index < len(args) else 0)
                    index += 1
                    out.append(("%" + spec + kind) % _struct.unpack("<d", raw)[0])
                else:
                    out.append(kind)
            return "".join(out)

        def _varargs(first: int, count: int = 12) -> list[int]:
            return [self.arg(first + step) for step in range(count)]

        @register("sprintf")
        def _sprintf() -> None:
            text = _format(self.cstring(self.arg(1)), _varargs(2))
            self.uc.mem_write(self.arg(0), text.encode("latin-1") + b"\0")
            self.set_return(len(text))

        @register("vsprintf")
        def _vsprintf() -> None:
            args = self.arg(2)
            text = _format(
                self.cstring(self.arg(1)),
                [self.read32(args + step * 4) for step in range(12)],
            )
            self.uc.mem_write(self.arg(0), text.encode("latin-1") + b"\0")
            self.set_return(len(text))

        @register("vsnprintf")
        def _vsnprintf() -> None:
            size = self.arg(1)
            args = self.arg(3)
            text = _format(
                self.cstring(self.arg(2)),
                [self.read32(args + step * 4) for step in range(12)],
            )
            payload = text.encode("latin-1")[: max(size - 1, 0)]
            if size:
                self.uc.mem_write(self.arg(0), payload + b"\0")
            self.set_return(len(text))

        @register("NvOsSnprintf")
        def _nvos_snprintf() -> None:
            size = self.arg(1)
            text = _format(self.cstring(self.arg(2)), _varargs(3))
            payload = text.encode("latin-1")[: max(size - 1, 0)]
            if size:
                self.uc.mem_write(self.arg(0), payload + b"\0")
            self.set_return(len(text))

        @register("printf", "puts", "fputs")
        def _printf() -> None:
            self.output.append(self.cstring(self.arg(0)))
            self.set_return(0)

        @register("qsort")
        def _qsort() -> None:
            """Sort in place using the guest's own comparison function.

            A no-op qsort leaves the compiler's tables unordered, and every later binary
            search over them silently misses — which is indistinguishable from the entry not
            existing at all.
            """
            base, count, width, compare = (
                self.arg(0), self.arg(1), self.arg(2), self.arg(3)
            )
            if not base or count < 2 or not width or not compare:
                self.set_return(0)
                return
            elements = [
                bytes(self.uc.mem_read(base + index * width, width))
                for index in range(count)
            ]
            scratch_a = self.malloc(width)
            scratch_b = self.malloc(width)

            import functools

            def compare_elements(left: bytes, right: bytes) -> int:
                self.uc.mem_write(scratch_a, left)
                self.uc.mem_write(scratch_b, right)
                return self._call_nested(compare, scratch_a, scratch_b)

            elements.sort(key=functools.cmp_to_key(compare_elements))
            for index, payload in enumerate(elements):
                self.uc.mem_write(base + index * width, payload)
            self.set_return(0)

        @register("sscanf")
        def _sscanf() -> None:
            """Enough of sscanf to parse the compiler's own option and table syntax.

            Returning zero unconditionally is not neutral: the compiler uses sscanf to read
            values out of its profile and option strings, and a parse that never succeeds is
            indistinguishable from a malformed definition.
            """
            import re as _re

            text = self.cstring(self.arg(0))
            fmt = self.cstring(self.arg(1))
            pattern = ""
            kinds: list[str] = []
            index = 0
            while index < len(fmt):
                char = fmt[index]
                if char == "%":
                    index += 1
                    while index < len(fmt) and fmt[index] in "0123456789.lh":
                        index += 1
                    if index >= len(fmt):
                        break
                    kind = fmt[index]
                    index += 1
                    if kind == "%":
                        pattern += "%"
                        continue
                    kinds.append(kind)
                    if kind in "diu":
                        pattern += r"\s*([-+]?\d+)"
                    elif kind in "xX":
                        pattern += r"\s*([0-9a-fA-F]+)"
                    elif kind in "feEgG":
                        pattern += r"\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?\d+)?)"
                    elif kind == "s":
                        pattern += r"\s*(\S+)"
                    elif kind == "c":
                        pattern += "(.)"
                    else:
                        kinds.pop()
                elif char.isspace():
                    pattern += r"\s*"
                    index += 1
                else:
                    pattern += _re.escape(char)
                    index += 1
            match = _re.match(pattern, text)
            if match is None:
                self.set_return(0)
                return
            assigned = 0
            for position, kind in enumerate(kinds):
                destination = self.arg(2 + position)
                if not destination:
                    break
                captured = match.group(position + 1)
                if kind in "diu":
                    self.write32(destination, int(captured) & 0xFFFFFFFF)
                elif kind in "xX":
                    self.write32(destination, int(captured, 16))
                elif kind in "feEgG":
                    self.uc.mem_write(
                        destination, struct.pack("<d", float(captured))
                    )
                elif kind == "s":
                    self.uc.mem_write(
                        destination, captured.encode("latin-1") + b"\0"
                    )
                elif kind == "c":
                    self.uc.mem_write(destination, captured.encode("latin-1"))
                assigned += 1
            self.set_return(assigned)

        for name in ("putchar", "fprintf", "vfprintf", "fputc", "fflush",
                     "fclose", "feof", "fgetc", "fread", "fseek", "ftell",
                     "fwrite", "fopen64", "mprotect"):
            self.handlers.setdefault(name, lambda: self.set_return(0))


def main(argv: list[str] | None = None) -> int:
    """Compile a shader with the firmware's compiler, or report the harness state."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="AU491 Cg driver under emulation")
    parser.add_argument("source", nargs="?", type=Path)
    parser.add_argument(
        "--target", choices=sorted(TARGETS), default="fragment"
    )
    parser.add_argument("--language", type=int, default=LANGUAGE_OGLES)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    driver = CgDriver()
    if args.source is None:
        print(f"library      : {CGDRV_LIBRARY}")
        print(f"entry points : {sorted(driver.exports)}")
        print(f"imports bound: {len(driver.import_slots)}")
        print(f"constructors : {driver.initialisers}")
        handle = driver.call(driver.exports["CgDrv_Create"])
        print(f"CgDrv_Create : 0x{handle:x}")
        print(f"unimplemented: {sorted(set(driver.unimplemented)) or 'none'}")
        return 0

    result = driver.compile(
        args.source.read_text(), args.target, args.language
    )
    print(f"ok           : {result.ok}")
    print(f"binary       : {len(result.binary)} bytes")
    print(f"instructions : {result.instructions}")
    if result.error:
        print(f"error        : {result.error}")
    if result.log:
        print(f"log          :\n{result.log}")
    if result.binary and args.output:
        args.output.write_bytes(result.binary)
        print(f"written      : {args.output}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
