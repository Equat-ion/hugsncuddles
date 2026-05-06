from langgraph.graph import END, StateGraph
from agent.state import GraftState
from agent.nodes import reader, planner, test_auditor, coder, pr_writer

MAX_RETRIES = 5


def route_after_coder(state: GraftState) -> str:
    if state["test_results_current"]["passed"]:
        return "pr_writer"
    if state["retry_count"] >= MAX_RETRIES:
        return "escalate"
    return "coder"


def escalate_node(state: GraftState):
    return {"status": "escalate"}


def build_graph(checkpointer):
    g = StateGraph(GraftState)

    g.add_node("reader", reader.run)
    g.add_node("planner", planner.run)
    g.add_node("test_auditor", test_auditor.run)
    g.add_node("coder", coder.run)
    g.add_node("pr_writer", pr_writer.run)
    g.add_node("escalate", escalate_node)

    g.set_entry_point("reader")
    g.add_edge("reader", "planner")
    g.add_edge("planner", "test_auditor")
    g.add_edge("test_auditor", "coder")

    g.add_conditional_edges(
        "coder",
        route_after_coder,
        {"coder": "coder", "pr_writer": "pr_writer", "escalate": "escalate"},
    )

    g.add_edge("pr_writer", END)
    g.add_edge("escalate", END)
    return g.compile(checkpointer=checkpointer)
