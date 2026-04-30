# trim_prompt.py — Remove Section 9 (examples) from prompts.py to reduce input tokens
import os

src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src', 'rag', 'prompts.py')

with open(src, 'rb') as f:
    raw = f.read()

# Try utf-8 first, fallback to latin-1
try:
    content = raw.decode('utf-8')
    enc = 'utf-8'
except UnicodeDecodeError:
    content = raw.decode('latin-1')
    enc = 'latin-1'

print(f"Read {len(raw)} bytes (encoding: {enc})")
print(f"Total lines: {len(content.splitlines())}")

# Find Section 9
markers = ['## 9.', '## 9 ', '*Phien ban', '*Phiên bản']
cut_idx = -1
for marker in markers:
    idx = content.find(marker)
    if idx > 0:
        print(f"Found cut marker '{marker}' at char {idx}")
        cut_idx = idx
        break

if cut_idx == -1:
    # Find the last --- separator before end of file
    last_sep = content.rfind('\n---\n')
    if last_sep > 0:
        cut_idx = last_sep
        print(f"Using last '---' at char {cut_idx}")

if cut_idx == -1:
    print("ERROR: Could not find section 9. Current file tail:")
    print(repr(content[-500:]))
else:
    # Keep before Section 9, add closing
    closing = '\n---\n\n*Phien ban 2.2 | HaUI Chatbot | 04/2026*\n"""\n'
    new_content = content[:cut_idx] + closing

    out_bytes = new_content.encode('utf-8')
    with open(src, 'wb') as f:
        f.write(out_bytes)

    saved = len(raw) - len(out_bytes)
    print(f"Done! Saved {saved} bytes ({len(raw.splitlines())} -> {len(out_bytes.splitlines())} lines)")
    print(f"New size: {len(out_bytes)} bytes")
