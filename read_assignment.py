import sys
sys.path.insert(0, '.')
import fitz

doc = fitz.open('asa-case-study-candidate (2) (1) (1) (1).pdf')
for i, page in enumerate(doc):
    text = page.get_text()
    print(f'=== PAGE {i+1} ===')
    print(text)
    print()
