import streamlit as st
import pandas as pd
import pickle
import holidays
import plotly.graph_objects as go

# =========================
# Page Configuration
# =========================
st.set_page_config(
    page_title="Future Banknotes Forecast",
    layout="wide"
)

st.title("Future Banknotes Circulation Forecast")
st.write(
    "This application forecasts Malaysia’s future banknotes circulation using SARIMAX models "
    "with holiday-related variables."
)

# =========================
# Load Historical Data
# =========================
df = pd.read_csv("df_banknotes_all_streamlit.csv")
df["date"] = pd.to_datetime(df["date"])
df = df.set_index("date")

# =========================
# Mappings
# =========================
note_cols = {
    "RM1": "note_1",
    "RM5": "note_5",
    "RM10": "note_10",
    "RM20": "note_20",
    "RM50": "note_50",
    "RM100": "note_100"
}

denom_value = {
    "RM1": 1,
    "RM5": 5,
    "RM10": 10,
    "RM20": 20,
    "RM50": 50,
    "RM100": 100
}

model_paths = {
    "RM1": "saved_models/RM1_sarimax.pkl",
    "RM5": "saved_models/RM5_sarimax.pkl",
    "RM10": "saved_models/RM10_sarimax.pkl",
    "RM20": "saved_models/RM20_sarimax.pkl",
    "RM50": "saved_models/RM50_sarimax.pkl",
    "RM100": "saved_models/RM100_sarimax.pkl"
}

# =========================
# Create Future Holiday Features
# =========================
def create_future_exog(start_date, end_date):
    future_dates = pd.date_range(start=start_date, end=end_date, freq="MS")
    future_exog = pd.DataFrame(index=future_dates)

    years = range(start_date.year, end_date.year + 1)
    my_holidays = holidays.MY(years=years)

    future_exog["holiday_count"] = 0
    future_exog["hari_raya"] = 0
    future_exog["cny"] = 0

    holiday_month_count = {}

    for date in my_holidays:
        month_key = (date.year, date.month)
        holiday_month_count[month_key] = holiday_month_count.get(month_key, 0) + 1

    for idx in future_exog.index:
        future_exog.loc[idx, "holiday_count"] = holiday_month_count.get(
            (idx.year, idx.month), 0
        )

    for date, name in my_holidays.items():
        holiday_name = str(name).lower()

        idx = future_exog[
            (future_exog.index.year == date.year) &
            (future_exog.index.month == date.month)
        ].index

        # Hari Raya Aidilfitri / Hari Raya Puasa
        if (
            "hari raya puasa" in holiday_name
            or "hari raya aidilfitri" in holiday_name
            or "eid al-fitr" in holiday_name
        ):
            future_exog.loc[idx, "hari_raya"] = 1

        # Chinese New Year / Tahun Baharu Cina
        if (
            "tahun baharu cina" in holiday_name
            or "chinese new year" in holiday_name
        ):
            future_exog.loc[idx, "cny"] = 1

    return future_exog

# =========================
# Sidebar
# =========================
st.sidebar.header("Forecast Settings")

year = st.sidebar.selectbox(
    "Select Forecast Year",
    list(range(2026, 2031)),
    index=3
)

month = st.sidebar.selectbox(
    "Select Forecast Month",
    list(range(1, 13)),
    index=1
)

predict_button = st.sidebar.button("Predict Forecast")

# =========================
# Prediction
# =========================
if predict_button:
    last_date = df.index.max()
    future_start = last_date + pd.DateOffset(months=1)
    future_end = pd.Timestamp(year=year, month=month, day=1)

    if future_end <= last_date:
        st.error("Please select a future month after the latest available data.")
        st.stop()

    future_exog = create_future_exog(future_start, future_end)

    all_forecasts = {}
    summary_rows = []

    for denom, note_col in note_cols.items():
        with open(model_paths[denom], "rb") as f:
            model_package = pickle.load(f)

        model = model_package["model"]
        exog_cols = model_package["exog_cols"]

        forecast = model.forecast(
            steps=len(future_exog),
            exog=future_exog[exog_cols]
        )

        forecast = pd.Series(forecast.values, index=future_exog.index)
        all_forecasts[denom] = forecast

        final_value = forecast.loc[future_end]
        final_quantity = final_value / denom_value[denom]

        summary_rows.append({
            "Denomination": denom,
            "Forecast Value (RM Million)": final_value,
            "Estimated Quantity (Million Notes)": final_quantity
        })

    summary_df = pd.DataFrame(summary_rows)

    total_value_rm_million = summary_df["Forecast Value (RM Million)"].sum()
    total_quantity_million_notes = summary_df["Estimated Quantity (Million Notes)"].sum()

    selected_holiday = future_exog.loc[future_end]

    kongsi_raya = (
        selected_holiday["hari_raya"] == 1 and
        selected_holiday["cny"] == 1
    )

    if kongsi_raya:
        scenario_label = "Kongsi Raya"
    elif selected_holiday["hari_raya"] == 1:
        scenario_label = "Hari Raya Month"
    elif selected_holiday["cny"] == 1:
        scenario_label = "Chinese New Year Month"
    else:
        scenario_label = "Normal Month"

    # =========================
    # KPI Cards
    # =========================
    st.subheader(f"Forecast Result for {future_end.strftime('%B %Y')}")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Total Forecast Value",
        f"RM {total_value_rm_million / 1000:,.2f} billion"
    )

    col2.metric(
        "Total Estimated Quantity",
        f"{total_quantity_million_notes:,.2f} million notes"
    )

    col3.metric(
        "Detected Scenario",
        scenario_label
    )

    # =========================
    # Holiday Scenario Detection
    # =========================
    st.subheader("Holiday Scenario Detection")

    holiday_status_df = pd.DataFrame({
        "Holiday Feature": [
            "Holiday Count",
            "Hari Raya",
            "Chinese New Year",
            "Kongsi Raya"
        ],
        "Status": [
            int(selected_holiday["holiday_count"]),
            "Yes" if selected_holiday["hari_raya"] == 1 else "No",
            "Yes" if selected_holiday["cny"] == 1 else "No",
            "Yes" if kongsi_raya else "No"
        ]
    })

    st.dataframe(
        holiday_status_df,
        use_container_width=True,
        hide_index=True
    )

    if kongsi_raya:
        st.success(
            f"🎉 Kongsi Raya detected in {future_end.strftime('%B %Y')}: "
            "Hari Raya and Chinese New Year occur in the same month."
        )
    elif selected_holiday["hari_raya"] == 1:
        st.info(f"🌙 Hari Raya month detected in {future_end.strftime('%B %Y')}.")
    elif selected_holiday["cny"] == 1:
        st.info(f"🧧 Chinese New Year month detected in {future_end.strftime('%B %Y')}.")
    else:
        st.info(
            f"No Hari Raya or Chinese New Year indicator detected in "
            f"{future_end.strftime('%B %Y')}."
        )

    # =========================
    # Summary Table
    # =========================
    st.subheader("Forecast Summary by Denomination")

    st.dataframe(
        summary_df.style.format({
            "Forecast Value (RM Million)": "{:,.2f}",
            "Estimated Quantity (Million Notes)": "{:,.2f}"
        }),
        use_container_width=True
    )

    # =========================
    # Line Chart by Denomination
    # =========================
    st.subheader("Forecast Trend by Denomination")

    for denom, note_col in note_cols.items():
        historical_df = df[[note_col]].copy()
        historical_df = historical_df.rename(columns={note_col: "Historical Actual"})

        forecast_df = pd.DataFrame({
            "Future Forecast": all_forecasts[denom]
        })

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=historical_df.index,
            y=historical_df["Historical Actual"],
            mode="lines",
            name="Historical Actual"
        ))

        fig.add_trace(go.Scatter(
            x=forecast_df.index,
            y=forecast_df["Future Forecast"],
            mode="lines",
            name="Future Forecast",
            line=dict(dash="dash")
        ))

        fig.add_vline(
            x=last_date,
            line_dash="dot",
            annotation_text="Forecast Start",
            annotation_position="top left"
        )

        fig.update_layout(
            title=f"{denom} Circulation Forecast",
            xaxis_title="Date",
            yaxis_title="Value (RM Million)",
            height=380,
            template="plotly_white",
            hovermode="x unified",
            margin=dict(l=40, r=40, t=60, b=40)
        )

        st.plotly_chart(fig, use_container_width=True)

    # =========================
    # Total Forecast Line Chart
    # =========================
    st.subheader("Total Banknotes Circulation Forecast")

    historical_total = df[list(note_cols.values())].sum(axis=1)
    forecast_total = pd.DataFrame(all_forecasts).sum(axis=1)

    fig_total = go.Figure()

    fig_total.add_trace(go.Scatter(
        x=historical_total.index,
        y=historical_total.values,
        mode="lines",
        name="Historical Total"
    ))

    fig_total.add_trace(go.Scatter(
        x=forecast_total.index,
        y=forecast_total.values,
        mode="lines",
        name="Forecast Total",
        line=dict(dash="dash")
    ))

    fig_total.add_vline(
        x=last_date,
        line_dash="dot",
        annotation_text="Forecast Start",
        annotation_position="top left"
    )

    fig_total.update_layout(
        title="Total Banknotes Circulation Forecast",
        xaxis_title="Date",
        yaxis_title="Value (RM Million)",
        height=450,
        template="plotly_white",
        hovermode="x unified",
        margin=dict(l=40, r=40, t=60, b=40)
    )

    st.plotly_chart(fig_total, use_container_width=True)

    st.caption(
        "Note: Forecast values are generated using SARIMAX models with holiday-related "
        "exogenous variables. Kongsi Raya is detected when both Hari Raya and Chinese "
        "New Year indicators are equal to 1 in the selected month."
    )

else:
    st.info("Select a forecast month from the sidebar and click Predict Forecast.")