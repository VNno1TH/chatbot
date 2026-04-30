# patch_prompts.py — Apply clean patches to prompts.py
import os, sys

# Force UTF-8 output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src', 'rag', 'prompts.py')

with open(src, 'r', encoding='utf-8') as f:
    content = f.read()

original_size = len(content.encode('utf-8'))
lines_count = len(content.splitlines())

# PATCH 1: Replace {context} block in section 2
old_block = '## 2. Ng\u1eef c\u1ea3nh RAG\n\n```\n[RETRIEVED CONTEXT]\n{context}\n[END RETRIEVED CONTEXT]\n```'
new_block = '## 2. Ng\u1eef c\u1ea3nh RAG\n\nTh\u00f4ng tin tham chi\u1ebfu \u0111\u01b0\u1ee3c cung c\u1ea5p \u1edf cu\u1ed1i prompt trong ph\u1ea7n `[RETRIEVED CONTEXT]`. \u0110\u1ecdc k\u1ef9 tr\u01b0\u1edbc khi tr\u1ea3 l\u1eddi.'

if old_block in content:
    content = content.replace(old_block, new_block, 1)
    print('PATCH 1 OK: Moved context out of section 2')
else:
    print('PATCH 1 SKIP: block not found, checking...')
    idx = content.find('{context}')
    print(f'  {{context}} at char: {idx}')

# PATCH 2: Remove section 9 (examples, ~1500 tokens)
sec9_marker = '\n## 9.'
idx9 = content.find(sec9_marker)
if idx9 == -1:
    # Try alternate
    sec9_marker = '\n## 9 '
    idx9 = content.find(sec9_marker)

if idx9 > 0:
    closing = '\n\n*Phi\u00ean b\u1ea3n 2.2 | HaUI Chatbot | 04/2026*\n"""'
    content = content[:idx9] + '\n\n---\n' + closing
    print(f'PATCH 2 OK: Removed Section 9 at char {idx9}')
else:
    # Find by "Cau hoi mau" pattern
    for marker in ['\u2014 Tra c\u1ee9u \u0111\u01a1n', 'M\u1eabu 1', 'mau_1', 'Cau hoi mau']:
        idx9 = content.find(marker)
        if idx9 > 0:
            # Find start of ## header before this
            h = content.rfind('\n## ', 0, idx9)
            if h > 0:
                closing = '\n\n---\n\n*Phi\u00ean b\u1ea3n 2.2 | HaUI Chatbot | 04/2026*\n"""'
                content = content[:h] + '\n\n---\n' + closing
                print(f'PATCH 2 OK: Removed Section 9 via marker "{marker}"')
                break
    else:
        print('PATCH 2 SKIP: Section 9 not found. Current section headers:')
        for i, l in enumerate(content.splitlines()):
            if l.strip().startswith('## '):
                print(f'  L{i+1}: {l[:60]}')

new_size = len(content.encode('utf-8'))
saved = original_size - new_size
print(f'Result: {len(content.splitlines())} lines, {new_size} bytes (saved {saved} bytes)')

with open(src, 'w', encoding='utf-8') as f:
    f.write(content)
print('Written OK')
