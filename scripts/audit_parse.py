"""Split a model reply into answer + SELF-AUDIT fields."""
import re
FIELDS = ["POSITIONING","GEOS_MENTIONED","SERVICES_MENTIONED","SENTIMENT","CONFIDENCE","RED_FLAGS"]
_LABEL = re.compile(r"(?im)^[\s#>*_`-]*SELF[-_ ]AUDIT[\s*_`:#-]*$|^[\s#>*_`-]*SELF[-_ ]AUDIT\b[^\n]*$")
def _field_re(): return re.compile(r"(?im)^[\s>*_`-]*\**(%s)\**\s*:\s*\**" % "|".join(FIELDS))
def parse(text):
    m = None
    for m in _LABEL.finditer(text): pass          # use the LAST label occurrence
    if not m: return text.strip(), {f: None for f in FIELDS}
    answer = text[:m.start()].rstrip(" \n-*_#>`"); block = text[m.end():]
    audit = {f: None for f in FIELDS}
    hits = list(_field_re().finditer(block))
    for i,h in enumerate(hits):
        end = hits[i+1].start() if i+1 < len(hits) else len(block)
        val = block[h.end():end].strip().strip("*_ \n")
        audit[h.group(1).upper()] = re.sub(r"\s*\n\s*", " ", val).strip(" *_")
    return answer.strip(), audit
