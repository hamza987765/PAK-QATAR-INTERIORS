from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import os
from werkzeug.utils import secure_filename
os.makedirs("static/images", exist_ok=True)
os.makedirs("static/uploads", exist_ok=True)
os.makedirs("static/uploads/service_designs", exist_ok=True)
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallback-secret")

ADMIN_USERNAME = "Admin"
ADMIN_PASSWORD = "ISBPESH"

UPLOAD_FOLDER = "static/images"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ---------- DATABASE ----------
def get_db():
    return sqlite3.connect("shop.db")


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        image TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL,
        stock INTEGER,
        image TEXT,
        category_id INTEGER,
        brand TEXT,
        FOREIGN KEY (category_id) REFERENCES categories(id)
    )
    """)
    c.execute("""
CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    image TEXT
)
""")

    c.execute("""
CREATE TABLE IF NOT EXISTS service_designs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id INTEGER,
    name TEXT NOT NULL,
    description TEXT,
    FOREIGN KEY (service_id) REFERENCES services(id)
)
""")
    c.execute("""
CREATE TABLE IF NOT EXISTS service_design_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    design_id INTEGER,
    image_path TEXT,
    FOREIGN KEY (design_id) REFERENCES service_designs(id)
)
""")
    
    conn.commit()
    conn.close()


init_db()


# ---------- HELPERS ----------
def admin_required():
    return session.get("admin")


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------- HOME ----------
@app.route("/")
def home():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, name, image FROM categories")
    categories = c.fetchall()
    # Services  ✅ IMPORTANT
    c.execute("SELECT * FROM services")
    services = c.fetchall()
    c.execute("SELECT * FROM service_designs")
    service_designs = c.fetchall()
    
    conn.close()
    return render_template("home.html", categories=categories, services=services, service_designs=service_designs)


# ---------- SHOP ----------
@app.route("/shop")
def shop():
    category = request.args.get("category")
    brand = request.args.get("brand")

    conn = get_db()
    c = conn.cursor()

    # If no category is selected → show ALL products
    if not category:

        c.execute("""
        SELECT id, name, price, stock, image, brand
        FROM products
        """)
        products = c.fetchall()

        conn.close()

        return render_template(
            "shop.html",
            products=products,
            selected_category=None,
            brands=[]
        )

    # Build query
    query = """
    SELECT products.id, products.name, products.price, products.stock, products.image, products.brand
    FROM products
    JOIN categories ON products.category_id = categories.id
    WHERE categories.name = ?
    """
    params = [category]

    if brand:
        query += " AND products.brand = ?"
        params.append(brand)

    c.execute(query, params)
    products = c.fetchall()

    # Fetch distinct brands for filter dropdown
    c.execute("""
        SELECT DISTINCT brand FROM products
        JOIN categories ON products.category_id = categories.id
        WHERE categories.name = ? AND brand IS NOT NULL AND brand != ''
    """, (category,))
    brands = [b[0] for b in c.fetchall()]

    conn.close()

    # AJAX response
    if request.args.get("ajax"):
        products_list = [
            {"id": p[0], "name": p[1], "price": p[2], "stock": p[3], "image": p[4], "brand": p[5]}
            for p in products
        ]
        return jsonify(products_list)

    return render_template("index.html", products=products, selected_category=category, brands=brands)


# ---------- ABOUT ----------
@app.route("/about")
def about():
    return render_template("about.html")


# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if (
            request.form["username"] == ADMIN_USERNAME
            and request.form["password"] == ADMIN_PASSWORD
        ):
            session["admin"] = True
            return redirect("/admin")
        return "Wrong credentials"
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")
# ---------- ADMIN ----------
@app.route("/admin")
def admin():
    if not admin_required():
        return redirect("/login")

    conn = get_db()
    c = conn.cursor()

    # CATEGORIES
    c.execute("SELECT * FROM categories")
    categories = c.fetchall()

    # PRODUCTS
    c.execute(""" 
        SELECT p.id, p.name, p.price, p.stock, p.category_id, p.brand, c.name
        FROM products p
        JOIN categories c ON p.category_id = c.id
    """)
    products = c.fetchall()

    # SERVICES
    c.execute("SELECT * FROM services")
    services = c.fetchall()

    # SERVICE DESIGNS
    c.execute("""
        SELECT sd.id, sd.service_id, sd.name, sd.description, sd.image
        FROM service_designs sd
        JOIN services s ON sd.service_id = s.id
    """)
    service_designs = c.fetchall()

    conn.close()

    return render_template(
        "admin.html",
        categories=categories,
        products=products,
        services=services,
        service_designs=service_designs
    )
@app.route("/delete-service-design/<int:id>")
def delete_service_design(id):

    conn = get_db()
    c = conn.cursor()

    c.execute("DELETE FROM service_designs WHERE id=?", (id,))

    conn.commit()
    conn.close()

    return redirect("/admin#service-designs")

@app.route("/edit-service-design/<int:id>", methods=["POST"])
def edit_service_design(id):
    if not admin_required():
        return redirect("/login")

    service_id = request.form["service_id"]
    name = request.form["name"]
    description = request.form["description"]

    image = request.files["image"]

    conn = get_db()
    c = conn.cursor()

    if image and image.filename:
        filename = secure_filename(image.filename)
        image.save(os.path.join("static/uploads", filename))

        c.execute("""
        UPDATE service_designs
        SET service_id=?, name=?, description=?, image=?
        WHERE id=?
        """, (service_id, name, description, filename, id))
    else:
        c.execute("""
        UPDATE service_designs
        SET service_id=?, name=?, description=?
        WHERE id=?
        """, (service_id, name, description, id))

    conn.commit()
    conn.close()

    return redirect("/admin#service-designs")

@app.route("/add-service", methods=["POST"])
def add_service():
    if not admin_required():
        return redirect("/login")

    title = request.form["title"]
    description = request.form["description"]
    image = request.files["service_image"]

    if image:
        filename = image.filename
        image_path = f"images/{filename}"
        image.save(os.path.join("static", image_path))

        conn = get_db()
        c = conn.cursor()
        c.execute(
            "INSERT INTO services (title, description, image) VALUES (?, ?, ?)",
            (title, description, image_path)
        )
        conn.commit()
        conn.close()

    return redirect("/admin")
@app.route("/edit-service/<int:id>", methods=["POST"])
def edit_service(id):
    if not admin_required():
        return redirect("/login")

    title = request.form["title"]
    description = request.form["description"]
    image = request.files["service_image"]

    conn = get_db()
    c = conn.cursor()

    if image and image.filename != "":
        filename = image.filename
        image_path = f"images/{filename}"
        image.save(os.path.join("static", image_path))

        c.execute("""
            UPDATE services
            SET title = ?, description = ?, image = ?
            WHERE id = ?
        """, (title, description, image_path, id))
    else:
        c.execute("""
            UPDATE services
            SET title = ?, description = ?
            WHERE id = ?
        """, (title, description, id))

    conn.commit()
    conn.close()

    return redirect("/admin")
@app.route("/delete-service/<int:id>")
def delete_service(id):
    if not admin_required():
        return redirect("/login")

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM services WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    return redirect("/admin")
@app.route("/service/<int:service_id>")
def service_page(service_id):
    conn = get_db()
    c = conn.cursor()

    service = c.execute(
        "SELECT * FROM services WHERE id=?", 
        (service_id,)
    ).fetchone()

    designs = c.execute("""
        SELECT sd.id, sd.name, sd.description,
               (SELECT image_path 
                FROM service_design_images 
                WHERE design_id = sd.id 
                LIMIT 1) as preview_image
        FROM service_designs sd
        WHERE sd.service_id=?
    """, (service_id,)).fetchall()

    conn.close()

    return render_template(
        "service_page.html",
        service=service,
        designs=designs
    )


@app.route("/design/<int:design_id>")
def design_detail(design_id):
    conn = sqlite3.connect("shop.db")
    c = conn.cursor()

    design = c.execute("SELECT * FROM service_designs WHERE id=?", (design_id,)).fetchone()
    images = c.execute("SELECT * FROM service_design_images WHERE design_id=?", (design_id,)).fetchall()

    conn.close()

    return render_template("design_detail.html", design=design, images=images)
@app.route("/add-service-design", methods=["POST"])
def add_service_design():
    service_id = request.form["service_id"]
    name = request.form["name"]
    description = request.form["description"]
    images = request.files.getlist("images")

    conn = sqlite3.connect("shop.db")
    c = conn.cursor()

    c.execute("INSERT INTO service_designs (service_id, name, description) VALUES (?, ?, ?)",
              (service_id, name, description))

    design_id = c.lastrowid

    for img in images:
        filename = secure_filename(img.filename)
        path = "uploads/service_designs/" + filename
        img.save("static/" + path)

        c.execute("INSERT INTO service_design_images (design_id, image_path) VALUES (?, ?)",
                  (design_id, path))

    conn.commit()
    conn.close()

    return redirect("/admin")

# ---------- ADD CATEGORY ----------
@app.route("/add-category", methods=["POST"])
def add_category():
    if not admin_required():
        return redirect("/login")

    name = request.form["name"]
    file = request.files.get("category_image")

    image_filename = None
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(UPLOAD_FOLDER, filename))
        image_filename = f"images/{filename}"

    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO categories (name, image) VALUES (?, ?)",
        (name, image_filename)
    )
    conn.commit()
    conn.close()

    return redirect("/admin")


# ---------- EDIT CATEGORY ----------
@app.route("/edit-category/<int:id>", methods=["POST"])
def edit_category(id):
    if not admin_required():
        return redirect("/login")

    new_name = request.form["name"]
    file = request.files.get("category_image")

    conn = get_db()
    c = conn.cursor()

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(UPLOAD_FOLDER, filename))
        image_path = f"images/{filename}"
        c.execute("UPDATE categories SET name = ?, image = ? WHERE id = ?", (new_name, image_path, id))
    else:
        c.execute("UPDATE categories SET name = ? WHERE id = ?", (new_name, id))

    conn.commit()
    conn.close()
    return redirect("/admin")


# ---------- ADD PRODUCT ----------
# ---------- PRODUCT DETAIL ----------
@app.route("/product/<int:id>")
def product_detail(id):
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT products.id, products.name, products.price,
               products.stock, products.image, products.brand,
               categories.name
        FROM products
        JOIN categories ON products.category_id = categories.id
        WHERE products.id = ?
    """, (id,))

    product = c.fetchone()
    conn.close()

    if not product:
        return "Product not found"

    return render_template("product_detail.html", product=product)

@app.route("/add-product", methods=["POST"])
def add_product():
    if not admin_required():
        return redirect("/login")

    name = request.form["name"]
    price = request.form["price"]
    stock = request.form["stock"]
    brand = request.form["brand"]
    category_id = request.form["category_id"]
    file = request.files["uploads"]

    if not allowed_file(file.filename):
        return "Invalid image"

    filename = secure_filename(file.filename)
    file.save(os.path.join(UPLOAD_FOLDER, filename))

    conn = get_db()
    c = conn.cursor()
    c.execute("""
    INSERT INTO products (name, price, stock, image, category_id, brand)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (name, price, stock, filename, category_id, brand))
    conn.commit()
    conn.close()
    return redirect("/admin")


# ---------- EDIT PRODUCT ----------
@app.route("/edit-product/<int:id>", methods=["POST"])
def edit_product(id):
    if not admin_required():
        return redirect("/login")

    data = request.form

    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE products
        SET name=?, brand=?, price=?, stock=?, category_id=?
        WHERE id=?
    """, (
        data["name"],
        data["brand"],
        data["price"],
        data["stock"],
        data["category_id"],
        id
    ))

    conn.commit()
    conn.close()

    return redirect("/admin")


# ---------- DELETE ----------
@app.route("/delete-product/<int:id>")
def delete_product(id):
    if not admin_required():
        return redirect("/login")
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect("/admin")


@app.route("/delete-category/<int:id>")
def delete_category(id):
    if not admin_required():
        return redirect("/login")
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE category_id = ?", (id,))
    c.execute("DELETE FROM categories WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect("/admin")


# ---------- RUN ----------
if __name__ == "__main__":
    app.run(debug=True)
