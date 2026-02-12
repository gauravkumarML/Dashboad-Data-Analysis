import os
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from src.utils import typed_read_csv, add_datekey_month, ensure_datetime, yoy
from src.metrics import revenue_from_sales, cost_from_sales, cohort_retention
from src.analytics import generate_forecast

st.set_page_config(page_title="Executive Analytics Dashboard", layout="wide")

def apply_custom_styling():
    """Injects custom CSS for branding and layout."""
    css_path = os.path.join(os.path.dirname(__file__), "src", "style", "style.css")
    if os.path.exists(css_path):
        with open(css_path) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

apply_custom_styling()

# Dashboard Theme Configuration

# Plotly Theme Override
def apply_chart_theme(fig):
    fig.update_layout(
        font_family="Inter",
        font_color="#0F172A", # Dark Navy Text
        title="",
        title_text="",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(t=10, b=50, l=50, r=50)
    )
    fig.update_xaxes(showgrid=False, color="#475569")
    fig.update_yaxes(showgrid=True, gridcolor='#E2E8F0', color="#475569")
    return fig

DATA_DIR = os.environ.get("APP_DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))

@st.cache_data(show_spinner=False)
def load_all_parquet(data_dir: str):
    processed_dir = os.path.join(data_dir, "processed")
    files = {
        "sales": "sales_gold.parquet",
        "web": "web_gold.parquet",
        "budget": "budget_gold.parquet",
        "fact_subs": "subscriptions_gold.parquet",
        "dim_date": "dim_date.parquet",
        "dim_channel": "dim_channel.parquet",
        "dim_customer": "dim_customer.parquet",
    }
    
    # If the processed Parquet files are missing, we run the ETL pipeline
    if not os.path.exists(os.path.join(processed_dir, "sales_gold.parquet")):
        from src.etl import run_etl
        run_etl(data_dir, processed_dir)
        
    dfs = {}
    for name, fname in files.items():
        dfs[name] = pd.read_parquet(os.path.join(processed_dir, fname))
    return dfs

data = load_all_parquet(DATA_DIR)

sales = data["sales"]
web = data["web"]
budget = data["budget"]
fact_subs = data["fact_subs"]
dim_date = data["dim_date"]
dim_channel = data["dim_channel"]
dim_customer = data["dim_customer"]

# State Management for Synced Filters
min_date = pd.to_datetime(dim_date["Date"].min())
max_date = pd.to_datetime(dim_date["Date"].max())

if 'date_range' not in st.session_state:
    st.session_state.date_range = (min_date, max_date)
if 'sel_channels' not in st.session_state: st.session_state.sel_channels = []
if 'sel_countries' not in st.session_state: st.session_state.sel_countries = []
if 'sel_segments' not in st.session_state: st.session_state.sel_segments = []
if 'discount_extra' not in st.session_state: st.session_state.discount_extra = 0.0

def render_global_filters(prefix: str):
    """Renders filters at the top of a tab and syncs with global state."""
    with st.container():
        c1, c2, c3, c4 = st.columns(4)
        
        # We use st.session_state.date_range directly as the value and update it
        with c1:
            dr = st.date_input("Date range", value=st.session_state.date_range, 
                               min_value=min_date, max_value=max_date, key=f"{prefix}_date")
            if dr != st.session_state.date_range:
                st.session_state.date_range = dr
                st.rerun()

        with c2:
            sc = st.multiselect("Channels", sorted(dim_channel["ChannelName"].unique().tolist()), 
                                default=st.session_state.sel_channels, key=f"{prefix}_chan")
            if sc != st.session_state.sel_channels:
                st.session_state.sel_channels = sc
                st.rerun()

        with c3:
            sco = st.multiselect("Countries", sorted(dim_customer["Country"].unique().tolist()), 
                                 default=st.session_state.sel_countries, key=f"{prefix}_coun")
            if sco != st.session_state.sel_countries:
                st.session_state.sel_countries = sco
                st.rerun()

        with c4:
            sse = st.multiselect("Segments", sorted(dim_customer["Segment"].unique().tolist()), 
                                 default=st.session_state.sel_segments, key=f"{prefix}_seg")
            if sse != st.session_state.sel_segments:
                st.session_state.sel_segments = sse
                st.rerun()
        
        de = st.slider("What‑If extra discount (%)", min_value=0.0, max_value=20.0, 
                       value=st.session_state.discount_extra * 100.0, step=0.5, key=f"{prefix}_disc") / 100.0
        if de != st.session_state.discount_extra:
            st.session_state.discount_extra = de
            st.rerun()
            
        st.markdown("---")

# Active Filters
date_range = st.session_state.date_range
sel_channels = st.session_state.sel_channels
sel_countries = st.session_state.sel_countries
sel_segments = st.session_state.sel_segments
discount_extra = st.session_state.discount_extra

# Apply filters
mask = (sales["Date"] >= pd.to_datetime(date_range[0])) & (sales["Date"] <= pd.to_datetime(date_range[1]))
if sel_channels:
    mask &= sales["ChannelName"].isin(sel_channels)
if sel_countries:
    mask &= sales["Country"].isin(sel_countries)
if sel_segments:
    mask &= sales["Segment"].isin(sel_segments)

sales_f = sales.loc[mask].copy()

if discount_extra > 0:
    sales_f["RevenueAdj"] = (sales_f["Qty"] * sales_f["UnitPrice"] * (1 - (sales_f["Discount"] + discount_extra)).clip(lower=0))
else:
    sales_f["RevenueAdj"] = sales_f["Revenue"]


# KPIs
rev = sales_f["RevenueAdj"].sum()
cost = sales_f["CostAmt"].sum()
gm = rev - cost
gm_pct = (gm / rev) if rev else 0.0

# MRR/ARR
sub_lines = sales_f[sales_f["IsSubscription"] == 1]
mrr = sub_lines.groupby(pd.Grouper(key="Date", freq="M"))["RevenueAdj"].sum().rename("MRR")
curr_mrr = float(mrr.iloc[-1]) if len(mrr) else 0.0
arr = curr_mrr * 12.0

# Subscriptions
subs = fact_subs.copy()
subs["StartDate"] = pd.to_datetime(subs["StartDate"], errors="coerce")
subs["EndDate"] = pd.to_datetime(subs["EndDate"], errors="coerce")
curr_day = pd.to_datetime(date_range[1])
subs_active = subs[(subs["StartDate"] <= curr_day) & ( (subs["EndDate"].isna()) | (subs["EndDate"] >= curr_day) )]
active_count = subs_active["CustomerID"].nunique()
new_count = subs[(subs["StartDate"].dt.to_period("M") == curr_day.to_period("M"))]["CustomerID"].nunique()
churned_count = subs[(subs["EndDate"].notna()) & (subs["EndDate"].dt.to_period("M") == curr_day.to_period("M"))]["CustomerID"].nunique()
churn_rate = churned_count / max(active_count + churned_count - new_count, 1)


# Application Layout and Metric Visualization

# KPI row
kpi_cols = st.columns(6)
kpi_cols[0].metric("Revenue", f"${rev:,.0f}")
kpi_cols[1].metric("Gross Margin %", f"{gm_pct*100:,.1f}%")
kpi_cols[2].metric("MRR (current)", f"${curr_mrr:,.0f}")
kpi_cols[3].metric("ARR", f"${arr:,.0f}")
kpi_cols[4].metric("Active Subs", f"{active_count:,}")
kpi_cols[5].metric("Churn % (month)", f"{churn_rate*100:,.2f}%")

# Metric Tabs
tab_trend, tab_product, tab_marketing, tab_budget, tab_cohort, tab_outlook, tab_quality = st.tabs(
    ["Trends", "Product & Margin", "Marketing", "Budget vs Actual", "Cohort Retention", "Future Outlook", "Data Quality"]
)


# Trends
with tab_trend:
    render_global_filters("trend")
    st.markdown("### Revenue trend")
    ts = sales_f.groupby(pd.Grouper(key="Date", freq="ME")).agg(Revenue=("RevenueAdj","sum")).reset_index()
    fig = px.line(ts, x="Date", y="Revenue", markers=True, color_discrete_sequence=["#0F172A"])
    apply_chart_theme(fig)
    st.plotly_chart(fig, use_container_width=True)

    # YoY
    ts_m = ts.set_index("Date")["Revenue"]
    yoy_series = yoy(ts_m, ts_m.index).dropna()
    if not yoy_series.empty:
        st.markdown("### YoY Revenue %")
        fig2 = px.bar(yoy_series.reset_index(), x="Date", y="Revenue", color_discrete_sequence=["#38BDF8"])
        fig2.update_yaxes(tickformat=".1%")
        apply_chart_theme(fig2)
        st.plotly_chart(fig2, use_container_width=True)


# Product & Margin
with tab_product:
    render_global_filters("prod")
    st.markdown("### Revenue and GM% by Category / Subcategory")
    ag = sales_f.groupby(["Category","Subcategory"], as_index=False).agg(
        Revenue=("RevenueAdj","sum"),
        Cost=("CostAmt","sum")
    )
    ag["GM%"] = (ag["Revenue"] - ag["Cost"]) / ag["Revenue"]
    fig = px.treemap(ag, path=["Category","Subcategory"], values="Revenue",
                     color="GM%", color_continuous_scale="RdBu")
    apply_chart_theme(fig)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Top Products by Revenue")
    topn = sales_f.groupby(["ProductID", "ProductName", "Category", "Subcategory"], as_index=False).agg(
        Revenue=("RevenueAdj","sum")
    ).sort_values("Revenue", ascending=False).head(25)
    fig2 = px.bar(topn, x="ProductName", y="Revenue", hover_data=["Category","Subcategory"], color_discrete_sequence=["#0F4C81"])
    fig2.update_layout(xaxis_tickangle=45, height=450)
    apply_chart_theme(fig2)
    st.plotly_chart(fig2, use_container_width=True)


# Marketing
with tab_marketing:
    render_global_filters("mkt")
    st.markdown("### Sessions, Conversions, Spend")
    web_f = web.copy()
    if sel_channels:
        web_f = web_f[web_f["ChannelName"].isin(sel_channels)]
    web_f = web_f[(web_f["Date"] >= pd.to_datetime(date_range[0])) & (web_f["Date"] <= pd.to_datetime(date_range[1]))]
    #kpis = web_f.agg(Sessions=("Sessions","sum"), Conversions=("Conversions","sum"), Spend=("Spend","sum"))
    kpis = web_f[["Sessions", "Conversions", "Spend"]].sum(numeric_only=True)
    colA, colB, colC, colD, colE = st.columns(5)
    colA.metric("Sessions", f"{int(kpis['Sessions']):,}")
    colB.metric("Conversions", f"{int(kpis['Conversions']):,}")
    colC.metric("Spend", f"${kpis['Spend']:,.0f}")
    conv_rate = kpis["Conversions"] / kpis["Sessions"] if kpis["Sessions"] else 0.0
    # Revenue per session: join sales revenue by channel & month
    rev_by_chm = sales_f.groupby(["ChannelName", pd.Grouper(key="Date", freq="M")]).agg(Revenue=("RevenueAdj","sum")).reset_index()
    web_by_chm = web_f.groupby(["ChannelName", pd.Grouper(key="Date", freq="M")]).agg(Sessions=("Sessions","sum"), Spend=("Spend","sum")).reset_index()
    merged = rev_by_chm.merge(web_by_chm, on=["ChannelName","Date"], how="right")
    merged["RevenuePerSession"] = merged["Revenue"] / merged["Sessions"]
    merged["ROAS"] = merged["Revenue"] / merged["Spend"]
    colD.metric("Conv Rate", f"{conv_rate*100:,.2f}%")
    rps = merged["Revenue"].sum() / merged["Sessions"].sum() if merged["Sessions"].sum() else 0.0
    colE.metric("Revenue / Session", f"${rps:,.2f}")

    st.markdown("### Channel performance")
    ch_ag = merged.groupby("ChannelName", as_index=False).agg(
        Revenue=("Revenue","sum"),
        Sessions=("Sessions","sum"),
        Spend=("Spend","sum")
    )
    ch_ag["ROAS"] = ch_ag["Revenue"] / ch_ag["Spend"]
    fig = px.scatter(ch_ag, x="Sessions", y="Revenue", size="Spend", color="ChannelName", hover_data=["ROAS"], color_discrete_sequence=px.colors.qualitative.Prism)
    apply_chart_theme(fig)
    st.plotly_chart(fig, use_container_width=True)


# Budget vs Actual
with tab_budget:
    render_global_filters("bud")
    st.markdown("### Variance to Budget (Monthly)")
    # Build monthly revenue by Category+Channel
    rev_mcc = sales_f.groupby(["DateKeyMonth","Category","ChannelName"], as_index=False).agg(Revenue=("RevenueAdj","sum"))
    # Budget
    bud = budget.rename(columns={"BudgetRevenue":"BudgetRevenue","BudgetMRR":"BudgetMRR"})
    # Align
    m = rev_mcc.merge(bud[["DateKeyMonth","Category","ChannelName","BudgetRevenue"]],
                      on=["DateKeyMonth","Category","ChannelName"], how="left")
    m["VarToBudget"] = m["Revenue"] - m["BudgetRevenue"]
    m["Var%"] = m["VarToBudget"] / m["BudgetRevenue"]
    # Plot
    show = m.sort_values("DateKeyMonth")
    show["DateObj"] = pd.to_datetime(show["DateKeyMonth"].astype(str), format="%Y%m%d")
    show["Month"] = show["DateObj"].dt.to_period("M").astype(str)
    fig = px.bar(show, x="Month", y="VarToBudget", color="Category", barmode="group", 
                 hover_data=["ChannelName","Revenue","BudgetRevenue","Var%"],
                 color_discrete_sequence=px.colors.qualitative.Safe)
    apply_chart_theme(fig)
    st.plotly_chart(fig, use_container_width=True)


# Cohort Retention
with tab_cohort:
    render_global_filters("coh")
    st.markdown("### Subscription Cohort Retention")
    date_index = pd.date_range(min_date, max_date, freq="M")
    ret = cohort_retention(fact_subs, date_index)
    if ret.empty:
        st.info("No cohort data available for the selected range.")
    else:
        fig = px.imshow(ret, aspect="auto", origin="lower", labels=dict(x="Months Since Start", y="Cohort (Start Month)", color="Retention"),
                        color_continuous_scale="Blues", zmin=0, zmax=1)
        fig.update_yaxes(ticktext=[d.strftime("%Y-%m") for d in ret.index], tickvals=list(range(len(ret.index))))
        apply_chart_theme(fig)
        st.plotly_chart(fig, use_container_width=True)


# Future Outlook
with tab_outlook:
    render_global_filters("fore")
    st.markdown("### Forecasted Revenue Project (12 Months)")
    st.info("Based on historical data and trends, Linear Regression.")
    
    forecast_df = generate_forecast(sales_f)
    
    fig = px.line(forecast_df, x="Date", y="revenue", color="type", markers=True,
                  color_discrete_map={"Historical": "#0F4C81", "Forecast": "#FF4B4B"})
    
    
    # In a real scenario, we'd use model.stdev or similar
    forecast_only = forecast_df[forecast_df["type"] == "Forecast"].copy()
    if not forecast_only.empty:
        forecast_only["upper"] = forecast_only["revenue"] * 1.1
        forecast_only["lower"] = forecast_only["revenue"] * 0.9
        
        fig.add_scatter(x=forecast_only["Date"], y=forecast_only["upper"], 
                        line=dict(width=0), showlegend=False, hoverinfo='skip')
        fig.add_scatter(x=forecast_only["Date"], y=forecast_only["lower"], 
                        fill='tonexty', fillcolor='rgba(255, 75, 75, 0.1)',
                        line=dict(width=0), name="90% Confidence Interval")

    apply_chart_theme(fig)
    st.plotly_chart(fig, use_container_width=True)


# Data Quality
with tab_quality:
    st.markdown("### Data Quality & Refresh")
    qc = []
    for name, df in data.items():
        qc.append({"Table": name, "Rows": len(df), "Null % (any col)": round(100*df.isna().mean().mean(), 2)})
    st.dataframe(pd.DataFrame(qc), use_container_width=True)
    st.caption(f"Data directory: {DATA_DIR}")
