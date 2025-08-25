import os
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from src.utils import typed_read_csv, add_datekey_month, revenue_from_sales, cost_from_sales, ensure_datetime, cohort_retention, yoy

st.set_page_config(page_title="E‑commerce & Subscriptions Analytics", layout="wide")
DATA_DIR = os.environ.get("APP_DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))

@st.cache_data(show_spinner=False)
def load_all(data_dir: str):
    files = {
        "DimDate": "DimDate.csv",
        "DimGeo": "DimGeo.csv",
        "DimChannel": "DimChannel.csv",
        "DimProduct": "DimProduct.csv",
        "DimCustomer": "DimCustomer.csv",
        "FactSubscriptions": "FactSubscriptions.csv",
        "FactSales": "FactSales.csv",
        "FactWeb": "FactWeb.csv",
        "FactBudget": "FactBudget.csv",
    }
    dfs = {}
    for name, fname in files.items():
        path = os.path.join(data_dir, fname)
        if not os.path.exists(path):
            st.error(f"Missing file: {fname} in {data_dir}")
            st.stop()
        dfs[name] = typed_read_csv(path)
    return dfs

dfs = load_all(DATA_DIR)


dfs["DimDate"]["Date"] = pd.to_datetime(dfs["DimDate"]["Date"], errors="coerce")
for c in ["StartDate","EndDate"]:
    if c in dfs["FactSubscriptions"]:
        dfs["FactSubscriptions"][c] = pd.to_datetime(dfs["FactSubscriptions"][c], errors="coerce")

# Precompute month keys
dfs["DimDate"]["DateKeyMonth"] = dfs["DimDate"]["Date"].dt.year * 10000 + dfs["DimDate"]["Date"].dt.month * 100 + 1
if "DateKey" not in dfs["FactBudget"] and "DateKey" in dfs["FactBudget"]:
    pass
else:

    dfs["FactBudget"]["DateKey"] = dfs["FactBudget"]["DateKey"].astype(int)


dim_date = dfs["DimDate"]
dim_geo = dfs["DimGeo"]
dim_channel = dfs["DimChannel"]
dim_product = dfs["DimProduct"]
dim_customer = dfs["DimCustomer"]
fact_sales = dfs["FactSales"]
fact_web = dfs["FactWeb"]
fact_budget = dfs["FactBudget"]
fact_subs = dfs["FactSubscriptions"]

# Derive revenue/cost on sales
fact_sales["Revenue"] = revenue_from_sales(fact_sales)
fact_sales["CostAmt"] = cost_from_sales(fact_sales)

# Enrich sales with date and dims
sales = fact_sales.merge(dim_date[["DateKey","Date","Year","Month","MonthIdx"]], on="DateKey", how="left") \
                  .merge(dim_product[["ProductID","Category","Subcategory"]], on="ProductID", how="left") \
                  .merge(dim_channel[["ChannelID","ChannelName","Type"]], on="ChannelID", how="left") \
                  .merge(dim_customer[["CustomerID","Region","Country","Segment"]], on="CustomerID", how="left")

# Budget enrichment (align by month/category/channel)
fact_budget = fact_budget.copy()
fact_budget["DateKey"] = fact_budget["DateKey"].astype(int)
budget = fact_budget.merge(dim_channel[["ChannelID","ChannelName"]], on="ChannelID", how="left")

# Web enrichment
web = fact_web.merge(dim_date[["DateKey","Date","Year","Month","MonthIdx"]], on="DateKey", how="left") \
              .merge(dim_channel[["ChannelID","ChannelName","Type"]], on="ChannelID", how="left")


st.sidebar.header("Filters")
min_date = pd.to_datetime(dim_date["Date"].min())
max_date = pd.to_datetime(dim_date["Date"].max())
date_range = st.sidebar.date_input("Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date)

sel_channels = st.sidebar.multiselect("Channels", sorted(dim_channel["ChannelName"].unique().tolist()))
sel_countries = st.sidebar.multiselect("Countries", sorted(dim_customer["Country"].unique().tolist()))
sel_segments = st.sidebar.multiselect("Segments", sorted(dim_customer["Segment"].unique().tolist()))

discount_extra = st.sidebar.slider("What‑If extra discount (%)", min_value=0.0, max_value=20.0, value=0.0, step=0.5) / 100.0

# filters
mask = (sales["Date"] >= pd.to_datetime(date_range[0])) & (sales["Date"] <= pd.to_datetime(date_range[1]))
if sel_channels:
    mask &= sales["ChannelName"].isin(sel_channels)
if sel_countries:
    mask &= sales["Country"].isin(sel_countries)
if sel_segments:
    mask &= sales["Segment"].isin(sel_segments)

sales_f = sales.loc[mask].copy()

# What‑If discount
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


# Layout
st.title("E‑commerce & Subscriptions Analytics")

# KPI row
kpi_cols = st.columns(6)
kpi_cols[0].metric("Revenue", f"${rev:,.0f}")
kpi_cols[1].metric("Gross Margin %", f"{gm_pct*100:,.1f}%")
kpi_cols[2].metric("MRR (current)", f"${curr_mrr:,.0f}")
kpi_cols[3].metric("ARR", f"${arr:,.0f}")
kpi_cols[4].metric("Active Subs", f"{active_count:,}")
kpi_cols[5].metric("Churn % (month)", f"{churn_rate*100:,.2f}%")

# Tabs
tab_trend, tab_product, tab_marketing, tab_budget, tab_cohort, tab_quality = st.tabs(
    ["Trends", "Product & Margin", "Marketing", "Budget vs Actual", "Cohort Retention", "Data Quality"]
)


# Trends
with tab_trend:
    st.subheader("Revenue trend")
    ts = sales_f.groupby(pd.Grouper(key="Date", freq="M")).agg(Revenue=("RevenueAdj","sum"))
    ts = ts.reset_index()
    fig = px.line(ts, x="Date", y="Revenue", markers=True)
    st.plotly_chart(fig, use_container_width=True)

    # YoY
    ts_m = ts.set_index("Date")["Revenue"]
    yoy_series = yoy(ts_m, ts_m.index).dropna()
    if not yoy_series.empty:
        st.subheader("YoY Revenue %")
        fig2 = px.bar(yoy_series.reset_index(), x="Date", y="Revenue")
        fig2.update_yaxes(tickformat=".1%")
        st.plotly_chart(fig2, use_container_width=True)


# Product & Margin
with tab_product:
    st.subheader("Revenue and GM% by Category / Subcategory")
    ag = sales_f.groupby(["Category","Subcategory"], as_index=False).agg(
        Revenue=("RevenueAdj","sum"),
        Cost=("CostAmt","sum")
    )
    ag["GM%"] = (ag["Revenue"] - ag["Cost"]) / ag["Revenue"]
    fig = px.treemap(ag, path=["Category","Subcategory"], values="Revenue",
                     color="GM%", color_continuous_scale="RdYlGn")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top Products by Revenue")
    topn = sales_f.groupby("ProductID", as_index=False).agg(
        Revenue=("RevenueAdj","sum")
    ).merge(dim_product[["ProductID","ProductName","Category","Subcategory"]], on="ProductID", how="left") \
     .sort_values("Revenue", ascending=False).head(25)
    fig2 = px.bar(topn, x="ProductName", y="Revenue", hover_data=["Category","Subcategory"])
    fig2.update_layout(xaxis_tickangle=45, height=450)
    st.plotly_chart(fig2, use_container_width=True)


# Marketing
with tab_marketing:
    st.subheader("Sessions, Conversions, Spend")
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

    st.subheader("Channel performance")
    ch_ag = merged.groupby("ChannelName", as_index=False).agg(
        Revenue=("Revenue","sum"),
        Sessions=("Sessions","sum"),
        Spend=("Spend","sum")
    )
    ch_ag["ROAS"] = ch_ag["Revenue"] / ch_ag["Spend"]
    fig = px.scatter(ch_ag, x="Sessions", y="Revenue", size="Spend", color="ChannelName", hover_data=["ROAS"])
    st.plotly_chart(fig, use_container_width=True)


# Budget vs Actual
with tab_budget:
    st.subheader("Variance to Budget (Monthly)")
    # Build monthly revenue by Category+Channel
    sales_mcc = sales_f.copy()
    sales_mcc["DateKeyMonth"] = sales_mcc["Date"].dt.year*10000 + sales_mcc["Date"].dt.month*100 + 1
    rev_mcc = sales_mcc.groupby(["DateKeyMonth","Category","ChannelName"], as_index=False).agg(Revenue=("RevenueAdj","sum"))
    # Budget
    bud = budget.rename(columns={"BudgetRevenue":"BudgetRevenue","BudgetMRR":"BudgetMRR"})
    bud = bud.merge(dim_date[["DateKeyMonth","Date"]], left_on="DateKey", right_on="DateKeyMonth", how="left")
    bud["Month"] = bud["Date"].dt.to_period("M").astype(str)
    # Align
    m = rev_mcc.merge(bud[["DateKeyMonth","Category","ChannelName","BudgetRevenue"]],
                      on=["DateKeyMonth","Category","ChannelName"], how="left")
    m["VarToBudget"] = m["Revenue"] - m["BudgetRevenue"]
    m["Var%"] = m["VarToBudget"] / m["BudgetRevenue"]
    # Plot
    show = m.sort_values("DateKeyMonth")
    show["Month"] = pd.to_datetime(show["DateKeyMonth"].astype(str), format="%Y%m%d").dt.to_period("M").astype(str)
    fig = px.bar(show, x="Month", y="VarToBudget", color="Category", barmode="group", hover_data=["ChannelName","Revenue","BudgetRevenue","Var%"])
    st.plotly_chart(fig, use_container_width=True)


# Cohort Retention
with tab_cohort:
    st.subheader("Subscription Cohort Retention")
    date_index = pd.date_range(min_date, max_date, freq="M")
    ret = cohort_retention(fact_subs, date_index)
    if ret.empty:
        st.info("No cohort data available for the selected range.")
    else:
        fig = px.imshow(ret, aspect="auto", origin="lower", labels=dict(x="Months Since Start", y="Cohort (Start Month)", color="Retention"),
                        color_continuous_scale="Blues", zmin=0, zmax=1)
        fig.update_yaxes(ticktext=[d.strftime("%Y-%m") for d in ret.index], tickvals=list(range(len(ret.index))))
        st.plotly_chart(fig, use_container_width=True)


# Data Quality
with tab_quality:
    st.subheader("Data Quality & Refresh")
    qc = []
    for name, df in dfs.items():
        qc.append({"Table": name, "Rows": len(df), "Null % (any col)": round(100*df.isna().mean().mean(), 2)})
    st.dataframe(pd.DataFrame(qc))
    st.caption(f"Data directory: {DATA_DIR}")
