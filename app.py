from flask import Flask, request, jsonify, render_template
import boto3
import mysql.connector
import os

app = Flask(__name__)

# AWS S3 client
s3 = boto3.client(
    's3',
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
)

BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "ecommersfashion-images-bucket")

# MySQL connection
conn = mysql.connector.connect(
    host=os.environ.get("RDS_HOST"),
    user=os.environ.get("RDS_USER"),
    password=os.environ.get("RDS_PASSWORD"),
    database=os.environ.get("RDS_DB"),
    use_pure=True
)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/products", methods=["GET"])
def products():
    # Pagination
    page = int(request.args.get("page", 1))
    per_page = 16
    offset = (page - 1) * per_page

    # Filters
    filters = []
    values = []
    for field in ["gender", "masterCategory", "subCategory", "ArticleType", "baseCOlour", "season"]:
        val = request.args.get(field)
        if val:
            filters.append(f"{field} = %s")
            values.append(val)

    # Price filter
    min_price = request.args.get("min_price")
    max_price = request.args.get("max_price")
    if min_price:
        filters.append("price >= %s")
        values.append(min_price)
    if max_price:
        filters.append("price <= %s")
        values.append(max_price)

    where_clause = " AND ".join(filters) if filters else "1=1"

    cursor = conn.cursor(dictionary=True)
    query = f"""
        SELECT id, productDisplayname, price, gender, masterCategory, subCategory, ArticleType, baseCOlour, season
        FROM ecommerce_proj_data
        WHERE {where_clause}
        LIMIT %s OFFSET %s
    """
    cursor.execute(query, tuple(values + [per_page, offset]))
    products = cursor.fetchall()

    # Add image URLs
    for product in products:
        product["image_url"] = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': f"{product['id']}.jpg"},
            ExpiresIn=3600
        )

    return jsonify({"products": products})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
