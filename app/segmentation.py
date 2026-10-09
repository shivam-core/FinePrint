# app/segmentation.py
import regex as re

def sentencize(text: str) -> list[tuple[str, int, int]]:
    """
    Splits text into sentences based on punctuation, preserving offsets.
    Protects common abbreviations, decimals.
    """
    # Regex to find sentence boundaries:
    # A boundary is a period, exclamation, or question mark, optionally followed by quotes/brackets,
    # then whitespace, then a capital letter or number.
    # We use negative lookbehinds for common abbreviations.
    
    abbrevs = r"(?<!\be\.g)(?<!\bi\.e)(?<!\bU\.S)(?<!\bLtd)(?<!\bInc)(?<!\bDr)(?<!\bMr)(?<!\bMrs)(?<!\bMs)(?<!\bProf)(?<!\bSt)(?<!\bFig)(?<!\bvs)"
    decimals = r"(?<!\d)"
    
    # We yield spans. We'll find all matching boundaries.
    boundary_pattern = re.compile(
        abbrevs + decimals + r"([.!?]+[\"']?\s+)(?=[A-Z0-9'\"\[\(])", 
        re.V0
    )
    
    spans = []
    start = 0
    for match in boundary_pattern.finditer(text):
        end = match.end()
        # The sentence includes the punctuation and whitespace
        sentence = text[start:end]
        if sentence.strip():
            spans.append((sentence, start, end))
        start = end
        
    if start < len(text):
        sentence = text[start:]
        if sentence.strip():
            spans.append((sentence, start, len(text)))
            
    # Fallback if the whole text is one block and very long
    final_spans = []
    for s, st, en in spans:
        # Check if it has internal newlines that might be list items/paragraphs
        # Split on double newlines
        parts = []
        p_start = 0
        for p_match in re.finditer(r'\n\s*\n', s):
            p_end = p_match.start()
            parts.append((s[p_start:p_end], st + p_start, st + p_end))
            parts.append((s[p_end:p_match.end()], st + p_end, st + p_match.end())) # the whitespace
            p_start = p_match.end()
            
        if p_start < len(s):
            parts.append((s[p_start:], st + p_start, en))
            
        for pt, pst, pen in parts:
            if pt.strip():
                final_spans.append((pt, pst, pen))
                
    return final_spans
