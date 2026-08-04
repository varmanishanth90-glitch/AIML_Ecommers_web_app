# 🛍 AIML E-Commerce Web App

This project is a **Shopping Assistant Bot** built with Flask, MySQL (AWS RDS), and AWS S3. It delivers a modern shopping experience with product discovery, filtering, image search, and outfit recommendations.

---

## 🚀 Current Features

- Responsive shopping landing page with product discovery
- Product listing with filter controls for:
  - Gender
  - Master category
  - Subcategory
  - Article type
  - Base color
  - Season
- Price range filtering with live slider updates
- Paginated product grid showing 16 items per page
- Secure AWS S3 image URLs for each product image
- Select up to 4 products and compare them side-by-side in a modal
- Visual Search (Image Search):
  - Upload a reference image from the app
  - The system analyzes the image and finds similar products based on dominant color and matching product attributes
  - Results appear in a popup modal for quick browsing
- Personal Stylist (Style Match):
  - Click **Style Match** on any product card
  - The app suggests complementary tops, bottoms, and accessories to complete the outfit
  - Recommendations are shown in a modal overlay for an easy shopping experience

## 🧠 How to Use the Main Features

- Use the filters to narrow down products by category, color, season, and price.
- Use the Visual Search option to upload a photo and discover similar products.
- Use the Personal Stylist option to get outfit suggestions for a selected product.

---

## 🧩 Project Structure

- `app.py` — Flask backend and API routes
- `templates/index.html` — main frontend page and UI logic
- `static/style.css` — app styling and modal layout
- `requirements.txt` — Python dependencies
- `render.yaml` — deployment configuration

---

## ⚙️ Requirements

- Python 3.10+
- Flask
- boto3
- mysql-connector-python
- Pillow
- gunicorn

---

## 🚀 Running Locally

1. Create a virtual environment and activate it.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set environment variables for database and AWS credentials:
   - `RDS_HOST`
   - `RDS_USER`
   - `RDS_PASSWORD`
   - `RDS_DB`
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `AWS_DEFAULT_REGION`
   - `S3_BUCKET_NAME`
4. Run the app:
   ```bash
   python app.py
   ```
5. Open `http://localhost:5000` in your browser.

---

## 📌 Notes

- The image search feature requires `Pillow` to analyze uploaded images.
- Product image assets are expected to be stored in AWS S3 using the product ID as the object key.

