from flask import Flask, request, jsonify, render_template
import boto3
import mysql.connector
import os

try:
    from PIL import Image, ImageStat
except ImportError:
    Image = None

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

    min_price = request_args.get("min_price")
    max_price = request_args.get("max_price")
    if min_price is not None and min_price != "" and default_max_price is not None:
        filters.append("price >= %s")
        values.append(min_price)
    if max_price is not None and max_price != "" and default_max_price is not None:
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


def get_product_by_id(product_id):
    connection = get_db_connection()
    if connection is None:
        return None

    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, productDisplayname, price, gender, masterCategory, subCategory, ArticleType, baseCOlour, season FROM ecommerce_proj_data WHERE id = %s",
        (product_id,)
    )
    product = cursor.fetchone()
    if product:
        product["image_url"] = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': f"{product['id']}.jpg"},
            ExpiresIn=3600
        )
    return product


def nearest_color_name(rgb):
    color_map = {
        "red": (220, 20, 60),
        "blue": (30, 144, 255),
        "green": (34, 139, 34),
        "yellow": (240, 230, 140),
        "orange": (255, 165, 0),
        "pink": (255, 105, 180),
        "purple": (148, 0, 211),
        "brown": (165, 42, 42),
        "grey": (128, 128, 128),
        "black": (20, 20, 20),
        "white": (245, 245, 245)
    }
    r, g, b = rgb
    best_match = None
    best_distance = float('inf')
    for name, value in color_map.items():
        dist = (value[0] - r) ** 2 + (value[1] - g) ** 2 + (value[2] - b) ** 2
        if dist < best_distance:
            best_distance = dist
            best_match = name
    return best_match


def compute_average_color(file_stream):
    if Image is None:
        return None
    with Image.open(file_stream) as img:
        img = img.convert('RGB')
        stats = ImageStat.Stat(img)
        return tuple(int(v) for v in stats.mean)


def query_products_by_color(color_name, limit=12):
    connection = get_db_connection()
    if connection is None:
        return []

    cursor = connection.cursor(dictionary=True)
    like_value = f"%{color_name}%"
    query = """
        SELECT id, productDisplayname, price, gender, masterCategory, subCategory, ArticleType, baseCOlour, season
        FROM ecommerce_proj_data
        WHERE baseCOlour LIKE %s OR productDisplayname LIKE %s OR ArticleType LIKE %s
        LIMIT %s
    """
    cursor.execute(query, (like_value, like_value, like_value, limit))
    products = cursor.fetchall()
    for p in products:
        p["image_url"] = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': f"{p['id']}.jpg"},
            ExpiresIn=3600
        )
    return products


def categorize_product(product):
    article = (product.get('ArticleType') or '').lower()
    master = (product.get('masterCategory') or '').lower()

    if any(keyword in article for keyword in ['jean', 'pant', 'trouser', 'short', 'skirt', 'bottom']):
        return 'bottom'
    if any(keyword in master for keyword in ['jean', 'pant', 'trouser', 'short', 'skirt', 'bottom']):
        return 'bottom'
    if any(keyword in article for keyword in ['shirt', 'top', 'blouse', 'dress', 't-shirt', 'tee', 'sweater', 'jacket', 'coat', 'hoodie']):
        return 'top'
    if any(keyword in master for keyword in ['shirt', 'top', 'blouse', 'dress', 'sweater', 'jacket', 'coat', 'hoodie']):
        return 'top'
    return 'accessory'


def find_matching_products(product, groups, limit=4):
    connection = get_db_connection()
    if connection is None:
        return []

    color_match = product.get('baseCOlour', '')
    season = product.get('season', '')
    product_id = product.get('id')
    search_terms = [f"%{term}%" for term in groups]

    where_clauses = ["id != %s"]
    values = [product_id]
    if groups:
        group_clauses = []
        for term in groups:
            group_clauses.append("masterCategory LIKE %s")
            group_clauses.append("ArticleType LIKE %s")
            values.extend([f"%{term}%", f"%{term}%"])
        where_clauses.append("(" + " OR ".join(group_clauses) + ")")
    if color_match:
        where_clauses.append("baseCOlour LIKE %s")
        values.append(f"%{color_match}%")
    if season:
        where_clauses.append("season = %s")
        values.append(season)

    query = f"""
        SELECT id, productDisplayname, price, gender, masterCategory, subCategory, ArticleType, baseCOlour, season
        FROM ecommerce_proj_data
        WHERE {" AND ".join(where_clauses)}
        LIMIT %s
    """
    values.append(limit)
    cursor = connection.cursor(dictionary=True)
    cursor.execute(query, tuple(values))
    results = cursor.fetchall()
    for item in results:
        item["image_url"] = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': f"{item['id']}.jpg"},
            ExpiresIn=3600
        )
    return results


def recommend_outfit(product):
    category = categorize_product(product)
    if category == 'top':
        bottoms = find_matching_products(product, ['bottom', 'jean', 'skirt', 'short', 'trouser'], limit=3)
        accessories = find_matching_products(product, ['footwear', 'bag', 'watch', 'sunglass', 'jewellery'], limit=3)
        return {'bottoms': bottoms, 'accessories': accessories}
    if category == 'bottom':
        tops = find_matching_products(product, ['top', 'shirt', 'dress', 'blouse', 'sweater', 'jacket'], limit=3)
        accessories = find_matching_products(product, ['footwear', 'bag', 'watch', 'sunglass', 'jewellery'], limit=3)
        return {'tops': tops, 'accessories': accessories}
    return {
        'tops': find_matching_products(product, ['top', 'shirt', 'dress', 'blouse'], limit=3),
        'bottoms': find_matching_products(product, ['bottom', 'jean', 'skirt', 'short', 'trouser'], limit=3)
    }


@app.route('/image-search', methods=['POST'])
def image_search():
    if Image is None:
        return jsonify({'error': 'Image search requires Pillow package.'}), 500

    file = request.files.get('image')
    if not file:
        return jsonify({'error': 'Please upload an image file.'}), 400

    rgb = compute_average_color(file.stream)
    if not rgb:
        return jsonify({'error': 'Could not analyze image.'}), 400

    color_name = nearest_color_name(rgb)
    products = query_products_by_color(color_name, limit=16)
    return jsonify({'query_color': color_name, 'results': products})


@app.route('/style-match', methods=['GET'])
def style_match():
    product_id = request.args.get('product_id')
    if not product_id:
        return jsonify({'error': 'Missing product_id parameter.'}), 400

    product = get_product_by_id(product_id)
    if not product:
        return jsonify({'error': 'Product not found.'}), 404

    suggestions = recommend_outfit(product)
    return jsonify({'product': product, 'suggestions': suggestions})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
