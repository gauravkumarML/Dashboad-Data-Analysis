import os
import pandas as pd
import logging
from src.utils import typed_read_csv
from src.metrics import revenue_from_sales, cost_from_sales

# Logger initialization for ETL tracking
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_etl(data_dir, output_dir):
    """
    Loads raw CSV data, performs cleaning and joining, and saves to Parquet.
    """
    logger.info(f"Starting ETL process. Source: {data_dir}, Destination: {output_dir}")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

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
            logger.error(f"Missing file: {fname}")
            return
        dfs[name] = typed_read_csv(path)
        logger.info(f"Loaded {name} ({len(dfs[name])} rows)")

    # Step 1: Standardize date formats across tables
    dfs["DimDate"]["Date"] = pd.to_datetime(dfs["DimDate"]["Date"], errors="coerce")
    dfs["DimDate"]["DateKeyMonth"] = dfs["DimDate"]["Date"].dt.year * 10000 + dfs["DimDate"]["Date"].dt.month * 100 + 1
    
    for c in ["StartDate", "EndDate"]:
        if c in dfs["FactSubscriptions"]:
            dfs["FactSubscriptions"][c] = pd.to_datetime(dfs["FactSubscriptions"][c], errors="coerce")

    # Step 2: Calculate core revenue and cost metrics
    dfs["FactSales"]["Revenue"] = revenue_from_sales(dfs["FactSales"])
    dfs["FactSales"]["CostAmt"] = cost_from_sales(dfs["FactSales"])

    # Step 3: Denormalize sales data into a unified 'Gold' table for fast dashboard reads
    sales = dfs["FactSales"].merge(dfs["DimDate"][["DateKey", "Date", "Year", "Month", "MonthIdx", "DateKeyMonth"]], on="DateKey", how="left") \
                      .merge(dfs["DimProduct"][["ProductID", "Category", "Subcategory", "ProductName"]], on="ProductID", how="left") \
                      .merge(dfs["DimChannel"][["ChannelID", "ChannelName", "Type"]], on="ChannelID", how="left") \
                      .merge(dfs["DimCustomer"][["CustomerID", "Region", "Country", "Segment"]], on="CustomerID", how="left")
    
    # Step 4: Enrich web session data with channel details
    web = dfs["FactWeb"].merge(dfs["DimDate"][["DateKey", "Date", "Year", "Month", "MonthIdx", "DateKeyMonth"]], on="DateKey", how="left") \
                  .merge(dfs["DimChannel"][["ChannelID", "ChannelName", "Type"]], on="ChannelID", how="left")

    # Step 5: Align budget data with the primary calendar
    budget = dfs["FactBudget"].merge(dfs["DimChannel"][["ChannelID", "ChannelName"]], on="ChannelID", how="left")
    budget = budget.merge(dfs["DimDate"][["DateKey", "Date", "DateKeyMonth"]].drop_duplicates(), on="DateKey", how="left")

    # Step 6: Persist enriched data to Parquet format for production use
    sales.to_parquet(os.path.join(output_dir, "sales_gold.parquet"), index=False)
    web.to_parquet(os.path.join(output_dir, "web_gold.parquet"), index=False)
    budget.to_parquet(os.path.join(output_dir, "budget_gold.parquet"), index=False)
    dfs["FactSubscriptions"].to_parquet(os.path.join(output_dir, "subscriptions_gold.parquet"), index=False)
    
    # Save dimensions just in case they are needed raw, but often they are burned into the gold tables
    dfs["DimDate"].to_parquet(os.path.join(output_dir, "dim_date.parquet"), index=False)
    dfs["DimChannel"].to_parquet(os.path.join(output_dir, "dim_channel.parquet"), index=False)
    dfs["DimCustomer"].to_parquet(os.path.join(output_dir, "dim_customer.parquet"), index=False)

    logger.info("ETL process completed successfully.")

if __name__ == "__main__":
    DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    OUTPUT_DIR = os.path.join(DATA_DIR, "processed")
    run_etl(DATA_DIR, OUTPUT_DIR)
