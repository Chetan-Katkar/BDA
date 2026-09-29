"""
E-Commerce Recommendation System Using Apache Spark
===================================================

A small, fully reproducible PySpark pipeline that turns raw e-commerce
transaction lines into personalised product recommendations using
collaborative filtering (Spark MLlib's ALS algorithm).

Pipeline
--------
    CSV transactions
        -> Spark DataFrame
        -> cleaning (drop invalid / missing rows)
        -> exploratory analysis
        -> build the user-item interaction matrix (implicit feedback)
        -> numeric index encoding for ALS
        -> train ALS model
        -> evaluate with RMSE
        -> generate top-N recommendations per customer

The bundled sample file is intentionally tiny so that the whole thing runs
on a laptop in under a minute. The *same* script, unchanged apart from the
input path, runs on millions of rows on a real Spark cluster -- that is the
point of using Spark rather than pandas.

Usage
-----
    python src/recommendation.py
    python src/recommendation.py --data data/online_retail_II.csv --top-n 10
    python src/recommendation.py --implicit          # implicit-feedback ALS

Author: Chetan Katkar and [ADD PARTNER NAME]
Course: Big Data Analytics - Assignment 10
"""

from __future__ import annotations

import argparse
import os
import sys

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F
from pyspark.ml.feature import StringIndexer
from pyspark.ml.recommendation import ALS, ALSModel
from pyspark.ml.evaluation import RegressionEvaluator


# Default location of the bundled demo file, resolved relative to this file so
# the script works from any working directory and on any operating system.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DATA = os.path.join(PROJECT_ROOT, "data", "sample_transactions.csv")

# Non-product stock codes used by the UCI Online Retail dataset for postage,
# manual adjustments, bank charges and so on. They are not recommendable items.
NON_PRODUCT_CODES = ["POST", "DOT", "M", "m", "C2", "BANK CHARGES", "S", "AMAZONFEE",
                     "PADS", "B", "CRUK", "D"]


# ---------------------------------------------------------------------------
# 1. Spark session
# ---------------------------------------------------------------------------
def create_spark_session(app_name: str = "EcommerceRecommendationSystem") -> SparkSession:
    """Create a local Spark session.

    ``local[*]`` asks Spark to use every available CPU core as a worker thread.
    On a real cluster you would submit the same code with
    ``spark-submit --master yarn`` (or k8s / standalone) and change nothing else.
    """
    spark = (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        # A small shuffle partition count keeps the demo fast; the default of
        # 200 partitions is meant for cluster-sized data, not a 1k-row CSV.
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.driver.memory", "2g")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark


# ---------------------------------------------------------------------------
# 2. Load
# ---------------------------------------------------------------------------
def load_transactions(spark: SparkSession, path: str) -> DataFrame:
    """Read the transaction CSV into a Spark DataFrame.

    ``inferSchema`` is convenient for a demo. For production-sized data you
    would pass an explicit ``StructType`` instead, because schema inference
    costs an extra full pass over the file.
    """
    if not os.path.exists(path):
        sys.exit(
            f"ERROR: data file not found: {path}\n"
            "Run the script without --data to use the bundled sample file, or see "
            "data/README.md for how to download the full Online Retail II dataset."
        )

    df = (
        spark.read
        .option("header", True)
        .option("inferSchema", True)
        .option("escape", '"')
        .csv(path)
    )

    # The full UCI Online Retail II export names two columns differently from
    # the 2010-2011 export. Normalise them so both files work unchanged.
    renames = {"Invoice": "InvoiceNo", "Price": "UnitPrice", "Customer ID": "CustomerID"}
    for old, new in renames.items():
        if old in df.columns and new not in df.columns:
            df = df.withColumnRenamed(old, new)

    required = {"StockCode", "Quantity", "UnitPrice", "CustomerID"}
    missing = required - set(df.columns)
    if missing:
        sys.exit(f"ERROR: input file is missing required column(s): {sorted(missing)}")

    return df


# ---------------------------------------------------------------------------
# 3. Clean
# ---------------------------------------------------------------------------
def clean_transactions(df: DataFrame) -> DataFrame:
    """Remove the records that would poison the recommendation model.

    Real retail exports always contain rows that are not genuine purchases:
    cancelled orders, rows with no customer attached (guest / till sales),
    free samples and postage lines. Each rule below is printed so the effect
    of cleaning is visible when the script runs.
    """
    print("\n=== STEP 2: DATA CLEANING ===")
    before = df.count()
    print(f"Rows before cleaning : {before:,}")

    cleaned = (
        df
        # A customer id is mandatory: without it there is no "user" to model.
        .filter(F.col("CustomerID").isNotNull())
        .filter(F.trim(F.col("CustomerID").cast("string")) != "")
        .filter(F.col("StockCode").isNotNull())
        # Negative quantities are returns / cancellations, zero is a data error.
        .filter(F.col("Quantity") > 0)
        # Zero or negative prices are adjustments, samples and write-offs.
        .filter(F.col("UnitPrice") > 0)
    )

    # Credit notes are flagged with a leading "C" on the invoice number.
    if "InvoiceNo" in cleaned.columns:
        cleaned = cleaned.filter(~F.upper(F.col("InvoiceNo").cast("string")).startswith("C"))

    # Drop postage / admin lines, then drop exact duplicate rows.
    cleaned = (
        cleaned
        .filter(~F.upper(F.trim(F.col("StockCode").cast("string")))
                 .isin([c.upper() for c in NON_PRODUCT_CODES]))
        .withColumn("CustomerID", F.col("CustomerID").cast("double").cast("int"))
        .withColumn("StockCode", F.trim(F.col("StockCode").cast("string")))
        .dropDuplicates()
    )

    after = cleaned.count()
    print(f"Rows after cleaning  : {after:,}  (removed {before - after:,})")
    return cleaned


# ---------------------------------------------------------------------------
# 4. Exploratory analysis
# ---------------------------------------------------------------------------
def explore(df: DataFrame) -> None:
    """Print a few simple aggregates so we understand the data before modelling."""
    print("\n=== STEP 3: EXPLORATORY DATA ANALYSIS ===")

    n_customers = df.select("CustomerID").distinct().count()
    n_products = df.select("StockCode").distinct().count()
    n_rows = df.count()
    density = n_rows / (n_customers * n_products) * 100

    print(f"Transaction lines : {n_rows:,}")
    print(f"Unique customers  : {n_customers:,}")
    print(f"Unique products   : {n_products:,}")
    print(f"Matrix density    : {density:.2f}%  "
          f"(the user-item matrix is {100 - density:.2f}% empty -- this sparsity "
          "is exactly what collaborative filtering exploits)")

    print("\nTop 10 products by total quantity sold:")
    label = "Description" if "Description" in df.columns else "StockCode"
    (df.groupBy("StockCode", label)
       .agg(F.sum("Quantity").alias("TotalQuantity"),
            F.countDistinct("CustomerID").alias("Customers"))
       .orderBy(F.desc("TotalQuantity"))
       .show(10, truncate=45))

    print("Top 5 customers by total spend:")
    (df.withColumn("LineRevenue", F.col("Quantity") * F.col("UnitPrice"))
       .groupBy("CustomerID")
       .agg(F.round(F.sum("LineRevenue"), 2).alias("TotalSpend"),
            F.countDistinct("StockCode").alias("DistinctProducts"))
       .orderBy(F.desc("TotalSpend"))
       .show(5))

    if "Country" in df.columns:
        print("Transactions by country (top 5):")
        df.groupBy("Country").count().orderBy(F.desc("count")).show(5, truncate=False)


def product_name_lookup(df: DataFrame) -> DataFrame | None:
    """One readable description per stock code (the most frequently used one).

    The same product code sometimes appears with slightly different spellings,
    so we keep whichever description was used most often.
    """
    if "Description" not in df.columns:
        return None
    most_common = Window.partitionBy("StockCode").orderBy(F.desc("count"))
    return (df.groupBy("StockCode", "Description").count()
              .withColumn("rank", F.row_number().over(most_common))
              .filter(F.col("rank") == 1)
              .select("StockCode", "Description"))


# ---------------------------------------------------------------------------
# 5. Build the user-item interaction matrix
# ---------------------------------------------------------------------------
def build_interactions(df: DataFrame, min_interactions: int = 2) -> DataFrame:
    """Turn transaction *lines* into one implicit rating per (customer, product).

    E-commerce data has no star ratings, so we derive an interest score from
    behaviour. Two signals are combined:

        purchases = how many separate times the customer bought the product
        quantity  = how many units in total

    A raw quantity would let one bulk order dominate the model, so the score is
    log-compressed with ``log1p`` and then scaled into a familiar 1-5 range.
    This is the standard "implicit feedback" trick.
    """
    print("\n=== STEP 4: BUILDING THE USER-ITEM INTERACTION MATRIX ===")

    interactions = (
        df.groupBy("CustomerID", "StockCode")
          .agg(F.sum("Quantity").alias("TotalQuantity"),
               F.count(F.lit(1)).alias("Purchases"))
          # log1p keeps big buyers ahead of small ones without letting a single
          # 500-unit order swamp everything else.
          .withColumn("RawScore",
                      F.log1p(F.col("TotalQuantity")) + F.col("Purchases"))
    )

    # Scale RawScore into [1, 5] so that the RMSE we report later is easy to
    # interpret on the same scale as a familiar 1-5 star rating.
    bounds = interactions.agg(F.min("RawScore").alias("lo"),
                              F.max("RawScore").alias("hi")).first()
    lo, hi = float(bounds["lo"]), float(bounds["hi"])
    span = (hi - lo) or 1.0   # guard against a division by zero on tiny inputs

    interactions = interactions.withColumn(
        "Rating", F.round(F.lit(1.0) + 4.0 * (F.col("RawScore") - F.lit(lo)) / F.lit(span), 4)
    )

    # Customers who bought only one distinct product give the model nothing to
    # learn from and cannot be evaluated, so they are held back.
    active = (interactions.groupBy("CustomerID").count()
                          .filter(F.col("count") >= min_interactions)
                          .select("CustomerID"))
    interactions = interactions.join(active, on="CustomerID", how="inner").cache()

    print(f"User-item pairs   : {interactions.count():,}")
    print(f"Rating range      : 1.0 to 5.0 (log-scaled implicit score)")
    print("\nSample of the interaction matrix:")
    interactions.select("CustomerID", "StockCode", "Purchases",
                        "TotalQuantity", "Rating").show(8)
    return interactions


def encode_ids(interactions: DataFrame) -> tuple[DataFrame, DataFrame]:
    """ALS needs numeric user and item ids, so index the string/int keys.

    ``StringIndexer`` assigns 0, 1, 2 ... in order of frequency. We keep the
    mapping so recommendations can be translated back into real stock codes.
    """
    user_indexer = StringIndexer(inputCol="CustomerID", outputCol="userIndex",
                                 handleInvalid="skip")
    item_indexer = StringIndexer(inputCol="StockCode", outputCol="itemIndex",
                                 handleInvalid="skip")

    indexed = user_indexer.fit(interactions).transform(interactions)
    indexed = item_indexer.fit(indexed).transform(indexed)
    indexed = (indexed
               .withColumn("userIndex", F.col("userIndex").cast("int"))
               .withColumn("itemIndex", F.col("itemIndex").cast("int"))
               .cache())

    # Lookup table used to turn itemIndex back into a readable product.
    item_lookup = indexed.select("itemIndex", "StockCode").distinct().cache()
    return indexed, item_lookup


# ---------------------------------------------------------------------------
# 6. Train
# ---------------------------------------------------------------------------
def train_als(train: DataFrame, rank: int = 10, max_iter: int = 15,
              reg_param: float = 0.1, implicit: bool = False) -> ALSModel:
    """Fit Spark MLlib's ALS collaborative-filtering model.

    ALS factorises the sparse user-item matrix R into two dense matrices,
    U (users x rank) and V (items x rank), such that ``U . V^T`` approximates R.
    It alternates: hold V fixed and solve for U, hold U fixed and solve for V.
    Each of those steps is an independent least-squares problem *per user* (or
    per item), which is why the algorithm parallelises so well across a cluster.
    """
    print("\n=== STEP 5: TRAINING THE ALS MODEL ===")
    print(f"rank={rank}  maxIter={max_iter}  regParam={reg_param}  "
          f"implicitPrefs={implicit}")

    als = ALS(
        userCol="userIndex",
        itemCol="itemIndex",
        ratingCol="Rating",
        rank=rank,                     # number of latent factors per user/item
        maxIter=max_iter,              # ALS alternations
        regParam=reg_param,            # L2 regularisation, guards overfitting
        implicitPrefs=implicit,        # True -> treat ratings as confidence
        # Users or items that appear only in the test split produce NaN
        # predictions; dropping them keeps the RMSE finite and honest.
        coldStartStrategy="drop",
        nonnegative=True,
        seed=42,
    )

    model = als.fit(train)
    print("Model trained. "
          f"User factors: {model.userFactors.count()}, "
          f"item factors: {model.itemFactors.count()}")
    return model


# ---------------------------------------------------------------------------
# 7. Evaluate
# ---------------------------------------------------------------------------
def evaluate(model: ALSModel, test: DataFrame) -> float | None:
    """Report RMSE on the held-out split.

    RMSE is the average error between the predicted and the actual interest
    score, on the same 1-5 scale. Lower is better. For implicit feedback RMSE
    is only a rough guide -- ranking metrics such as precision@k matter more in
    production -- but it is the standard quick check and it is what MLlib's
    RegressionEvaluator gives us.
    """
    print("\n=== STEP 6: EVALUATION ===")
    predictions = model.transform(test)
    n = predictions.count()
    if n == 0:
        print("Test split produced no scorable rows (too little data) -- RMSE skipped.")
        return None

    evaluator = RegressionEvaluator(metricName="rmse", labelCol="Rating",
                                    predictionCol="prediction")
    rmse = evaluator.evaluate(predictions)
    mae = RegressionEvaluator(metricName="mae", labelCol="Rating",
                              predictionCol="prediction").evaluate(predictions)

    print(f"Scored test rows  : {n:,}")
    print(f"RMSE              : {rmse:.4f}  (on the 1-5 interest scale)")
    print(f"MAE               : {mae:.4f}")
    print("\nSample predictions vs actual:")
    predictions.select("CustomerID", "StockCode", "Rating",
                       F.round("prediction", 4).alias("prediction")).show(8)
    return rmse


# ---------------------------------------------------------------------------
# 8. Generate recommendations
# ---------------------------------------------------------------------------
def recommend(model: ALSModel, indexed: DataFrame, item_lookup: DataFrame,
              product_names: DataFrame | None, top_n: int = 5,
              show_users: int = 5, exclude_purchased: bool = True) -> DataFrame:
    """Produce the top-N products for every customer and print a readable sample.

    ``recommendForAllUsers`` scores every user against every item using the
    learned latent factors. By default we then remove products the customer has
    already bought -- recommending something already in their order history is
    correct arithmetic but useless merchandising.
    """
    print(f"\n=== STEP 7: TOP-{top_n} RECOMMENDATIONS PER CUSTOMER ===")

    owned = indexed.select("userIndex", "itemIndex").distinct()

    # Ask for extra candidates so that enough survive the "already bought" filter.
    max_owned = (owned.groupBy("userIndex").count()
                      .agg(F.max("count")).first()[0] or 0)
    n_candidates = top_n + int(max_owned) if exclude_purchased else top_n

    # recommendForAllUsers returns an array of structs; explode it into rows.
    candidates = (
        model.recommendForAllUsers(n_candidates)
        .select("userIndex", F.explode("recommendations").alias("rec"))
        .select("userIndex",
                F.col("rec.itemIndex").alias("itemIndex"),
                F.round(F.col("rec.rating"), 4).alias("score"))
    )

    if exclude_purchased:
        candidates = candidates.join(owned, on=["userIndex", "itemIndex"], how="left_anti")

    # Keep the best top_n per user after filtering.
    best = Window.partitionBy("userIndex").orderBy(F.desc("score"))
    candidates = (candidates.withColumn("rank", F.row_number().over(best))
                            .filter(F.col("rank") <= top_n))

    # Translate the numeric indices back into real customer and product ids.
    user_lookup = indexed.select("userIndex", "CustomerID").distinct()
    recs = (candidates
            .join(user_lookup, on="userIndex", how="inner")
            .join(item_lookup, on="itemIndex", how="inner")
            .select("CustomerID", "rank", "StockCode", "score"))

    if product_names is not None:
        recs = (recs.join(product_names, on="StockCode", how="left")
                    .select("CustomerID", "rank", "StockCode", "Description", "score"))

    recs = recs.orderBy("CustomerID", "rank").cache()

    sample_users = [r["CustomerID"] for r in
                    recs.select("CustomerID").distinct()
                        .orderBy("CustomerID").limit(show_users).collect()]

    for customer in sample_users:
        print(f"\n--- Customer {customer} ---")
        print("Already purchased (top 5 by interest score):")
        (indexed.filter(F.col("CustomerID") == customer)
                .select("StockCode", "Purchases", "TotalQuantity",
                        F.round("Rating", 2).alias("Rating"))
                .orderBy(F.desc("Rating")).show(5, truncate=40))
        print(f"Recommended next (top {top_n}, excluding items already bought):")
        recs.filter(F.col("CustomerID") == customer).show(top_n, truncate=45)

    return recs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="E-commerce recommendation system built with Apache Spark MLlib (ALS).")
    parser.add_argument("--data", default=DEFAULT_DATA,
                        help="path to the transactions CSV (default: bundled sample)")
    parser.add_argument("--top-n", type=int, default=5,
                        help="number of products to recommend per customer (default: 5)")
    parser.add_argument("--rank", type=int, default=10,
                        help="number of ALS latent factors (default: 10)")
    parser.add_argument("--max-iter", type=int, default=15,
                        help="ALS iterations (default: 15)")
    parser.add_argument("--reg-param", type=float, default=0.1,
                        help="ALS regularisation parameter (default: 0.1)")
    parser.add_argument("--include-purchased", action="store_true",
                        help="do not filter out products the customer already bought")
    parser.add_argument("--implicit", action="store_true",
                        help="use implicit-feedback ALS instead of explicit ratings")
    parser.add_argument("--save-recs", metavar="DIR", default=None,
                        help="optional directory to write all recommendations as CSV")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    spark = create_spark_session()
    print("=" * 72)
    print("E-COMMERCE RECOMMENDATION SYSTEM USING APACHE SPARK")
    print("=" * 72)
    print(f"Spark version : {spark.version}")
    print(f"Master        : {spark.sparkContext.master}")
    print(f"Input file    : {args.data}")

    try:
        print("\n=== STEP 1: LOADING DATA ===")
        raw = load_transactions(spark, args.data)
        print("Schema:")
        raw.printSchema()
        raw.show(5, truncate=40)

        clean = clean_transactions(raw)
        explore(clean)

        # Keep a product-code -> description lookup for readable output.
        names = product_name_lookup(clean)

        interactions = build_interactions(clean)
        indexed, item_lookup = encode_ids(interactions)

        # 80/20 split. A random split is fine for this demo; for a production
        # system you would split by time so the model is never tested on data
        # that came before what it trained on.
        train, test = indexed.randomSplit([0.8, 0.2], seed=42)
        print(f"\nTrain rows: {train.count():,}   Test rows: {test.count():,}")

        model = train_als(train, rank=args.rank, max_iter=args.max_iter,
                          reg_param=args.reg_param, implicit=args.implicit)
        evaluate(model, test)

        recs = recommend(model, indexed, item_lookup, names, top_n=args.top_n,
                         exclude_purchased=not args.include_purchased)

        if args.save_recs:
            (recs.coalesce(1).write.mode("overwrite")
                 .option("header", True).csv(args.save_recs))
            print(f"\nAll recommendations written to: {args.save_recs}")

        print("\n" + "=" * 72)
        print("PIPELINE COMPLETE")
        print("=" * 72)
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    raise SystemExit(main())
