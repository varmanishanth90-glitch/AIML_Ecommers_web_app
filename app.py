from flask import Flask, request, jsonify, render_template
import boto3
import mysql.connector
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

conn = None

# AWS S3 client
s3 = boto3.client(
    's3',
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
)

BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "ecommersfashion-images-bucket")

def get_db_connection():
    global conn
    if conn is not None:
        return conn

    host = os.environ.get("RDS_HOST")
    user = os.environ.get("RDS_USER")
    password = os.environ.get("RDS_PASSWORD")
    database = os.environ.get("RDS_DB")

    if not all([host, user, password, database]):
        return None

    try:
        conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            use_pure=True,
        )
        return conn
    except Exception:
        return None


def build_product_filters(request_args, default_max_price=None):
    filters = []
    values = []

    for field in ["gender", "masterCategory", "subCategory", "ArticleType", "baseCOlour", "season"]:
        val = request_args.get(field)
        if val:
            filters.append(f"{field} = %s")
            values.append(val)

    max_price = request_args.get("max_price")
    if max_price and default_max_price is not None and str(max_price) != str(default_max_price):
        filters.append("price <= %s")
        values.append(max_price)

    return filters, values


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/filters", methods=["GET"])
def filters():
    connection = get_db_connection()
    if connection is None:
        return jsonify({
            "gender": [],
            "masterCategory": [],
            "subCategory": [],
            "ArticleType": [],
            "baseCOlour": [],
            "season": [],
            "price_range": {"min": 0, "max": 100000},
        })

    cursor = connection.cursor()
    fields = ["gender", "masterCategory", "subCategory", "ArticleType", "baseCOlour", "season"]
    filter_data = {}
    for field in fields:
        cursor.execute(f"SELECT DISTINCT {field} FROM ecommerce_proj_data WHERE {field} IS NOT NULL AND {field} != ''")
        filter_data[field] = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT MIN(price), MAX(price) FROM ecommerce_proj_data WHERE price IS NOT NULL")
    min_price, max_price = cursor.fetchone()
    filter_data["price_range"] = {"min": min_price, "max": max_price}

    return jsonify(filter_data)

@app.route("/products", methods=["GET"])
def products():
    # ✅ Always show 16 products per page
    page = int(request.args.get("page", 1))
    per_page = 16
    offset = (page - 1) * per_page

    connection = get_db_connection()
    if connection is None:
        return jsonify({"products": [], "page": page})

    cursor = connection.cursor()
    cursor.execute("SELECT MAX(price) FROM ecommerce_proj_data WHERE price IS NOT NULL")
    db_max_price = cursor.fetchone()[0]

    filters, values = build_product_filters(request.args, db_max_price)
    where_clause = " AND ".join(filters) if filters else "1=1"

    cursor = connection.cursor(dictionary=True)
    query = f"""
        SELECT id, productDisplayname, price, gender, masterCategory, subCategory, ArticleType, baseCOlour, season
        FROM ecommerce_proj_data
        WHERE {where_clause}
        LIMIT %s OFFSET %s
    """
    cursor.execute(query, tuple(values + [per_page, offset]))
    products = cursor.fetchall()

    for product in products:
        product["image_url"] = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': f"{product['id']}.jpg"},
            ExpiresIn=3600
        )

    return jsonify({"products": products, "page": page})

@app.route("/compare", methods=["POST"])
def compare():
    product_ids = request.json.get("products", [])
    if not product_ids or len(product_ids) < 2:
        return jsonify({"error": "Please select at least two products"}), 400
    if len(product_ids) > 4:
        return jsonify({"error": "You can compare up to 4 products only"}), 400

    connection = get_db_connection()
    if connection is None:
        return jsonify({"comparison": []})

    cursor = connection.cursor(dictionary=True)
    format_strings = ','.join(['%s'] * len(product_ids))
    query = f"""
        SELECT id, productDisplayname, price, gender, masterCategory, subCategory, ArticleType, baseCOlour, season
        FROM ecommerce_proj_data
        WHERE id IN ({format_strings})
    """
    cursor.execute(query, tuple(product_ids))
    products = cursor.fetchall()

    for p in products:
        p["image_url"] = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': f"{p['id']}.jpg"},
            ExpiresIn=3600
        )

    return jsonify({"comparison": products})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
