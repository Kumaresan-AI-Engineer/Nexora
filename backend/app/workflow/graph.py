"""The single LangGraph orchestrator.

Order differs slightly from the brief: deduplicate_offers runs before verification so evidence from
repeated listings is merged (and conflicts surface) *before* the verification rules run.
"""

from langgraph.graph import END, START, StateGraph

from app.workflow import nodes as n
from app.workflow.state import GraphState


def build_graph():
    g = StateGraph(GraphState)
    for fn in (
        n.validate_request,
        n.analyze_image,
        n.resolve_product_identity,
        n.check_identity_ambiguity,
        n.discover_supplier_sources,
        n.search_supplier_connectors,
        n.extract_and_normalize_offers,
        n.deduplicate_offers,
        n.verify_offer_evidence,
        n.calculate_comparable_costs,
        n.rank_eligible_offers,
        n.finalize_results,
    ):
        g.add_node(fn.__name__, fn)

    g.add_edge(START, "validate_request")
    g.add_conditional_edges(
        "validate_request",
        n.route_after_validate,
        ["finalize_results", "check_identity_ambiguity", "analyze_image"],
    )
    g.add_conditional_edges(
        "analyze_image", n.route_after_analyze, ["finalize_results", "resolve_product_identity"]
    )
    g.add_edge("resolve_product_identity", "check_identity_ambiguity")
    g.add_conditional_edges(
        "check_identity_ambiguity",
        n.route_after_ambiguity,
        ["finalize_results", "discover_supplier_sources"],
    )
    g.add_edge("discover_supplier_sources", "search_supplier_connectors")
    g.add_conditional_edges(
        "search_supplier_connectors",
        n.route_after_search,
        ["extract_and_normalize_offers", "finalize_results"],
    )
    g.add_edge("extract_and_normalize_offers", "deduplicate_offers")
    g.add_edge("deduplicate_offers", "verify_offer_evidence")
    g.add_edge("verify_offer_evidence", "calculate_comparable_costs")
    g.add_edge("calculate_comparable_costs", "rank_eligible_offers")
    g.add_edge("rank_eligible_offers", "finalize_results")
    g.add_edge("finalize_results", END)
    return g.compile()
