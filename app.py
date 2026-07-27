from flask import Flask, request, jsonify, render_template
import boto3
import mysql.connector
import os

app = Flask(__name__)

# AWS S3 client (credentials from environment variables)
s3 = boto3.client(
    's3',
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
)

BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "ecommersfashion-images-bucket")

# MySQL connection (RDS credentials from environment variables)
db_host = os.environ.get("RDS_HOST", "awsrdsdatabase.cwhsqi0qgwid.us-east-1.rds.amazonaws.com")
db_user = os.environ.get("RDS_USER", "admin")
db_password = os.environ.get("RDS_PASSWORD", "Eval4545")
db_name = os.environ.get("RDS_DB", "SQLRDSAWS")

conn = mysql.connector.connect(
    host=db_host,
    user=db_user,
    password=db_password,
    database=db_name,
    use_pure=True
)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")

    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT id, gender, masterCategory, subCategory, ArticleType, baseCOlour,
               season, productDisplayname, price
        FROM ecommerce_proj_data
        WHERE productDisplayname LIKE %s OR baseCOlour LIKE %s OR gender LIKE %s
          OR masterCategory LIKE %s OR subCategory LIKE %s
        LIMIT 100
    """
    cursor.execute(query, (
        f"%{user_message}%", 
        f"%{user_message}%", 
        f"%{user_message}%", 
        f"%{user_message}%", 
        f"%{user_message}%"
    ))
    products = cursor.fetchall()

    results = []
    for product in products:
        image_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': f"{product['id']}.jpg"},
            ExpiresIn=3600
        )
        product["image_url"] = image_url
        results.append(product)

    return jsonify({"response": results})

# New route for product comparison
@app.route("/compare", methods=["POST"])
def compare():
    product_ids = request.json.get("products", [])
    if not product_ids or len(product_ids) < 2:
        return jsonify({"error": "Please select at least two products"}), 400

    cursor = conn.cursor(dictionary=True)
    format_strings = ','.join(['%s'] * len(product_ids))
    query = f"""
        SELECT id, productDisplayname, price, baseCOlour, gender, season, masterCategory, subCategory
        FROM ecommerce_proj_data
        WHERE id IN ({format_strings})
    """
    cursor.execute(query, tuple(product_ids))
    products = cursor.fetchall()

    comparison = []
    if len(products) == 2:
        p1, p2 = products
        comparison.append({
            "product1": p1["productDisplayname"],
            "product2": p2["productDisplayname"],
            "price_difference": abs(p1["price"] - p2["price"]),
            "same_category": p1["masterCategory"] == p2["masterCategory"],
            "same_colour": p1["baseCOlour"] == p2["baseCOlour"],
            "same_gender": p1["gender"] == p2["gender"],
            "season_match": p1["season"] == p2["season"]
        })

    return jsonify({"comparison": comparison})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
