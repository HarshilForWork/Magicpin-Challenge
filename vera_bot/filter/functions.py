def _lower(s):
    return s.lower() if isinstance(s, str) else ""


def _match_text(item, keys, keyword):
    if not keyword:
        return False
    kw = _lower(keyword)
    for k in keys:
        v = item.get(k)
        if isinstance(v, str) and kw in _lower(v):
            return True
    return False


def _pick_first(items):
    return items[0] if items else None


def _pick_digest(category, kind=None, item_id=None, keyword=None):
    items = category.get("digest") or []
    if item_id:
        items = [d for d in items if d.get("id") == item_id]
    if kind:
        items = [d for d in items if d.get("kind") == kind]
    if keyword:
        items = [d for d in items if _match_text(d, ["title", "summary", "source", "actionable"], keyword)]
    return items[:1]


def _pick_offer(category, merchant, audience=None, types=None):
    offers = category.get("offer_catalog") or []
    if audience:
        offers = [o for o in offers if o.get("audience") == audience or o.get("audience") == "all"]
    if types:
        offers = [o for o in offers if o.get("type") in types]
    if offers:
        return offers[:2]
    merchant_offers = [o for o in (merchant.get("offers") or []) if o.get("status") == "active"]
    return merchant_offers[:2]


def _pick_content(category, keyword=None):
    items = category.get("patient_content_library") or []
    if keyword:
        items = [c for c in items if _match_text(c, ["title", "body"], keyword)]
    return items[:1]


def _pick_seasonal(category, keyword=None):
    items = category.get("seasonal_beats") or []
    if keyword:
        items = [s for s in items if _match_text(s, ["month_range", "note"], keyword)]
    return items[:1]


def _pick_trend(category, keyword=None):
    items = category.get("trend_signals") or []
    if keyword:
        items = [t for t in items if _match_text(t, ["query", "segment_age", "skew"], keyword)]
    return items[:1]


def _pick_peer_stats(category: dict, keys: list[str] = None) -> dict:
    stats = category.get("peer_stats") or {}
    if keys:
        return {k: stats[k] for k in keys if k in stats}
    return stats


def filter_for_research_digest(category, merchant, trigger, customer):
    payload = trigger.get("payload") or {}
    digest = _pick_digest(category, kind="research", item_id=payload.get("top_item_id"))
    offers = []
    ctr = (merchant.get("performance") or {}).get("ctr")
    avg_ctr = (category.get("peer_stats") or {}).get("avg_ctr")
    if isinstance(ctr, (int, float)) and isinstance(avg_ctr, (int, float)) and ctr < avg_ctr:
        offers = _pick_offer(category, merchant, audience="new_user",
                             types={"service_at_price", "free_service", "free_trial"})
    content = _pick_content(category, keyword=payload.get("metric_or_topic"))
    peer_stats = _pick_peer_stats(category, ["avg_ctr", "avg_rating", "avg_reviews"])
    return {"digest": digest, "offers": offers, "content": content, "peer_stats": peer_stats}


def filter_for_regulation_change(category, merchant, trigger, customer):
    payload = trigger.get("payload") or {}
    digest = _pick_digest(category, kind="compliance", item_id=payload.get("top_item_id"))
    return {"digest": digest}


def filter_for_cde_opportunity(category, merchant, trigger, customer):
    payload = trigger.get("payload") or {}
    digest = _pick_digest(category, kind="cde", item_id=payload.get("digest_item_id"))
    return {"digest": digest}


def filter_for_perf_dip(category, merchant, trigger, customer):
    digest = _pick_digest(category, kind="tech") or _pick_digest(category, kind="trend")
    offers = _pick_offer(category, merchant, audience="new_user",
                         types={"service_at_price", "free_service", "free_trial"})
    content = _pick_content(category)
    peer_stats = _pick_peer_stats(category, ["avg_ctr", "avg_rating", "avg_reviews"])
    return {"digest": digest, "offers": offers, "content": content, "peer_stats": peer_stats}


def filter_for_perf_spike(category, merchant, trigger, customer):
    digest = _pick_digest(category, kind="trend") or _pick_digest(category, kind="tech")
    offers = _pick_offer(category, merchant, audience="repeat_user") or _pick_offer(category, merchant, audience="new_user")
    return {"digest": digest, "offers": offers}


def filter_for_renewal_due(category, merchant, trigger, customer):
    offers = [o for o in (merchant.get("offers") or []) if o.get("status") == "active"][:2]
    return {"offers": offers}


def filter_for_festival_upcoming(category, merchant, trigger, customer):
    payload = trigger.get("payload") or {}
    digest = _pick_digest(category, kind="seasonal")
    seasonal = _pick_seasonal(category, keyword=payload.get("festival"))
    offers = _pick_offer(category, merchant, audience="new_user", types={"service_at_price"})
    content = _pick_content(category)
    return {"digest": digest, "seasonal": seasonal, "offers": offers, "content": content}


def filter_for_category_seasonal(category, merchant, trigger, customer):
    payload = trigger.get("payload") or {}
    seasonal = _pick_seasonal(category, keyword=payload.get("season"))
    digest = _pick_digest(category, kind="seasonal")
    offers = _pick_offer(category, merchant, audience="new_user")
    return {"seasonal": seasonal, "digest": digest, "offers": offers}


def filter_for_seasonal_perf_dip(category, merchant, trigger, customer):
    payload = trigger.get("payload") or {}
    seasonal = _pick_seasonal(category, keyword=payload.get("season_note"))
    offers = _pick_offer(category, merchant, audience="new_user", types={"service_at_price"})
    return {"seasonal": seasonal, "offers": offers}


def filter_for_review_theme_emerged(category, merchant, trigger, customer):
    offers = _pick_offer(category, merchant, audience="new_user")
    return {"offers": offers}


def filter_for_milestone_reached(category, merchant, trigger, customer):
    offers = _pick_offer(category, merchant, audience="repeat_user") or _pick_offer(category, merchant, audience="new_user")
    return {"offers": offers}


def filter_for_competitor_opened(category, merchant, trigger, customer):
    offers = _pick_offer(category, merchant, audience="new_user", types={"service_at_price"})
    digest = _pick_digest(category, kind="trend")
    return {"offers": offers, "digest": digest}


def filter_for_gbp_unverified(category, merchant, trigger, customer):
    return {}


def filter_for_active_planning_intent(category, merchant, trigger, customer):
    offers = [o for o in (merchant.get("offers") or []) if o.get("status") == "active"][:2]
    if not offers:
        offers = _pick_offer(category, merchant, audience="new_user")
    return {"offers": offers}


def filter_for_curious_ask_due(category, merchant, trigger, customer):
    return {}


def filter_for_dormant_with_vera(category, merchant, trigger, customer):
    digest = _pick_digest(category)
    offers = _pick_offer(category, merchant, audience="new_user")
    return {"digest": digest, "offers": offers}


def filter_for_winback_eligible(category, merchant, trigger, customer):
    offers = _pick_offer(category, merchant, audience="repeat_user") or _pick_offer(category, merchant, audience="new_user")
    content = _pick_content(category)
    return {"offers": offers, "content": content}


def filter_for_ipl_match_today(category, merchant, trigger, customer):
    offers = _pick_offer(category, merchant, audience="new_user", types={"service_at_price"})
    trends = _pick_trend(category, keyword="near me")
    return {"offers": offers, "trends": trends}


def filter_for_supply_alert(category, merchant, trigger, customer):
    return {}


def filter_for_recall_due(category, merchant, trigger, customer):
    offers = _pick_offer(category, merchant, audience="new_user", types={"service_at_price", "free_service"})
    content = _pick_content(category, keyword=(trigger.get("payload") or {}).get("service_due"))
    return {"offers": offers, "content": content}


def filter_for_appointment_tomorrow(category, merchant, trigger, customer):
    return {}


def filter_for_customer_lapsed_soft(category, merchant, trigger, customer):
    offers = _pick_offer(category, merchant, audience="repeat_user") or _pick_offer(category, merchant, audience="new_user")
    content = _pick_content(category)
    return {"offers": offers, "content": content}


def filter_for_customer_lapsed_hard(category, merchant, trigger, customer):
    offers = _pick_offer(category, merchant, audience="repeat_user") or _pick_offer(category, merchant, audience="new_user")
    content = _pick_content(category)
    return {"offers": offers, "content": content}


def filter_for_trial_followup(category, merchant, trigger, customer):
    offers = _pick_offer(category, merchant, audience="new_user", types={"service_at_price", "free_trial"})
    content = _pick_content(category)
    return {"offers": offers, "content": content}


def filter_for_wedding_package_followup(category, merchant, trigger, customer):
    offers = _pick_offer(category, merchant, audience="new_user", types={"service_at_price"})
    content = _pick_content(category)
    return {"offers": offers, "content": content}


def filter_for_chronic_refill_due(category, merchant, trigger, customer):
    return {}
