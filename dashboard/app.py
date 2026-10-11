"""RentCast Ireland: multipage Streamlit app entry point."""

from pathlib import Path

import streamlit as st

st.set_page_config(page_title="RentCast Ireland", page_icon="🏠", layout="wide")

VIEWS = Path(__file__).parent / "views"
pages = {
    "map": st.Page(VIEWS / "map.py", title="Map", icon="🗺️", default=True),
    "explorer": st.Page(VIEWS / "explorer.py", title="Forecast explorer", icon="🔎"),
    "afford": st.Page(VIEWS / "afford.py", title="Where can I afford?", icon="💶"),
    "compare": st.Page(VIEWS / "compare.py", title="Compare areas", icon="⚖️"),
    "league": st.Page(VIEWS / "league.py", title="League table", icon="🏆"),
    "model": st.Page(VIEWS / "model.py", title="Model performance", icon="📊"),
}
st.session_state["pages"] = pages

nav = st.navigation(list(pages.values()))
with st.sidebar:
    st.caption(
        "Data: RTB Rent Index via CSO (RIQ02), Property Price Register, Tailte Éireann boundaries "
        "(CC BY 4.0). Forecasts are estimates, not financial advice."
    )
nav.run()
