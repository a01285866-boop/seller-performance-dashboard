# Seller Performance Dashboard

A Streamlit dashboard for exploring seller performance by region, comparing
units sold, total sales, and average sales, and inspecting an individual vendor.

## Run locally

```bash
python -m pip install -r requirements.txt
streamlit run sellers_dashboard.py
```

Upload `sellers.xlsx` or a CSV in the app. Excel workbooks can contain multiple
worksheets; select the worksheet and map its region, vendor, units, and sales
columns. The dashboard calculates average sales from the mean sales amount per
row when the workbook has no average-sales column.

For local development, a file can also be placed at `data/sellers.xlsx` or
`data/sellers.csv`. Dataset files are intentionally excluded from this
repository.
