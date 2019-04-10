#!/usr/bin/env python2

import os

import sys

import io

import numpy as np
import json

import decimal as dec

from sbp.jit import msg
from sbp.jit.table import dispatch

from sbp import msg as msg_nojit
from sbp.table import dispatch as dispatch_nojit

NORM = os.environ.get('NOJIT') is not None

dec.getcontext().rounding = dec.ROUND_HALF_UP


class SbpJSONEncoder(json.JSONEncoder):
    # Overwrite for json.JSONEncoder.iterencode()
    def iterencode(self, o, _one_shot=False):
        """Encode the given object and yield each string
        representation as available.
        For example::
            for chunk in JSONEncoder().iterencode(bigobject):
                mysocket.write(chunk)
        """
        if self.check_circular:
            markers = {}
        else:
            markers = None
        if self.ensure_ascii:
            _encoder = json.encoder.encode_basestring_ascii
        else:
            _encoder = json.encoder.encode_basestring

        def floatstr(o, allow_nan=self.allow_nan,
                     _repr=float.__repr__, _inf=float('inf'), _neginf=-float('inf')):
            # Check for specials.  Note that this type of test is processor
            # and/or platform-specific, so do tests which don't depend on the
            # internals.
            if o != o:
                text = 'NaN'
            elif o == _inf:
                text = 'Infinity'
            elif o == _neginf:
                text = '-Infinity'
            elif o.is_integer():
                return str(int(o))
            elif abs(o) < 0.1 or abs(o) > 9999999:
                # GHC uses showFloat to print which will result in the
                # scientific notation whenever the absolute value is outside the
                # range between 0.1 and 9,999,999. Numpy wants to put '+' after
                # exponent sign, strip it. Use decimal module to control
                # rounding method.
                text = np.format_float_scientific(o, precision=None, unique=True, trim='0', exp_digits=1)
                d = dec.Decimal(text)
                rounded = round(dec.Decimal(o), abs(d.as_tuple().exponent))

                if d == rounded:
                    # original is good
                    return text.replace('+', '')

                return ('{:.' + str(len(d.as_tuple().digits) - 1) + 'e}').format(rounded).replace('+', '')
            else:
                d = dec.Decimal(np.format_float_positional(o, precision=None, unique=True, trim='0'))
                return round(dec.Decimal(o), abs(d.as_tuple().exponent)).to_eng_string()

            if not allow_nan:
                raise ValueError(
                    "Out of range float values are not JSON compliant: " +
                    repr(o))

            return text

        _iterencode = json.encoder._make_iterencode(
            markers, self.default, _encoder, self.indent, floatstr,
            self.key_separator, self.item_separator, self.sort_keys,
            self.skipkeys, _one_shot)
        return _iterencode(o, 0)

    def default(self, obj):
        if isinstance(obj, np.float32):
            d = dec.Decimal(np.format_float_positional(obj, precision=None, unique=True, trim='0'))
            ret = float(round(dec.Decimal(float(obj)), abs(d.as_tuple().exponent)))
            return ret
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


def main():
    header_len = 6
    reader = io.open(sys.stdin.fileno(), 'rb')
    buf = np.zeros(4096, dtype=np.uint8)
    unconsumed_offset = 0
    read_offset = 0
    buffer_remaining = len(buf)
    while True:
        if buffer_remaining == 0:
            memoryview(buf)[0:(read_offset - unconsumed_offset)] = \
                memoryview(buf)[unconsumed_offset:read_offset]
            read_offset = read_offset - unconsumed_offset
            unconsumed_offset = 0
            buffer_remaining = len(buf) - read_offset
        mv = memoryview(buf)[read_offset:]
        read_length = reader.readinto(mv)
        if read_length == 0:
            unconsumed = read_offset - unconsumed_offset
            if unconsumed != 0:
                sys.stderr.write("unconsumed: {}\n".format(unconsumed))
                sys.stderr.flush()
            break
        read_offset += read_length
        buffer_remaining -= read_length
        while True:
            if NORM:
                from construct.core import StreamError
                bytes_available = read_offset - unconsumed_offset
                b = buf[unconsumed_offset:(unconsumed_offset + bytes_available)]
                try:
                    m = msg_nojit.SBP.unpack(b)
                except StreamError:
                    break
                m = dispatch_nojit(m)
                sys.stdout.write(json.dumps(m.to_json_dict(),
                                            allow_nan=False,
                                            sort_keys=True,
                                            separators=(',', ':')))
                consumed = header_len + m.length + 2
            else:
                consumed, payload_len, msg_type, sender, crc, crc_fail = \
                    msg.SBP.unpack_payload(buf, unconsumed_offset, (read_offset - unconsumed_offset))

                if not crc_fail and msg_type != 0:
                    payload = buf[unconsumed_offset + header_len:unconsumed_offset + header_len + payload_len]
                    m = dispatch(msg_type)(msg_type, sender, payload_len, payload, crc)
                    res, offset, length = m.unpack(buf, unconsumed_offset + header_len, payload_len)
                    sys.stdout.write(json.dumps(res,
                                                allow_nan=False,
                                                sort_keys=True,
                                                separators=(',', ':'),
                                                cls=SbpJSONEncoder))
                    sys.stdout.write("\n")

                if consumed == 0:
                    break
            unconsumed_offset += consumed


if __name__ == '__main__':
    main()
