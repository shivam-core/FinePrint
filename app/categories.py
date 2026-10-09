# app/categories.py
CATEGORY_MAPPING = {
    0: "Limitation of liability",
    1: "Unilateral termination",
    2: "Unilateral change",
    3: "Content removal",
    4: "Contract by using",
    5: "Choice of law",
    6: "Jurisdiction",
    7: "Arbitration"
}

CATEGORY_CONTEXT = {
    0: "may restrict responsibility or available compensation.",
    1: "may allow the provider to end access with broad discretion.",
    2: "may allow changes to the agreement without individual negotiation.",
    3: "may give the provider broad removal discretion.",
    4: "may treat use of the service as acceptance.",
    5: "identifies which legal system governs the agreement.",
    6: "identifies where disputes must be brought.",
    7: "may direct disputes into arbitration instead of court."
}

def get_category_context(cat_id: int) -> str:
    ctx = CATEGORY_CONTEXT.get(cat_id, "")
    return ctx + " The model matched patterns associated with this category; the clause's effect depends on full context."
