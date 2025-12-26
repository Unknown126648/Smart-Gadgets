from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///shop.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = "static/images"

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    price = db.Column(db.Float)
    description = db.Column(db.Text)
    category = db.Column(db.String(100))
    stock = db.Column(db.Integer, default=0)
    image= db.Column(db.String(200), default="noimage.jpg")

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    total = db.Column(db.Float)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"))
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"))
    quantity = db.Column(db.Integer)
    price = db.Column(db.Float)

def get_cart():
    return session.get("cart", {})

def save_cart(cart):
    session["cart"] = cart
    session.modified = True

@app.route("/")
def index():
    products = Product.query.all()
    return render_template("index.html", products=products)

@app.route("/product/<int:id>")
def product_page(id):
    product = Product.query.get_or_404(id)
    return render_template("product.html", product=product)

@app.route("/cart/add/<int:id>")
def add_to_cart(id):
    cart = get_cart()
    cart[str(id)] = cart.get(str(id), 0) + 1
    save_cart(cart)
    flash("Товар додано в кошик!")
    return redirect(url_for("index"))

@app.route("/cart")
def cart():
    cart = get_cart()
    items = []
    total = 0

    for id, qty in cart.items():
        p = Product.query.get(int(id))
        if p:
            subtotal = p.price * qty
            items.append({"product": p, "qty": qty, "subtotal": subtotal})
            total += subtotal

    return render_template("cart.html", items=items, total=total)

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = get_cart()
    if not cart:
        flash("Кошик порожній!")
        return redirect("/")

    if request.method == "POST":
        total = 0
        user_id = session.get("user_id")

        for id, qty in cart.items():
            p = Product.query.get(int(id))
            total += p.price * qty

        order = Order(total=total, user_id=user_id)
        db.session.add(order)
        db.session.commit()

        for id, qty in cart.items():
            p = Product.query.get(int(id))
            item = OrderItem(
                order_id=order.id, 
                product_id=p.id, 
                quantity=qty, 
                price=p.price
            )
            db.session.add(item)

        db.session.commit()
        session["cart"] = {}

        flash("Замовлення успішно оформленно!")
        return redirect("/")

    items = []
    total = 0

    for id, qty in cart.items():
        p = Product.query.get(int(id))
        if p:
            subtotal = p.price * qty
            items.append({
                "product": p, 
                "qty": qty, 
                "subtotal": subtotal
            })
            total += subtotal

    return render_template("checkout.html", items=items, total=total)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if User.query.filter_by(username=username).first():
            flash("Користувач вже існує!")
            return redirect("/register")

        u = User(username=username, password=generate_password_hash(password))
        db.session.add(u)
        db.session.commit()

        flash("Реєстрація успішна! Увійдіть.")
        return redirect("/login")

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password, password):
            flash("Невірні дані!")
            return redirect("/login")

        session["user_id"] = user.id
        session["is_admin"] = user.is_admin

        flash("Вхід успішний!")
        return redirect("/")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Вихід виконано.")
    return redirect("/")

@app.route("/admin")
def admin():
    if not session.get("is_admin"):
        return "Доступ заборонено!"

    products = Product.query.all()
    return render_template("admin.html", products=products)

@app.route("/admin/add", methods=["GET", "POST"])
def admin_add():
    if not session.get("is_admin"):
        return "Доступ заборонено!"

    if request.method == "POST":
        name = request.form["name"]
        price = float(request.form["price"])
        description = request.form["description"]
        category = request.form["category"]
        stock = int(request.form["stock"])
        image_file = request.files.get("image")

        filename = "noimage.jpg"

        if image_file and image_file.filename != "":
            filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        p = Product(
            name=name,
            price=price,
            description=description,
            category=category,
            stock=stock,
            image=filename
        )

        db.session.add(p)
        db.session.commit()

        flash("Товар додано!")
        return redirect("/admin")

    return render_template("admin_add.html")

@app.route("/admin/delete/<int:id>")
def admin_delete(id):
    if not session.get("is_admin"):
        return "Доступ заборонено!"

    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()

    flash("Товар видалено!")
    return redirect("/admin")

@app.route("/admin/edit/<int:id>", methods=["GET", "POST"])
def admin_edit(id):
    if not session.get("is_admin"):
        return "Доступ заборонено!"

    product = Product.query.get_or_404(id)

    if request.method == "POST":
        product.name = request.form["name"]
        product.price = float(request.form["price"])
        product.category = request.form["category"]
        product.stock = int(request.form["stock"])
        product.description = request.form["description"]

        image_file = request.files.get("image")

        if image_file and image_file.filename != "":
            filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            product.image = filename

        db.session.commit()
        flash("Товар оновлено!")
        return redirect("/admin")

    return render_template("admin_edit.html", product=product)

@app.cli.command("initdb")
def initdb():
    db.create_all()

    if not User.query.filter_by(username="admin").first():
        admin = User(
            username="admin",
            password=generate_password_hash("admin123"),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print("База даних створена!")

if __name__ == "__main__":
    app.run(debug=True)
