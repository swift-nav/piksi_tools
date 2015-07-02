# GDB plugin for generation of core dumps on bare-metal ARM.
#
# This replaces GDB's 'gcore' command.  A new GDB parameter
# 'gcore-file-name' is added to set the name of the core file to be dumped.
# The module also hooks stop events on SIGSEGV to core dump and resume
# the target.
#
# The generated core dumps should be used with gdb-multiarch on Debian
# or similar systems.  The GDB provided with gcc-arm-embedded is not capable
# of reading a core file.  Only the general purpose registers are available
# from the core dump.

# Referece:
# - Tool Interface Standard (TIS) Executable and Linking Format (ELF)
#   Specification Version 1.2 (May 1995)
#   http://refspecs.linuxbase.org/elf/elf.pdf

import gdb
import struct
import time

# This nasty struct stuff could be replaced with construct, at the cost
# of adding a horrible dependency.  It may be possible to use ctypes.Structure
# but it wasn't immediately obvious how.
class Struct(object):
  def __init__(self, buf=None):
    if buf is None:
      buf = b"\0" * self.sizeof()
    fields = struct.unpack(self.__class__.fmt, buf[:self.sizeof()])
    self.__dict__.update(zip(self.__class__.fields, fields))

  def sizeof(self):
    return struct.calcsize(self.__class__.fmt)

  def dumps(self):
    keys =  self.__class__.fields
    return struct.pack(self.__class__.fmt, *(self.__dict__[k] for k in keys))

  def __str__(self):
    keys =  self.__class__.fields
    return (self.__class__.__name__ + "({" +
        ", ".join("%s:%r" % (k, self.__dict__[k]) for k in keys) +
        "})")

class Elf32_Ehdr(Struct):
  """ELF32 File header"""
  ET_NONE = 0
  ET_EXEC = 2
  ET_CORE = 4
  fields = ("e_ident",
            "e_type",
            "e_machine",
            "e_version",
            "e_entry",
            "e_phoff",
            "e_shoff",
            "e_flags",
            "e_ehsize",
            "e_phentsize",
            "e_phnum",
            "e_shentsize",
            "e_shnum",
            "e_shstrndx")
  fmt = "<16sHHLLLLLHHHHHH"

  def __init__(self, buf=None):
    Struct.__init__(self, buf)
    if buf is None:
      # Fill in sane ELF header for LSB32
      self.e_ident = b"\x7fELF\1\1\1\0\0\0\0\0\0\0\0\0"
      self.e_version = 1
      self.e_ehsize = self.sizeof()

class Elf32_Phdr(Struct):
  """ELF32 Program Header"""
  PT_NULL = 0
  PT_LOAD = 1
  PT_NOTE = 4
  fields = ("p_type",
            "p_offset",
            "p_vaddr",
            "p_paddr",
            "p_filesz",
            "p_memsz",
            "p_flags",
            "p_align")
  fmt = "<LLLLLLLL"

class ARM_prstatus(Struct):
  """ARM Program Status structure"""
  fields = ("si_signo", "si_code", "si_errno",
            "pr_cursig",
            "pr_pad0",
            "pr_sigpend",
            "pr_sighold",
            "pr_pid",
            "pr_pid",
            "pr_pgrp",
            "pr_sid",
            "pr_utime",
            "pr_stime",
            "pr_cutime",
            "pr_cstime")
  fmt = "<3LHHLLLLLLQQQQ"

class CoreFile(object):
  """Beginnings of a ELF file object.
     Only supports program headers (segments) used by core files and not
     Sections used by executables."""
  def __init__(self, fileobj=None):
    """Create a core object (from a file image)"""
    ehdr = self._ehdr = Elf32_Ehdr(fileobj)
    self._phdr = []
    for i in range(self._ehdr.e_phnum):
      chunk = fileobj[ehdr.e_phoff + i * ehdr.e_phentsize:
                      ehdr.e_phoff + (i+1) * ehdr.e_phentsize]
      phdr = Elf32_Phdr(chunk)
      phdr.data = fileobj[phdr.p_offset:phdr.p_offset + phdr.p_filesz]
      self._phdr.append(phdr)

  def update_headers(self):
    """Update header fields after segments are modified."""
    ehdr = self._ehdr
    if self._phdr:
      ehdr.e_phoff = ehdr.sizeof()
      ehdr.e_phentsize = self._phdr[0].sizeof()
      ehdr.e_phnum = len(self._phdr)
    else:
      ehdr.e_phoff = 0
      ehdr.e_phentsize = 0
      ehdr.e_phnum = 0
    ofs = ehdr.e_phoff + ehdr.e_phentsize * ehdr.e_phnum
    for phdr in self._phdr:
      phdr.p_offset = ofs
      phdr.p_filesz = len(phdr.data)
      if phdr.p_filesz > phdr.p_memsz:
        phdr.p_memsz = phdr.p_filesz
      ofs += phdr.p_filesz

  def dump(self, f):
    """Write the object to an ELF file."""
    self.update_headers()
    f.write(self._ehdr.dumps())
    for phdr in self._phdr:
      f.write(phdr.dumps())
    for phdr in self._phdr:
      f.write(phdr.data)

  def set_type(self, t):
    """Set the file type in the file header."""
    self._ehdr.e_type = t

  def set_machine(self, m):
    """Set the machine type in the file header."""
    self._ehdr.e_machine = m

  def add_program(self, p_type, vaddr, data):
    """Add a program header (segment) to the object."""
    phdr = Elf32_Phdr()
    phdr.p_type = p_type
    phdr.p_vaddr = vaddr
    phdr.p_filesz = phdr.p_memsz = len(data)
    phdr.data = data
    self._phdr.append(phdr)

  def __str__(self):
    return str(self._ehdr) + "\n" + "\n".join(str(phdr) for phdr in self._phdr)

def note_desc(name, type, desc):
  """Conveninece function to format a note descriptor.
     All note descriptors must be concatenated and added to a
     PT_NOTE segment."""
  name = bytearray(name, 'ascii') + b'\0'
  header = struct.pack("<LLL", len(name), len(desc), type)
  # pad up to 4 byte alignment
  name += ((4 - len(name)) % 4) * b'\0'
  desc += ((4 - len(desc)) % 4) * b'\0'
  return header + name + desc


class CommandGCore(gdb.Command):
  """Replacemenet 'gcore' function to generate ARM core dumps."""
  def __init__(self):
    super(CommandGCore, self).__init__('gcore', gdb.COMMAND_USER)

  def invoke(self, arg='', from_tty=False, sig=0):
    gdb.newest_frame().select()
    regs = [0] * 19
    # parse_and_eval seems to be the only way to access target registers
    for i in range(16):
      regs[i] = int(gdb.parse_and_eval("(unsigned long)$r%d" % i))
    regs[16] = int(gdb.parse_and_eval("(unsigned long)$xpsr"))
    # Don't know how to include other registers in core dump
    prstatus = ARM_prstatus()
    prstatus.pr_cursig = sig
    # Is it possible to include a target register description?
    notes = note_desc("CORE", 1, prstatus.dumps() + struct.pack("<19L", *regs))

    inf = gdb.selected_inferior()
    # How do we query the memory map from GDB?
    # TODO: Use 'info mem'
    ram = inf.read_memory(0x20000000, 128*1024)
    ccmram = inf.read_memory(0x10000000, 64*1024)
    scs = inf.read_memory(0xE000ED00, 0x40)

    core = CoreFile()
    core.set_type(Elf32_Ehdr.ET_CORE)
    core.set_machine(0x28) #ARM
    core.add_program(Elf32_Phdr.PT_NOTE, 0, notes)
    core.add_program(Elf32_Phdr.PT_LOAD, 0x10000000, ccmram)
    core.add_program(Elf32_Phdr.PT_LOAD, 0x20000000, ram)
    core.add_program(Elf32_Phdr.PT_LOAD, 0xE000ED00, scs)

    fn = arg if arg else gcore_file_name.value
    fn += "-" + time.strftime("%y%m%d-%H%M%S")
    core.dump(open(fn, "wb"))
    print("(core dumped to %r)" % fn)

gcore = CommandGCore()

def stop_handler(event):
  """Dump core file when GDB's inferior is stopped with SIGSEGV."""
  if type(event) is not gdb.SignalEvent:
    return
  if event.stop_signal == "SIGSEGV":
    gcore.invoke(sig=11)
    gdb.execute("continue")
gdb.events.stop.connect(stop_handler)

class ParameterGCoreFileName(gdb.Parameter):
  def __init__(self):
    self.set_doc = "Set gcore default name"
    self.show_doc = "Show gcore default name"
    gdb.Parameter.__init__(self, "gcore-file-name", gdb.COMMAND_SUPPORT,
                           gdb.PARAM_STRING)
    self.value = "core"
  def get_set_string(self):
    cm3.TPIU.ACPR = self.value
    return "Default gcore name is %r" % self.value
  def get_show_string(self, svalue):
    return "Default gcore name is %r" % self.value
gcore_file_name = ParameterGCoreFileName()

gdb.execute("set mem inaccessible-by-default off")
gdb.execute("handle SIGSEGV stop nopass")
gdb.execute("handle SIGTRAP nostop nopass")

