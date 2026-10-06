"""Read-only decoder for KISSsoft ``*.KDB`` database files.

Binary layout (reverse-engineered, KISSsoft 2026 "ver2026" files):

* 19-byte header: ``ver<YYYY>`` + ``time`` + uint32 LE unix timestamp + 4x 0x00
* one schema block per table, back to back::

      "anf" <NAME> 0x00 "integer ID,integer FOLGE,...,string XX" 0x0A
      0x00 <uint64 n_records> <uint32 rec_bytes> <uint32 rec_off>
      <uint32 str_off> <uint32 str_bytes> "end"

  (``rec_off`` / ``str_off`` are byte offsets relative to the pool base)
* global string pool starting right after the last ``end`` marker (+1 byte),
  UTF-16LE, NUL-terminated, heavy suffix sharing, multi-language values
  joined with U+00AC ("¬"), translation-wrapped in ``#TS(...)TS~``
* fixed-size record arrays, ``integer`` = 4 bytes, ``real`` = 8-byte double,
  ``string`` = uint32 offset in UTF-16 code units from the pool base
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field


@dataclass
class KdbTable:
    name: str
    fields: list[tuple[str, str]]          # [(type, column), ...]
    n_records: int = 0
    record_size: int = 0
    record_offset: int = 0                  # bytes from pool base
    string_offset: int = 0
    string_bytes: int = 0
    records: list[dict] = field(default_factory=list)

    @property
    def columns(self) -> list[str]:
        return [c for _, c in self.fields]


class KdbFile:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as fh:
            self.data = fh.read()
        d = self.data
        if not d.startswith(b"ver"):
            raise ValueError(f"{path}: not a KISSsoft KDB file")
        self.version = d[3:7].decode("ascii", "replace")
        self.timestamp = struct.unpack_from("<I", d, 11)[0] if d[7:11] == b"time" else 0
        self.tables: dict[str, KdbTable] = {}
        self._str_cache: dict[int, str] = {}
        self._parse_blocks()
        self.pool_base = self._block_end + 1
        self._load_records()

    # -- parsing ---------------------------------------------------------
    def _parse_blocks(self):
        d, pos = self.data, 19
        end = pos
        while pos < len(d) and d[pos:pos + 3] == b"anf":
            name_end = d.index(b"\x00", pos + 3)
            name = d[pos + 3:name_end].decode("latin1")
            schema_end = d.index(b"\n", name_end)
            schema = d[name_end + 1:schema_end].decode("latin1")
            fields = [tuple(f.split(" ", 1)) for f in schema.split(",")]
            end = d.index(b"end", schema_end)
            tail = d[schema_end + 1:end]
            n, a, b, c, e = struct.unpack("<Q4I", tail[1:26])
            self.tables[name] = KdbTable(
                name=name, fields=fields, n_records=n,
                record_size=(a // n) if n else 0,
                record_offset=b, string_offset=c, string_bytes=e,
            )
            pos = end + 3
        self._block_end = end + 3

    def _pool_string(self, char_off: int, str_base: int | None = None) -> str:
        """Decode a NUL-terminated UTF-16LE pool string.

        ``char_off`` counts UTF-16 code units from the *table's own* string
        segment (pool base + ``string_offset``), not from the global pool
        start -- only tables whose segment offset happens to be 0 (e.g. the
        first table) resolve against the raw pool base.
        """
        d = self.data
        start = (self.pool_base if str_base is None else str_base) + 2 * char_off
        key = start
        cached = self._str_cache.get(key)
        if cached is not None:
            return cached
        # NUL terminator: two zero bytes at an even offset from `start`
        i = d.find(b"\x00\x00", start)
        while i >= 0 and (i - start) % 2:
            i = d.find(b"\x00\x00", i + 1)
        end = start if i < 0 else i
        raw = d[start:end]
        try:
            value = raw.decode("utf-16-le")
        except UnicodeDecodeError:
            value = raw.decode("utf-16-le", "replace")
        if len(self._str_cache) < 2_000_000:
            self._str_cache[start] = value
        return value

    def _load_records(self):
        for tab in self.tables.values():
            str_base = self.pool_base + tab.string_offset
            base = self.pool_base + tab.record_offset
            for i in range(tab.n_records):
                off = base + i * tab.record_size
                row = {}
                for ftype, fname in tab.fields:
                    if ftype == "integer":
                        row[fname], off = struct.unpack_from("<i", self.data, off)[0], off + 4
                    elif ftype == "real":
                        row[fname], off = struct.unpack_from("<d", self.data, off)[0], off + 8
                    else:  # string -> offset in UTF-16 units from own segment
                        (soff,) = struct.unpack_from("<I", self.data, off)
                        row[fname] = self._pool_string(soff, str_base)
                        off += 4
                tab.records.append(row)


def first_language(value: str) -> str:
    """Return the first (German) variant of a ``a¬b¬c`` multi-language value."""
    inner = value
    if inner.startswith("#TS(") and inner.endswith("TS~"):
        inner = inner[4:-3]
    return inner.split("¬")[0]
