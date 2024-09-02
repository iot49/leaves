import re
import logging
from io import StringIO
from collections import OrderedDict

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

##################################################################################
# dump yaml

_INDENT = '  '

def is_scalar(obj):
    try:
        len(obj)
        return isinstance(obj, str)
    except:
        return True

def dump(obj, stream, indent=0):
    global _INDENT
    if isinstance(obj, dict):
        for key, value in obj.items():
            if is_scalar(value):
                stream.write(f"{_INDENT*indent}{key}: {value}\n")
            else:
                stream.write(f"{_INDENT*indent}{key}:\n")
                dump(value, stream, indent+1)
    elif isinstance(obj, list):
        for value in obj:
            s = StringIO()
            dump(value, s)
            s.seek(0)
            for i, l in enumerate(s):
                if i==0: 
                    stream.write(f"{_INDENT*indent}- {l}")
                else:
                    stream.write(f"{_INDENT*indent}  {l}")
    else:
        stream.write(f"{_INDENT*indent}{obj}\n")


def dumps(obj):
    s = StringIO()
    dump(obj, s)
    return s.getvalue()


##################################################################################
# parse yaml

class Y:

    @classmethod
    def parse(cls, stream, file_name):
        return cls(stream, file_name)._parse(0)

    def __init__(self, stream, file_name):
        self.file_name = file_name
        self._stream = stream
        # lexer
        self._line = ""
        self._line_no = 0
        self._next()

    def _parse(self, indent):      
        while True:
            # print(f"{self._line_no:3} {self._line:50} {self._indent:2} {'[]' if self._list else '  '} {(self._key if self._key else ''):10}: {self._value}")
            if self._indent < 0: 
                # eof
                return None
            if self._key or self._value:
                return self._parse_list(indent) if self._list else self._parse_dict(indent)
            self._next()

    def _parse_dict(self, indent):
        result = OrderedDict()
        if self._indent < indent: self._syntax("indentation")
        indent = self._indent
        while True:
            if self._key and self._value:
                result[self._key] = self._value
            elif self._value:
                self._syntax("missing colon")
            elif self._key:
                key = self._key
                self._next()
                value = None if self._indent <= indent else self._parse(indent+1)
                result[key] = value
                if self._indent < indent:
                    # end of dict or eof
                    return result
                # _parse looks ahead
                continue
            self._next()
            if self._indent < indent: 
                # end of dict or eof
                return result
            if self._indent != indent: self._syntax(f"inconsistent indent: {self._indent}, expected {indent}")
            if self._list: self._syntax("unexpected dash") 
        

    def _parse_list(self, indent):
        result = []
        if self._indent < indent: self._syntax(f"indentation: {self._indent}, expected {indent}")
        indent = self._indent
        while True:
            if self._list:
                # append list element
                if self._key and self._value:
                    result.append(OrderedDict({ self._key: self._value }))
                elif self._value:
                    result.append(self._value)
                elif self._key:
                    key = self._key
                    self._next()
                    value = None if self._indent <= indent else self._parse(indent+1)
                    result.append(OrderedDict({ key: value }))
                    if self._indent < indent:
                        # end of dict or eof
                        return result
                    # _parse looks ahead
                    continue
            else:
                # merge into dict
                if self._key and self._value:
                    d = result[-1]
                    if not isinstance(d, dict): 
                        self._syntax("not a dictionary")
                    else:
                        d[self._key] = self._value
                elif self._value:
                    self._syntax("expected dash")
                elif self._key:
                    key = self._key
                    self._next()
                    d = result[-1]
                    if not isinstance(d, dict): 
                        self._syntax("not a dictionary")
                    else:
                        d[key] = None if self._indent <= indent else self._parse(indent+1)
                    if self._indent < indent:
                        # end of dict or eof
                        return result
                    # _parse looks ahead
                    continue
            self._next()
            if self._indent < indent: 
                # end of dict or eof
                return result
            if self._indent != (indent if self._list else indent+2): self._syntax(f"inconsistent indent: {self._indent}, expected {indent}")
        return result


    #################################
    # lexer

    _RE_INDENT = re.compile(r'(\s*)(-?)\s*(.*)')
    _RE_QKEY   = re.compile(r'("[^"]*"|\'[^\']*\')(:?)(.*)')
    _RE_QVALUE = re.compile(r'\s*("[^"]*"|\'[^\']*\')\s*([^#]*)')

    def _next(self):
        self._key = self._value = None
        while True:
            # loop until we get a non-empty line (or eof)
            if self._key or self._value:
                # successful parse
                return
                
            # parse next (non-empty} line
            self._line = self._stream.readline()
            if not self._line: 
                # EOF
                self._indent = -1
                self._line = self._key = self._value = None
                return
            self._line = self._line.rstrip()
            self._line_no += 1

            # indent, dash
            indent, dash, rest = self._RE_INDENT.match(self._line).groups()
            if '\t' in indent: 
                self._syntax('tab')
            self._indent = len(indent)
            self._list = dash == '-'

            # quoted key?
            if m := self._RE_QKEY.match(rest):
                key, colon, value = m.groups()
                if '\t' in indent: 
                    self._syntax('tab')
                self._indent = len(indent)
                self._list = dash == '-'
                self._key = key[1:-1]
                if colon == ':':
                    self._value = self._parse_value(value)
                else:
                    self._value = self._key
                    self._key = None
                continue
                
            # key not quoted
            kv = rest.split(': ', 1)
            if len(kv) == 2:
                key, value = kv
                colon = ': '
            else: 
                key, colon, value = rest.rpartition(':')
                
            if colon:
                if '#' in key:
                    key, _ = key.split('#', 1)
                    key = key.strip()
                    if key.endswith(':'):
                        self._key = key[0:-1]
                        self._value = None
                    else:
                        self._key = None
                        self._value = key
                else:
                    self._key = key
                    self._value = self._parse_value(value)
                continue

            self._key = None
            self._value = self._parse_value(rest)

    def _parse_value(self, v):
        if m := self._RE_QVALUE.match(v):
            if m.group(2):
                self._syntax(f"unexpected trailer: {m.group(2)} (ignored)")
            return str(m.group(1))[1:-1]
        if '#' in v:
            v, _ = v.split('#', 1)
        return v.strip()

    def _syntax(self, msg):
        logger.error(f"Syntax error in {self.file_name} line {self._line_no} '{self._line.strip()}': {msg}")


def load(stream, file_name="<stream>"):
    return Y.parse(stream, file_name)

def loads(string, file_name="<string>"):
    return Y.parse(StringIO(string), file_name)

