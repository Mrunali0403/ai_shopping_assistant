"""Sequential CrewAI workflow for sample laptop recommendations."""

import json
import os

from crewai import Agent, Crew, LLM, Process, Task
from crewai.tools import tool

from catalog import compare_prices, filter_products, load_products


def _select_products(product_ids):
    """Resolve requested IDs against the bundled sample catalog."""
    products_by_id = {product["product_id"]: product for product in load_products()}
    requested_ids = list(dict.fromkeys(str(product_id).strip() for product_id in product_ids))
    unknown_ids = [product_id for product_id in requested_ids if product_id not in products_by_id]
    if unknown_ids:
        return None, unknown_ids
    return [products_by_id[product_id] for product_id in requested_ids], []


@tool("search_sample_products")
def search_sample_products(max_budget_inr: float, min_ram_gb: int) -> str:
    """Filter the sample CSV in Python; use -1 for no budget and 0 for no RAM minimum."""
    try:
        products = filter_products(
            load_products(),
            max_budget_inr=None if max_budget_inr < 0 else max_budget_inr,
            min_ram_gb=None if min_ram_gb == 0 else min_ram_gb,
        )
    except ValueError as error:
        return json.dumps({"error": str(error)})
    return json.dumps(products, ensure_ascii=False)


@tool("compare_sample_product_prices")
def compare_sample_product_prices(product_ids: list[str]) -> str:
    """Sort selected sample products by CSV price and calculate the price spread in Python."""
    products, unknown_ids = _select_products(product_ids)
    if unknown_ids:
        return json.dumps({"error": "Unknown sample product IDs", "product_ids": unknown_ids})

    sorted_products = compare_prices(products)
    prices = [product["price_inr"] for product in sorted_products if product["price_inr"] is not None]
    result = {
        "products_by_price_ascending": sorted_products,
        "lowest_price_inr": min(prices) if prices else None,
        "highest_price_inr": max(prices) if prices else None,
        "price_spread_inr": max(prices) - min(prices) if prices else None,
    }
    return json.dumps(result, ensure_ascii=False)


@tool("get_sample_product_reviews")
def get_sample_product_reviews(product_ids: list[str]) -> str:
    """Return the existing sample ratings and review text for selected CSV product IDs."""
    products, unknown_ids = _select_products(product_ids)
    if unknown_ids:
        return json.dumps({"error": "Unknown sample product IDs", "product_ids": unknown_ids})

    reviews = [
        {
            "product_id": product["product_id"],
            "name": product["name"],
            "rating": product["rating"],
            "customer_reviews": product["customer_reviews"],
        }
        for product in products
    ]
    return json.dumps(reviews, ensure_ascii=False)


def _configured_llm():
    model = os.getenv("CREWAI_MODEL", "").strip()
    if not model:
        raise RuntimeError("Set CREWAI_MODEL to a compatible provider/model identifier before creating the crew")

    try:
        temperature = float(os.getenv("CREWAI_TEMPERATURE", "0"))
    except ValueError as error:
        raise ValueError("CREWAI_TEMPERATURE must be a number between 0 and 2") from error
    if not 0 <= temperature <= 2:
        raise ValueError("CREWAI_TEMPERATURE must be between 0 and 2")

    config = {"model": model, "temperature": temperature, "custom_openai": True}
    api_key = os.getenv("CREWAI_API_KEY", "").strip()
    base_url = os.getenv("CREWAI_BASE_URL", "").strip()
    if api_key:
        config["api_key"] = api_key
    if base_url:
        config["base_url"] = base_url
    return LLM(**config)


def create_crew():
    """Build the five-agent sequential crew without making a model request."""
    shared_llm = _configured_llm()
    common_agent_settings = {
        "llm": shared_llm,
        "allow_delegation": False,
        "max_iter": 2,
        "verbose": False,
    }

    requirement_agent = Agent(
        role="Customer Requirement Agent",
        goal="Extract explicit laptop constraints and preferences from the customer request.",
        backstory="You distinguish hard constraints from preferences and never invent missing requirements.",
        **common_agent_settings,
    )
    product_search_agent = Agent(
        role="Product Search Agent",
        goal="Find every sample laptop matching the extracted budget and RAM constraints.",
        backstory="You rely on the Python catalog filter and do not invent or silently omit matching products.",
        tools=[search_sample_products],
        **common_agent_settings,
    )
    price_comparison_agent = Agent(
        role="Price Comparison Agent",
        goal="Compare candidate prices using the deterministic Python price tool.",
        backstory="You report calculated prices and price spread without estimating or changing values.",
        tools=[compare_sample_product_prices],
        **common_agent_settings,
    )
    review_analysis_agent = Agent(
        role="Review Analysis Agent",
        goal="Summarize the sample customer reviews for the candidate laptops.",
        backstory="You use only the supplied CSV review text and distinguish evidence from inference.",
        tools=[get_sample_product_reviews],
        **common_agent_settings,
    )
    recommendation_agent = Agent(
        role="Recommendation Agent",
        goal="Rank matching laptops and explain their trade-offs against the customer's priorities.",
        backstory="You ground recommendations in the candidate data, calculated prices, and sample reviews.",
        **common_agent_settings,
    )

    requirement_task = Task(
        description=(
            "Extract requirements from this customer request: {customer_request}\n"
            "Return valid JSON with max_budget_inr and min_ram_gb as numbers or null, plus arrays "
            "for priorities, hard_constraints, and uncertainties. Preserve only explicitly stated constraints."
        ),
        expected_output="A JSON object of explicit constraints and preferences; unknown numeric limits are null.",
        agent=requirement_agent,
    )
    product_search_task = Task(
        description=(
            "Use the requirement JSON in context. You MUST call search_sample_products exactly once. "
            "Pass -1 for a null budget and 0 for a null RAM minimum. Return the tool's complete matching "
            "sample product list without adding or removing products."
        ),
        expected_output="The complete JSON list returned by the Python sample-catalog filter.",
        agent=product_search_agent,
        context=[requirement_task],
    )
    price_comparison_task = Task(
        description=(
            "Use the candidate list in context. You MUST call compare_sample_product_prices with the "
            "candidate product_id values. Report its ascending price order, lowest and highest prices, "
            "and calculated price spread; do not do arithmetic yourself."
        ),
        expected_output="The Python-calculated price comparison for the candidate product IDs.",
        agent=price_comparison_agent,
        context=[requirement_task, product_search_task],
    )
    review_analysis_task = Task(
        description=(
            "Use the candidate list in context. You MUST call get_sample_product_reviews with the "
            "candidate product_id values. Summarize only the returned ratings and sample review text; "
            "do not claim these are verified real-world reviews."
        ),
        expected_output="A concise, evidence-based review summary for the candidate products.",
        agent=review_analysis_agent,
        context=[requirement_task, product_search_task, price_comparison_task],
    )
    recommendation_task = Task(
        description=(
            "Rank the matching candidates for the customer using the requirements, product results, "
            "Python price comparison, and review analysis in context. Explain meaningful trade-offs "
            "and cite product names and INR prices. If there are no matching candidates, say so and "
            "do not recommend a non-matching product. Return only valid JSON with this shape: "
            "{\"ranked_products\":[{\"product_id\":\"sample CSV ID\",\"why_recommended\":\"...\","
            "\"advantages\":[\"...\"],\"disadvantages\":[\"...\"],"
            "\"review_summary\":\"...\"}]}. Include every matching candidate exactly once, "
            "in recommendation order. Use only product IDs and facts present in the supplied "
            "catalogue and review context; do not invent review details."
        ),
        expected_output="Valid JSON containing every matching product in rank order with rationale, pros, cons, and a sample review summary.",
        agent=recommendation_agent,
        context=[requirement_task, product_search_task, price_comparison_task, review_analysis_task],
    )

    return Crew(
        agents=[
            requirement_agent,
            product_search_agent,
            price_comparison_agent,
            review_analysis_agent,
            recommendation_agent,
        ],
        tasks=[
            requirement_task,
            product_search_task,
            price_comparison_task,
            review_analysis_task,
            recommendation_task,
        ],
        process=Process.sequential,
        verbose=False,
    )


def run_recommendation(customer_request):
    """Execute the sequential crew for one customer request."""
    if not isinstance(customer_request, str) or not customer_request.strip():
        raise ValueError("customer_request must be a non-empty string")
    return create_crew().kickoff(inputs={"customer_request": customer_request.strip()})