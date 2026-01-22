import streamlit as st
from agent.tools import search_catalog, parse_constraints, filter_results

st.set_page_config(page_title="Agentic Shopping Assistant", layout="wide")
st.title("🛍️ Agentic Shopping Assistant (Fashion)")

query = st.text_input(
    "What are you shopping for?", "winter wedding guest dress under $150"
)
top_k = st.slider("Number of results", 3, 12, 8)

if st.button("Search catalog"):
    constraints = parse_constraints(query)
    st.subheader("Parsed constraints")
    st.json(
        {
            "budget_max": constraints.budget_max,
            "colors": constraints.colors,
            "categories": constraints.categories,
        }
    )

    results = search_catalog(query, top_k=top_k)
    filtered = filter_results(results, constraints)

    if not filtered:
        st.warning("No matches found after applying constraints.")
    else:
        st.subheader("Results (after constraints)")
        for res in filtered:
            item = res.item
            with st.container(border=True):
                st.markdown(
                    f"**{item['title']}**  \n*{item['brand']}* — **${item['price_usd']:.2f}**"
                )
                st.caption(
                    f"Category: {item['category']} • Rating: {item.get('rating', 'N/A')} ({item.get('num_reviews', 0)} reviews)"
                )
                st.write(item["description"])
                st.write("Matched terms:", ", ".join(res.matched_terms))
