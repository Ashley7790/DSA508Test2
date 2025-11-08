
import os
from datetime import datetime
import pandas as pd
import numpy as np
import streamlit as st
from pymongo import MongoClient
from pymongo.errors import PyMongoError

st.set_page_config(page_title="Retail Orders Dashboard", layout="wide")

# ---------------------------
# Config: Streamlit secrets
# ---------------------------
# In Streamlit Community Cloud, add these in: Settings → Secrets
# MONGO_URI: your CosmosDB/MongoDB connection string
# DB_NAME: database name (e.g., "retail")
# COLL_NAME: collection name (e.g., "orders")
MONGO_URI = st.secrets.get("MONGO_URI") or os.environ.get("MONGO_URI", "")
DB_NAME = st.secrets.get("DB_NAME") or os.environ.get("DB_NAME", "retail")
COLL_NAME = st.secrets.get("COLL_NAME") or os.environ.get("COLL_NAME", "orders")

@st.cache_resource(show_spinner=False)
def get_collection(uri, db_name, coll_name):
    if not uri:
        raise RuntimeError("MONGO_URI is not set. Add it to Streamlit Secrets.")
    client = MongoClient(uri, tls=True)
    db = client[db_name]
    return db[coll_name]

@st.cache_data(show_spinner=False)
def load_orders(_coll):
    # Pull only the fields we need for performance
    pipeline = [
        {"$project": {
            "_id": 1, "purchase_ts": 1, "purchase_date": 1, "purchase_time": 1,
            "weekday": 1, "hour": 1,
            "store.store_city": 1, "store.region": 1,
            "channel": 1, "payment_method": 1,
            "customer.loyalty_member": 1, "customer.age_band": 1,
            "coupon_used": 1, "discount_pct": 1,
            "subtotal": 1, "discount_amount": 1, "tax_amount": 1,
            "shipping_amount": 1, "total_amount": 1,
            "items": 1
        }}
    ]
    docs = list(_coll.aggregate(pipeline))
    if not docs:
        return pd.DataFrame()
    # flatten
    rows = []
    for d in docs:
        items = d.get("items", [])
        rows.append({
            "order_id": str(d.get("_id")),
            "purchase_ts": d.get("purchase_ts"),
            "purchase_date": d.get("purchase_date"),
            "purchase_time": d.get("purchase_time"),
            "weekday": d.get("weekday"),
            "hour": d.get("hour"),
            "store_city": d.get("store",{}).get("store_city"),
            "region": d.get("store",{}).get("region"),
            "channel": d.get("channel"),
            "payment_method": d.get("payment_method"),
            "loyalty_member": d.get("customer",{}).get("loyalty_member"),
            "age_band": d.get("customer",{}).get("age_band"),
            "coupon_used": d.get("coupon_used"),
            "discount_pct": d.get("discount_pct"),
            "subtotal": d.get("subtotal"),
            "discount_amount": d.get("discount_amount"),
            "tax_amount": d.get("tax_amount"),
            "shipping_amount": d.get("shipping_amount"),
            "total_amount": d.get("total_amount"),
            "num_items": sum(it.get("quantity",0) for it in items),
            "categories": ",".join(sorted({it.get("category","") for it in items}))
        })
    df = pd.DataFrame(rows)
    # types
    df["purchase_ts"] = pd.to_datetime(df["purchase_ts"], errors="coerce")
    return df

st.title("🛍️ Retail Orders Dashboard")

try:
    coll = get_collection(MONGO_URI, DB_NAME, COLL_NAME)
    df = load_orders(coll)
except (PyMongoError, Exception) as e:
    st.error(f"Database connection failed: {e}")
    st.stop()

if df.empty:
    st.warning("No orders found. Import data into your collection and refresh.")
    st.stop()

# Sidebar filters
with st.sidebar:
    st.header("Filters")
    date_min, date_max = df["purchase_ts"].min().date(), df["purchase_ts"].max().date()
    date_range = st.date_input("Date Range", value=(date_min, date_max), min_value=date_min, max_value=date_max)
    region = st.multiselect("Region", sorted(df["region"].dropna().unique()))
    channel = st.multiselect("Channel", sorted(df["channel"].dropna().unique()))
    loyalty = st.multiselect("Loyalty Member", [True, False])
    age = st.multiselect("Age Band", sorted(df["age_band"].dropna().unique()))
    show_table = st.toggle("Show Raw Table", value=False)

mask = pd.Series(True, index=df.index)
start = pd.to_datetime(date_range[0])
end = pd.to_datetime(date_range[1]) + pd.Timedelta(days=1)
mask &= (df["purchase_ts"] >= start) & (df["purchase_ts"] < end)
if region: mask &= df["region"].isin(region)
if channel: mask &= df["channel"].isin(channel)
if loyalty: mask &= df["loyalty_member"].isin(loyalty)
if age: mask &= df["age_band"].isin(age)

f = df[mask].copy()

# KPIs
c1, c2, c3, c4 = st.columns(4)
c1.metric("Orders", f"{len(f):,}")
c2.metric("Revenue", f"${f['total_amount'].sum():,.0f}")
c3.metric("Avg Order Value", f"${f['total_amount'].mean():,.2f}")
c4.metric("Avg Discount %", f"{(f['discount_pct'].mean() * 100):.1f}%")

# Charts
st.subheader("Revenue Over Time (Daily)")
daily = f.resample("D", on="purchase_ts")["total_amount"].sum().reset_index()
st.line_chart(daily.set_index("purchase_ts"))

c5, c6 = st.columns(2)
with c5:
    st.subheader("Revenue by Region")
    by_region = f.groupby("region")["total_amount"].sum().sort_values(ascending=False)
    st.bar_chart(by_region)
with c6:
    st.subheader("Revenue by Channel")
    by_channel = f.groupby("channel")["total_amount"].sum().sort_values(ascending=False)
    st.bar_chart(by_channel)

c7, c8 = st.columns(2)
with c7:
    st.subheader("AOV by Loyalty")
    aov = f.groupby("loyalty_member")["total_amount"].mean().rename({True:"Loyalty", False:"Non-Loyalty"})
    st.bar_chart(aov)
with c8:
    st.subheader("Avg Discount % by Channel")
    disc = (f.groupby("channel")["discount_pct"].mean() * 100).sort_values(ascending=False)
    st.bar_chart(disc)

# Weekday/Hour heat table
st.subheader("Revenue by Weekday & Hour (table)")
heat = f.pivot_table(index="weekday", columns="hour", values="total_amount", aggfunc="sum").fillna(0)
wd_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
heat = heat.reindex(wd_order)
st.dataframe(heat.style.format("{:,.0f}"))

if show_table:
    st.subheader("Raw Orders (Filtered)")
    st.dataframe(f.sort_values("purchase_ts", ascending=False).head(1000))
