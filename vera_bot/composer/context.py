from toon import encode


def _clean(data):
    """Recursively strip None values and empty containers before encoding."""
    if isinstance(data, dict):
        return {
            k: _clean(v)
            for k, v in data.items()
            if v is not None and v != [] and v != {}
        }
    if isinstance(data, list):
        cleaned = [_clean(i) for i in data if i is not None]
        return cleaned if cleaned else None
    return data


def build_toon_context(
    filtered: dict,
    merchant: dict,
    trigger: dict,
    customer: dict | None,
    history: list[dict],
    max_history_turns: int = 6,
) -> str:
    """
    Assembles all context sections into a single TOON string for the LLM.
    Uses python-toon's encode() -- no custom serializer needed.

    Input:  {"name": "Dr. Meera", "ctr": 0.021, "signals": ["stale_posts"]}
    Output (via encode):
      name: Dr. Meera
      ctr: 0.021
      signals[1]: stale_posts

    None/empty values are stripped before encoding so they never appear in prompts.
    """
    ctx: dict = {}

    # Merchant -- only the fields the LLM needs
    ctx["merchant"] = _clean({
        "name": merchant.get("identity", {}).get("name"),
        "locality": merchant.get("identity", {}).get("locality"),
        "city": merchant.get("identity", {}).get("city"),
        "languages": merchant.get("identity", {}).get("languages"),
        "ctr": merchant.get("performance", {}).get("ctr"),
        "signals": merchant.get("signals"),
        "subscription_days_remaining": merchant.get("subscription", {}).get("days_remaining"),
        "lapsed_patients": merchant.get("customer_aggregate", {}).get("lapsed_180d_plus"),
        "high_risk_adult_count": merchant.get("customer_aggregate", {}).get("high_risk_adult_count"),
    })

    # Trigger
    ctx["trigger"] = _clean({
        "kind": trigger.get("kind"),
        "urgency": trigger.get("urgency"),
        **(trigger.get("payload") or {}),
    })

    # Filtered sections -- only add keys that have data
    if filtered.get("digest"):
        ctx["relevant_research"] = _clean(filtered["digest"])
    if filtered.get("offers"):
        ctx["available_offers"] = _clean(filtered["offers"])
    if filtered.get("content"):
        ctx["patient_content"] = _clean(filtered["content"])
    if filtered.get("seasonal"):
        ctx["seasonal_context"] = _clean(filtered["seasonal"])
    if filtered.get("peer_stats"):
        ctx["peer_benchmarks"] = _clean(filtered["peer_stats"])

    # Customer (only for customer-scoped triggers)
    if customer:
        ctx["customer"] = _clean({
            "name": customer.get("identity", {}).get("name"),
            "language": customer.get("identity", {}).get("language_pref"),
            "state": customer.get("state"),
            "last_visit": customer.get("relationship", {}).get("last_visit"),
            "preferred_slots": customer.get("preferences", {}).get("preferred_slots"),
        })

    # encode() from python-toon converts the full context dict to TOON string
    toon_str = encode(ctx)

    # Append conversation history as plain labelled turns after the TOON block
    parts = [toon_str.rstrip()]
    if history:
        recent = history[-max_history_turns:]
        lines = [
            f"  {t.get('role', '?').upper()}: {t.get('body', '')}"
            for t in recent
        ]
        parts.append("conversation_so_far:\n" + "\n".join(lines))

    return "\n\n".join(parts)
