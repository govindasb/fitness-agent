import streamlit as st

from dashboard.metrics import get_dashboard_metrics
from database.connection import SessionLocal


st.set_page_config(
    page_title="Fitness Dashboard",
    page_icon="🏋️",
    layout="wide",
)

st.title("Fitness Dashboard")
st.caption("Local-first fitness metrics from your deterministic analytics layer.")

days = st.selectbox(
    "Dashboard window",
    options=[7, 14, 30],
    index=0,
    format_func=lambda value: f"Last {value} days",
)

with SessionLocal() as db:
    metrics = get_dashboard_metrics(
        db,
        days=days,
    )

goal = metrics["goal"]

st.subheader("Goal Progress")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Current Weight",
    (
        f'{goal["current_weight_kg"]:.1f} kg'
        if goal["current_weight_kg"] is not None
        else "No data"
    ),
)

col2.metric(
    "Weight Lost",
    (
        f'{goal["weight_lost_kg"]:.1f} kg'
        if goal["weight_lost_kg"] is not None
        else "No data"
    ),
)

col3.metric(
    "Remaining",
    (
        f'{goal["remaining_kg"]:.1f} kg'
        if goal["remaining_kg"] is not None
        else "No data"
    ),
)

col4.metric(
    "Goal Progress",
    (
        f'{goal["progress_percent"]:.1f}%'
        if goal["progress_percent"] is not None
        else "No data"
    ),
)

st.subheader("Data Status")

status1, status2, status3, status4 = st.columns(4)

status1.metric(
    "Weight Days",
    f'{metrics["weight"]["days_with_weight"]}/{days}',
)

status2.metric(
    "Step Days",
    f'{metrics["steps"]["logged_days"]}/{days}',
)

status3.metric(
    "Workouts",
    metrics["training"]["workout_count"],
)

status4.metric(
    "Food Logging Days",
    f'{metrics["nutrition"]["days_with_food"]}/{days}',
)
