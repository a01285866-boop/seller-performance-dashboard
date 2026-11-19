from io import BytesIO
from pathlib import Path
import re
from zipfile import BadZipFile

import pandas as pd
import streamlit as st


APP_DIR = Path(__file__).resolve().parent
DATA_CANDIDATES = (
    APP_DIR / "data" / "sellers.xlsx",
    APP_DIR / "data" / "sellers.csv",
    APP_DIR / "sellers.xlsx",
    APP_DIR / "sellers.csv",
)
PLACEHOLDER = "— Select a column —"
AVERAGE_FROM_SALES = "Calculate from sales"

COLUMN_ALIASES = {
    "Region": ("region", "territory", "area"),
    "Vendor": (
        "vendor",
        "vendorname",
        "vendorid",
        "seller",
        "sellername",
        "sellerid",
        "salesrep",
        "salesperson",
        "representative",
    ),
    "Units sold": ("unitssold", "units", "quantity", "qty"),
    "Sales amount": (
        "totalsales",
        "sales",
        "salesamount",
        "revenue",
        "totalrevenue",
        "grosssales",
        "amount",
    ),
    "Average sales": (
        "averagesales",
        "avgsales",
        "averagesale",
        "avgsale",
        "averagerevenue",
        "avgrevenue",
    ),
}


def normalize_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def detect_column(columns: list[str], role: str) -> str | None:
    normalized = {normalize_name(column): column for column in columns}
    for alias in COLUMN_ALIASES[role]:
        if alias in normalized:
            return normalized[alias]
    return None


def select_column(label: str, columns: list[str], role: str) -> str:
    detected = detect_column(columns, role)
    options = [PLACEHOLDER, *columns]
    selected_index = options.index(detected) if detected in columns else 0
    return st.selectbox(label, options, index=selected_index)


@st.cache_data
def excel_sheets(file_bytes: bytes) -> list[str]:
    with pd.ExcelFile(BytesIO(file_bytes)) as workbook:
        return workbook.sheet_names


@st.cache_data
def read_dataset(file_bytes: bytes, filename: str, sheet_name: str) -> pd.DataFrame:
    if Path(filename).suffix.lower() == ".csv":
        return pd.read_csv(BytesIO(file_bytes))
    return pd.read_excel(BytesIO(file_bytes), sheet_name=sheet_name)


def numeric_values(values: pd.Series) -> pd.Series:
    cleaned = values.astype("string").str.replace(r"[$,\s]", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce")


st.set_page_config(page_title="Seller Performance Dashboard", layout="wide")
st.title("Seller Performance Dashboard")
st.write(
    "Explore seller performance by region, compare sales metrics, "
    "and inspect an individual vendor."
)

uploaded_file = st.sidebar.file_uploader(
    "Upload sellers.xlsx or sellers.csv",
    type=["xlsx", "csv"],
)

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    filename = uploaded_file.name
else:
    default_file = next(
        (path for path in DATA_CANDIDATES if path.is_file()),
        None,
    )
    if default_file is None:
        st.info(
            "Upload the provided sellers.xlsx (or a CSV), or place it at "
            "`data/sellers.xlsx` / `data/sellers.csv`."
        )
        st.stop()
    file_bytes = default_file.read_bytes()
    filename = default_file.name

sheet_name = ""
if Path(filename).suffix.lower() != ".csv":
    try:
        sheets = excel_sheets(file_bytes)
    except (BadZipFile, ImportError, OSError, ValueError) as error:
        st.error(f"Could not read {filename}: {error}")
        st.stop()
    if not sheets:
        st.error(f"No worksheets were found in {filename}.")
        st.stop()
    sheet_name = st.sidebar.selectbox("Worksheet", sheets)

try:
    source_data = read_dataset(file_bytes, filename, sheet_name)
except (BadZipFile, ImportError, OSError, pd.errors.ParserError, ValueError) as error:
    st.error(f"Could not read {filename}: {error}")
    st.stop()

if source_data.empty or len(source_data.columns) == 0:
    st.error("The selected file has no tabular data.")
    st.stop()

source_data.columns = [str(column) for column in source_data.columns]
column_names = list(source_data.columns)

with st.sidebar.expander("Map your data columns", expanded=True):
    region_column = select_column("Region", column_names, "Region")
    vendor_column = select_column("Vendor", column_names, "Vendor")
    units_column = select_column("Units sold", column_names, "Units sold")
    sales_column = select_column("Sales amount", column_names, "Sales amount")
    average_options = [AVERAGE_FROM_SALES, *column_names]
    detected_average = detect_column(column_names, "Average sales")
    average_index = (
        average_options.index(detected_average)
        if detected_average in column_names
        else 0
    )
    average_column = st.selectbox(
        "Average sales (optional)",
        average_options,
        index=average_index,
        help=(
            "If the file has no average-sales field, the dashboard calculates "
            "the mean sales amount per row."
        ),
    )

required_columns = {
    "Region": region_column,
    "Vendor": vendor_column,
    "Units sold": units_column,
    "Sales amount": sales_column,
}
unmapped = [
    role for role, column in required_columns.items() if column == PLACEHOLDER
]
if unmapped:
    st.warning("Choose columns for: " + ", ".join(unmapped) + ".")
    st.stop()
if len(set(required_columns.values())) != len(required_columns):
    st.error("Map each required field to a different source column.")
    st.stop()

dashboard_data = source_data.copy()
dashboard_data["_region"] = (
    source_data[region_column].fillna("Unknown").astype(str).str.strip()
)
dashboard_data["_vendor"] = (
    source_data[vendor_column].fillna("Unknown").astype(str).str.strip()
)
dashboard_data["_units_sold"] = numeric_values(source_data[units_column])
dashboard_data["_total_sales"] = numeric_values(source_data[sales_column])

if average_column == AVERAGE_FROM_SALES:
    dashboard_data["_average_sales"] = dashboard_data["_total_sales"]
    average_description = "mean sales amount per row"
else:
    dashboard_data["_average_sales"] = numeric_values(
        source_data[average_column]
    )
    average_description = f"mean of {average_column}"

regions = sorted(dashboard_data["_region"].unique(), key=str.casefold)
selected_regions = st.sidebar.multiselect(
    "Filter by region",
    regions,
    default=regions,
)
filtered_data = dashboard_data[
    dashboard_data["_region"].isin(selected_regions)
]
analytics_data = filtered_data.dropna(
    subset=["_units_sold", "_total_sales"]
)
invalid_count = len(filtered_data) - len(analytics_data)
if invalid_count:
    st.warning(
        f"{invalid_count} row(s) have missing or non-numeric units/sales; "
        "they remain in the table but are excluded from metrics and charts."
    )

st.caption(f"Source: {filename} · {len(filtered_data):,} row(s) shown")
if filtered_data.empty:
    st.warning("No rows match the selected region filter.")
    st.stop()
if analytics_data.empty:
    st.error("No rows have numeric values for both units sold and sales.")
    st.stop()

total_units = analytics_data["_units_sold"].sum()
total_sales = analytics_data["_total_sales"].sum()
average_sales = analytics_data["_average_sales"].mean()

with st.container(border=True):
    st.subheader("Overview")
    metric_columns = st.columns(3)
    metric_columns[0].metric("Units sold", f"{total_units:,.0f}")
    metric_columns[1].metric("Total sales", f"{total_sales:,.2f}")
    metric_columns[2].metric("Average sales", f"{average_sales:,.2f}")
    st.caption(f"Average sales is the {average_description}.")

with st.container(border=True):
    st.subheader("Sales by vendor or region")
    breakdown = st.selectbox(
        "Group charts by",
        ["Vendor", "Region"],
    )
    group_column = "_vendor" if breakdown == "Vendor" else "_region"
    group_label = "Vendor" if breakdown == "Vendor" else "Region"
    top_n = st.slider(
        f"Maximum {breakdown.lower()}s to chart",
        min_value=5,
        max_value=50,
        value=20,
    )
    chart_data = (
        analytics_data.groupby(group_column, as_index=False)
        .agg(
            Units_Sold=("_units_sold", "sum"),
            Total_Sales=("_total_sales", "sum"),
            Average_Sales=("_average_sales", "mean"),
        )
        .sort_values("Total_Sales", ascending=False)
        .head(top_n)
    )
    charts = st.columns(3)
    charts[0].bar_chart(
        chart_data,
        x=group_column,
        y="Units_Sold",
        x_label=group_label,
        y_label="Units sold",
        height=320,
    )
    charts[1].bar_chart(
        chart_data,
        x=group_column,
        y="Total_Sales",
        x_label=group_label,
        y_label="Total sales",
        height=320,
    )
    charts[2].bar_chart(
        chart_data,
        x=group_column,
        y="Average_Sales",
        x_label=group_label,
        y_label="Average sales",
        height=320,
    )

with st.container(border=True):
    st.subheader("Vendor details")
    vendors = sorted(filtered_data["_vendor"].unique(), key=str.casefold)
    selected_vendor = st.selectbox(
        "Select a vendor",
        ["Select a vendor...", *vendors],
    )
    if selected_vendor == "Select a vendor...":
        st.info("Select a vendor to see its summary and source rows.")
    else:
        vendor_rows = filtered_data[
            filtered_data["_vendor"] == selected_vendor
        ]
        vendor_metrics = vendor_rows.dropna(
            subset=["_units_sold", "_total_sales"]
        )
        vendor_columns = st.columns(3)
        vendor_columns[0].metric(
            "Units sold",
            f"{vendor_metrics['_units_sold'].sum():,.0f}",
        )
        vendor_columns[1].metric(
            "Total sales",
            f"{vendor_metrics['_total_sales'].sum():,.2f}",
        )
        vendor_columns[2].metric(
            "Average sales",
            f"{vendor_metrics['_average_sales'].mean():,.2f}",
        )
        st.dataframe(
            vendor_rows[column_names],
            width="stretch",
            hide_index=True,
        )

with st.container(border=True):
    st.subheader("Seller table")
    st.dataframe(
        filtered_data[column_names],
        width="stretch",
        hide_index=True,
    )
    st.download_button(
        "Download filtered data as CSV",
        data=filtered_data[column_names].to_csv(index=False).encode("utf-8"),
        file_name="sellers_filtered.csv",
        mime="text/csv",
    )
