from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import re

@dataclass
class CatalogCandidate:
    display_name: str
    score: float
    fields: dict[str, Any]
    reasons: list[str]


def norm(v: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(v or "").lower()).strip()


def rank_catalog(extracted: dict[str, dict[str, Any]], rows: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    """Rank known catalog/collection identities against vision extraction.

    This is deliberately deterministic: it never invents a card. It boosts exact
    card-number/player/product/season matches and penalizes conflicting parallels.
    """
    vals={k:(v or {}).get('value') for k,v in extracted.items()}
    weights={
        'card_number_printed':4.0,'primary_subject_name':4.0,'product_line':3.0,
        'season':2.5,'manufacturer':1.5,'set_name':2.0,'parallel_name':3.5,
        'variation_name':3.0,'team_name':1.0,'insert_name':2.0,
    }
    out=[]
    for row in rows:
        score=0.0; possible=0.0; reasons=[]; conflicts=[]
        for f,w in weights.items():
            a,b=norm(vals.get(f)),norm(row.get(f))
            if not a: continue
            possible += w
            if a and b and a==b:
                score += w; reasons.append(f"{f}: exakt")
            elif a and b and (a in b or b in a):
                score += w*0.65; reasons.append(f"{f}: ähnlich")
            elif f in {'card_number_printed','parallel_name','variation_name'} and b:
                score -= w*0.55; conflicts.append(f)
        if possible <= 0: continue
        normalized=max(0.0,min(1.0,score/possible))
        if normalized >= .35:
            name=' · '.join(str(x) for x in [row.get('primary_subject_name'),row.get('season'),row.get('product_line'),row.get('card_number_printed'),row.get('parallel_name')] if x)
            out.append({'display_name':name or 'Katalogtreffer','score':round(normalized,3),'fields':{k:row.get(k) for k in weights if row.get(k) not in (None,'')},'reasons':reasons,'conflicts':conflicts})
    return sorted(out,key=lambda x:x['score'],reverse=True)[:limit]
