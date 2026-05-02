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

    identity = merchant.get("identity", {}) or {}
    performance = merchant.get("performance", {}) or {}
    subscription = merchant.get("subscription", {}) or {}
    customer_agg = merchant.get("customer_aggregate", {}) or {}

    review_summary = []
    for item in (merchant.get("review_themes") or [])[:2]:
        if isinstance(item, dict):
            review_summary.append({
                "theme": item.get("theme"),
                "sentiment": item.get("sentiment"),
                "occurrences_30d": item.get("occurrences_30d"),
                "common_quote": item.get("common_quote"),
            })

    # Merchant -- only the fields the LLM needs
    ctx["merchant"] = _clean({
        "name": identity.get("name"),
        "owner_first_name": identity.get("owner_first_name"),
        "locality": identity.get("locality"),
        "city": identity.get("city"),
        "languages": identity.get("languages"),
        "verified": identity.get("verified"),
        "established_year": identity.get("established_year"),
        "signals": merchant.get("signals"),
        "ctr": performance.get("ctr"),
        "performance": {
            "views": performance.get("views"),
            "calls": performance.get("calls"),
            "directions": performance.get("directions"),
            "leads": performance.get("leads"),
            "ctr": performance.get("ctr"),
            "delta_7d": performance.get("delta_7d"),
            "window_days": performance.get("window_days"),
        },
        "subscription": {
            "status": subscription.get("status"),
            "plan": subscription.get("plan"),
            "days_remaining": subscription.get("days_remaining"),
            "days_since_expiry": subscription.get("days_since_expiry"),
            "renewed_at": subscription.get("renewed_at"),
        },
        "customer_aggregate": {
            "total_unique_ytd": customer_agg.get("total_unique_ytd"),
            "total_active_members": customer_agg.get("total_active_members"),
            "lapsed_90d_plus": customer_agg.get("lapsed_90d_plus"),
            "lapsed_180d_plus": customer_agg.get("lapsed_180d_plus"),
            "retention_3mo_pct": customer_agg.get("retention_3mo_pct"),
            "retention_6mo_pct": customer_agg.get("retention_6mo_pct"),
            "repeat_customer_pct": customer_agg.get("repeat_customer_pct"),
            "monthly_churn_pct": customer_agg.get("monthly_churn_pct"),
            "delivery_orders_30d": customer_agg.get("delivery_orders_30d"),
            "dine_in_orders_30d": customer_agg.get("dine_in_orders_30d"),
            "delivery_share_pct": customer_agg.get("delivery_share_pct"),
            "trial_to_paid_pct": customer_agg.get("trial_to_paid_pct"),
            "high_risk_adult_count": customer_agg.get("high_risk_adult_count"),
            "chronic_rx_count": customer_agg.get("chronic_rx_count"),
        },
        "review_themes": review_summary,
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
