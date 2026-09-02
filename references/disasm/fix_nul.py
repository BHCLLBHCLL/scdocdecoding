# -*- coding: utf-8 -*-
"""Replace the accidental real-NUL literal in scdoc_write.py blob line."""
import io

P = r"D:\training\caedecoder\scdocdecoding\scdm\scdoc_write.py"
s = io.open(P, encoding="latin-1").read()

tpl = 'blob = b"' + "\x00\x00\x00\x01" + "\x00" * 7 + '"'
esc_txt = "\\x00" * 3 + "\\x01" + "\\x00" * 7
esc = 'blob = b"' + esc_txt + '"'
n = s.count(tpl)
print("template hits:", n)
if n != 1:
    raise SystemExit("expected exactly one template hit")
# the intended literal in the source is the escaped text b"\\x00..."
# which, when written to disk as code, must be the 11-byte NUL sequence is
# WRONG - we want the TEXT backslash-escapes. esc above is built with chr(92)
# plus letters, i.e. the text "\\x00" -> 4 chars.  Verify:
print("esc raw:", repr(esc[:30]))
s = s.replace(tpl, esc)
io.open(P, "w", encoding="latin-1", newline="").write(s)
print("nuls after:", s.count("\x00"))
