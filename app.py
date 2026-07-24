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
        WHERE productDisplayname LIKE %s OR baseCOlour LIKE %s
        limit 20
    """
    cursor.execute(query, (f"%{user_message}%", f"%{user_message}%"))
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
