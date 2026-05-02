from filter.functions import (
    filter_for_research_digest,
    filter_for_regulation_change,
    filter_for_cde_opportunity,
    filter_for_perf_dip,
    filter_for_perf_spike,
    filter_for_renewal_due,
    filter_for_festival_upcoming,
    filter_for_category_seasonal,
    filter_for_seasonal_perf_dip,
    filter_for_review_theme_emerged,
    filter_for_milestone_reached,
    filter_for_competitor_opened,
    filter_for_gbp_unverified,
    filter_for_active_planning_intent,
    filter_for_curious_ask_due,
    filter_for_dormant_with_vera,
    filter_for_winback_eligible,
    filter_for_ipl_match_today,
    filter_for_supply_alert,
    filter_for_recall_due,
    filter_for_appointment_tomorrow,
    filter_for_customer_lapsed_soft,
    filter_for_customer_lapsed_hard,
    filter_for_trial_followup,
    filter_for_wedding_package_followup,
    filter_for_chronic_refill_due,
)

FILTER_MAP = {
    "research_digest": filter_for_research_digest,
    "regulation_change": filter_for_regulation_change,
    "cde_opportunity": filter_for_cde_opportunity,
    "perf_dip": filter_for_perf_dip,
    "perf_spike": filter_for_perf_spike,
    "renewal_due": filter_for_renewal_due,
    "festival_upcoming": filter_for_festival_upcoming,
    "category_seasonal": filter_for_category_seasonal,
    "seasonal_perf_dip": filter_for_seasonal_perf_dip,
    "review_theme_emerged": filter_for_review_theme_emerged,
    "milestone_reached": filter_for_milestone_reached,
    "competitor_opened": filter_for_competitor_opened,
    "gbp_unverified": filter_for_gbp_unverified,
    "active_planning_intent": filter_for_active_planning_intent,
    "curious_ask_due": filter_for_curious_ask_due,
    "dormant_with_vera": filter_for_dormant_with_vera,
    "winback_eligible": filter_for_winback_eligible,
    "ipl_match_today": filter_for_ipl_match_today,
    "supply_alert": filter_for_supply_alert,
    "recall_due": filter_for_recall_due,
    "appointment_tomorrow": filter_for_appointment_tomorrow,
    "customer_lapsed_soft": filter_for_customer_lapsed_soft,
    "customer_lapsed_hard": filter_for_customer_lapsed_hard,
    "trial_followup": filter_for_trial_followup,
    "wedding_package_followup": filter_for_wedding_package_followup,
    "chronic_refill_due": filter_for_chronic_refill_due,
}


def route_filter(category: dict, merchant: dict, trigger: dict, customer: dict | None) -> dict:
    kind = trigger.get("kind", "")
    fn = FILTER_MAP.get(kind)
    if fn:
        return fn(category, merchant, trigger, customer)
    return {}
