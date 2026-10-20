"""Streamlit interface for the sample laptop recommendation crew."""

import json
import os

import streamlit as st

from catalog import compare_prices, filter_products, load_products
from crew import run_recommendation


SECRET_NAMES = (
    "CREWAI_MODEL",
    "CREWAI_API_KEY",
    "CREWAI_BASE_URL",
    "CREWAI_TEMPERATURE",
)


def _load_streamlit_secrets():
    """Expose configured Streamlit Community Cloud secrets to the existing crew config."""
    try:
        secrets = st.secrets
        for name in SECRET_NAMES:
            value = secrets.get(name)
            if value:
                os.environ.setdefault(name, str(value))
    except Exception:
        return


def _recommendation_payload(result):
    raw = result if isinstance(result, str) else getattr(result, "raw", str(result))
    text = str(raw).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3].strip()
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None, str(raw)
    if not isinstance(payload, dict) or not isinstance(payload.get("ranked_products"), list):
        return None, str(raw)
    return payload, str(raw)


def _as_list(value):
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _display_product(product, recommendation=None, rank=None):
    recommendation = recommendation or {}
    heading = f"{rank}. {product['name']}" if rank is not None else product["name"]
    with st.container(border=True):
        st.subheader(heading)
        price = product["price_inr"]
        st.markdown(f"**Price:** INR {price:,.0f}" if price is not None else "**Price:** Not listed")
        st.write(
            f"RAM: {product['ram_gb'] if product['ram_gb'] is not None else 'Not listed'} GB · "
            f"Processor: {product['processor'] or 'Not listed'} · "
            f"Storage: {product['storage'] or 'Not listed'} · "
            f"Battery: {product['battery_life_hours'] if product['battery_life_hours'] is not None else 'Not listed'} hours · "
            f"Rating: {product['rating'] if product['rating'] is not None else 'Not listed'} / 5"
        )

        reason = recommendation.get("why_recommended")
        if reason:
            st.markdown(f"**Why recommended:** {reason}")

        advantages = _as_list(recommendation.get("advantages"))
        if not advantages:
            advantages = [feature.strip() for feature in (product["features"] or "").split(";") if feature.strip()]
        st.markdown("**Advantages**")
        if advantages:
            st.markdown("\n".join(f"- {advantage}" for advantage in advantages))
        else:
            st.write("No advantages listed in the sample catalogue.")

        disadvantages = _as_list(recommendation.get("disadvantages"))
        st.markdown("**Disadvantages / trade-offs**")
        if disadvantages:
            st.markdown("\n".join(f"- {disadvantage}" for disadvantage in disadvantages))
        else:
            st.write("No specific disadvantage was identified in the recommendation.")

        review_summary = recommendation.get("review_summary")
        st.markdown("**Sample review summary**")
        st.write(review_summary or product["customer_reviews"] or "No sample review text available.")


_load_streamlit_secrets()
st.set_page_config(page_title="Laptop Recommendations", layout="centered")



st.markdown("""
<style>
/* Main dark background */
.stApp {
    background: linear-gradient(135deg, #0b1020 0%, #111827 55%, #17152e 100%);
    color: #f1f5f9;
}

[data-testid="stHeader"] {
    background: transparent;
}

[data-testid="stAppViewContainer"] {
    background: transparent;
}

/* Main content width and spacing */
.block-container {
    max-width: 1050px;
    padding-top: 2.5rem;
    padding-bottom: 3rem;
}

/* Headings and normal text */
h1, h2, h3 {
    color: #f8fafc !important;
    letter-spacing: -0.4px;
}

p, label, .stMarkdown, [data-testid="stCaptionContainer"] {
    color: #cbd5e1;
}

/* Form and product cards */
[data-testid="stForm"],
[data-testid="stVerticalBlockBorderWrapper"] {
    background: rgba(30, 41, 59, 0.65);
    border: 1px solid #334155;
    border-radius: 16px;
}

/* Input fields and dropdowns */
.stTextInput input,
.stNumberInput input,
.stTextArea textarea,
.stSelectbox div[data-baseweb="select"] > div {
    background-color: #1e293b !important;
    color: #f8fafc !important;
    border-color: #475569 !important;
    border-radius: 9px !important;
}

/* Primary and secondary buttons */
.stButton button,
.stFormSubmitButton button {
    border-radius: 10px;
    font-weight: 600;
    min-height: 44px;
    transition: all 0.2s ease;
}

.stFormSubmitButton button[kind="primaryFormSubmit"],
.stFormSubmitButton button[kind="primary"] {
    background: linear-gradient(90deg, #6366f1, #8b5cf6);
    color: white;
    border: none;
}

.stButton button:hover,
.stFormSubmitButton button:hover {
    border-color: #a5b4fc;
    color: white;
}

/* Improve readability of product details */
[data-testid="stVerticalBlockBorderWrapper"] {
    padding: 12px;
    margin-bottom: 12px;
}

/* Links and accent text */
a {
    color: #93c5fd !important;
}

/* Keep text readable in expanders */
[data-testid="stExpander"] {
    background: #172033;
    border: 1px solid #334155;
    border-radius: 10px;
}

/* Error and information messages */
[data-testid="stAlert"] {
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

st.title("🛍️ Smart Shopping Assistant")
st.caption("AI-powered laptop recommendations tailored to your needs.")
st.info("Demo mode: Recommendations use a sample laptop catalogue, not live shopping data.")

try:
    products = load_products()
except (OSError, ValueError) as error:
    st.error(f"Could not load the sample catalogue: {error}")
    st.stop()

with st.form("recommendation_form"):
    category = st.selectbox("Product category", ["Laptop"])
    budget = st.number_input(
        "Maximum budget (INR)", min_value=0, value=75000, step=5000,
        help="Enter 0 for no budget limit.",
    )
    purpose = st.selectbox(
        "Purpose",
        ["Work", "Study", "Gaming", "Creative work", "General use", "Other"],
    )
    other_purpose = st.text_input("Describe the purpose")
    minimum_ram = st.selectbox(
        "Minimum RAM", [0, 4, 8, 16, 32, 64], index=0,
        format_func=lambda value: "No minimum" if value == 0 else f"{value} GB",
    )
    preferences = st.text_area(
        "Customer preferences",
        placeholder="For example: lightweight, long battery life, quiet operation",
    )
    submitted = st.form_submit_button("Generate recommendations", type="primary")

if submitted:
    selected_purpose = other_purpose.strip() if purpose == "Other" else purpose
    customer_request = (
        f"Category: {category}. "
        f"Maximum budget: {'no limit' if budget == 0 else f'INR {budget:,.0f}'}. "
        f"Purpose: {selected_purpose or 'not specified'}. "
        f"Minimum RAM: {'no minimum' if minimum_ram == 0 else f'{minimum_ram} GB'}. "
        f"Customer preferences: {preferences.strip() or 'none specified'}."
    )
    candidates = compare_prices(
        filter_products(
            products,
            max_budget_inr=None if budget == 0 else budget,
            min_ram_gb=None if minimum_ram == 0 else minimum_ram,
        )
    )
    st.session_state.pop("recommendation_payload", None)
    st.session_state.pop("recommendation_error", None)
    st.session_state["recommendation_request"] = customer_request
    st.session_state["matching_products"] = candidates

    if not candidates:
        st.session_state["recommendation_payload"] = {"ranked_products": []}
    elif not os.getenv("CREWAI_MODEL", "").strip():
        st.session_state["recommendation_error"] = (
            "No compatible LLM is configured. Set CREWAI_MODEL and any provider-required "
            "credentials in the environment or Streamlit Community Cloud secrets."
        )
    else:
        try:
            with st.spinner("Analyzing the sample catalogue..."):
                result = run_recommendation(customer_request)
            payload, raw = _recommendation_payload(result)
            if payload is None:
                st.session_state["recommendation_error"] = "The crew returned an unreadable recommendation response."
                st.session_state["recommendation_raw"] = raw
            else:
                st.session_state["recommendation_payload"] = payload
        except Exception as error:
            st.session_state["recommendation_error"] = f"Recommendation run failed: {error}"

if st.session_state.get("recommendation_request"):
    st.caption(f"Request: {st.session_state['recommendation_request']}")
    candidates = st.session_state.get("matching_products", [])
    if not candidates:
        st.info("No sample laptops match that budget and minimum RAM. Try relaxing one of the filters.")
    elif st.session_state.get("recommendation_error"):
        st.error(st.session_state["recommendation_error"])
        raw = st.session_state.get("recommendation_raw")
        if raw:
            with st.expander("Raw crew response"):
                st.text(raw)
        st.subheader("Matching sample products, ordered by price")
        for product in candidates:
            _display_product(product)
    else:
        payload = st.session_state.get("recommendation_payload", {})
        product_by_id = {product["product_id"]: product for product in candidates}
        ranked = []
        seen_ids = set()
        for item in payload.get("ranked_products", []):
            if not isinstance(item, dict):
                continue
            product_id = item.get("product_id")
            if product_id in product_by_id and product_id not in seen_ids:
                ranked.append((product_by_id[product_id], item))
                seen_ids.add(product_id)

        if ranked:
            st.subheader("Ranked recommendations")
            for rank, (product, item) in enumerate(ranked, start=1):
                _display_product(product, item, rank)
        else:
            st.warning("The crew found matching products but did not return a valid ranked list.")

        unranked = [product for product in candidates if product["product_id"] not in seen_ids]
        if unranked:
            st.subheader("Other matching sample products")
            for product in unranked:
                _display_product(product)