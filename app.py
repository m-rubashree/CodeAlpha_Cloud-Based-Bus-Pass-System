import os
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from jinja2 import DictLoader
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///bus_booking_system.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Tamil Nadu's 38 districts
DISTRICTS = [
    "Ariyalur", "Chengalpattu", "Chennai", "Coimbatore", "Cuddalore",
    "Dharmapuri", "Dindigul", "Erode", "Kallakurichi", "Kancheepuram",
    "Kanniyakumari", "Karur", "Krishnagiri", "Madurai", "Mayiladuthurai",
    "Nagapattinam", "Namakkal", "Nilgiris", "Perambalur", "Pudukkottai",
    "Ramanathapuram", "Ranipet", "Salem", "Sivaganga", "Tenkasi",
    "Thanjavur", "Theni", "Thoothukudi", "Tiruchirappalli", "Tirunelveli",
    "Tirupathur", "Tiruppur", "Tiruvallur", "Tiruvannamalai",
    "Tiruvarur", "Vellore", "Viluppuram", "Virudhunagar"
]

BUS_IMAGE = "https://images.unsplash.com/photo-1570125909232-eb263c188f7e?w=1200&auto=format&fit=crop&q=85"
INTERIOR_IMAGE = "https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?w=1200&auto=format&fit=crop&q=85"


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)


class Bus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    operator = db.Column(db.String(120), nullable=False)
    bus_type = db.Column(db.String(80), nullable=False)
    source = db.Column(db.String(80), nullable=False, default="Chennai")
    destination = db.Column(db.String(80), nullable=False)
    departure = db.Column(db.String(10), nullable=False)
    arrival = db.Column(db.String(10), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    seats = db.Column(db.Integer, nullable=False, default=30)
    image_url = db.Column(db.String(500), nullable=False, default=BUS_IMAGE)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    bus_id = db.Column(db.Integer, db.ForeignKey("bus.id"), nullable=False)
    travel_date = db.Column(db.String(10), nullable=False)
    seat_number = db.Column(db.Integer, nullable=False)
    booked_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", backref="bookings")
    bus = db.relationship("Bus", backref="bookings")
    __table_args__ = (
        db.UniqueConstraint("bus_id", "travel_date", "seat_number",
                            name="unique_bus_date_seat"),
    )


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    bus_id = db.Column(db.Integer, db.ForeignKey("bus.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User")
    bus = db.relationship("Bus", backref="reviews")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "info")
            next_page = request.path
            if request.endpoint == "book":
                next_page = url_for("bus_details", bus_id=kwargs.get("bus_id"),
                                    date=request.form.get("travel_date", ""))
            return redirect(url_for("login", next=next_page))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_globals():
    return {"districts": DISTRICTS, "current_user": User.query.get(session.get("user_id")) if session.get("user_id") else None}


@app.route("/")
def index():
    return render_template("index.html", bus_image=BUS_IMAGE,
                           today=datetime.now().strftime("%Y-%m-%d"))


@app.route("/search")
def search():
    source = request.args.get("source", "Chennai").strip()
    destination = request.args.get("destination", "").strip()
    travel_date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    buses = []
    if source in DISTRICTS and destination in DISTRICTS and source != destination:
        buses = Bus.query.filter_by(source=source, destination=destination).order_by(Bus.departure).all()
    return render_template("search.html", buses=buses, source=source,
                           destination=destination, travel_date=travel_date,
                           bus_image=BUS_IMAGE)


@app.route("/bus/<int:bus_id>")
def bus_details(bus_id):
    bus = Bus.query.get_or_404(bus_id)
    travel_date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    reviews = Review.query.filter_by(bus_id=bus.id).order_by(Review.created_at.desc()).all()
    occupied = {b.seat_number for b in Booking.query.filter_by(
        bus_id=bus.id, travel_date=travel_date).all()}
    return render_template("bus.html", bus=bus, reviews=reviews,
                           travel_date=travel_date, occupied=occupied,
                           bus_image=BUS_IMAGE, interior_image=INTERIOR_IMAGE)


@app.route("/bus/<int:bus_id>/review", methods=["POST"])
@login_required
def add_review(bus_id):
    bus = Bus.query.get_or_404(bus_id)
    try:
        rating = int(request.form.get("rating", "5"))
    except ValueError:
        rating = 0
    comment = request.form.get("comment", "").strip()
    if rating not in range(1, 6) or not comment:
        flash("Choose a rating and enter a review.", "error")
    else:
        db.session.add(Review(user_id=session["user_id"], bus_id=bus.id,
                              rating=rating, comment=comment[:500]))
        db.session.commit()
        flash("Thank you! Your review was added.", "success")
    return redirect(url_for("bus_details", bus_id=bus.id))


@app.route("/book/<int:bus_id>", methods=["POST"])
@login_required
def book(bus_id):
    bus = Bus.query.get_or_404(bus_id)
    travel_date = request.form.get("travel_date", "")
    try:
        date_obj = datetime.strptime(travel_date, "%Y-%m-%d").date()
        seat_number = int(request.form.get("seat_number", "0"))
    except (ValueError, TypeError):
        flash("Please choose a valid date and seat.", "error")
        return redirect(url_for("bus_details", bus_id=bus.id))
    if date_obj < datetime.now().date():
        flash("Travel date cannot be in the past.", "error")
        return redirect(url_for("bus_details", bus_id=bus.id, date=travel_date))
    if seat_number < 1 or seat_number > bus.seats:
        flash("Please choose a valid seat.", "error")
        return redirect(url_for("bus_details", bus_id=bus.id, date=travel_date))
    booking = Booking(user_id=session["user_id"], bus_id=bus.id,
                      travel_date=travel_date, seat_number=seat_number)
    db.session.add(booking)
    try:
        db.session.commit()
        flash("Your bus ticket has been booked successfully!", "success")
        return redirect(url_for("my_bookings"))
    except IntegrityError:
        db.session.rollback()
        flash("That seat has already been booked. Please choose another seat.", "error")
        return redirect(url_for("bus_details", bus_id=bus.id, date=travel_date))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter your name, a valid email, and a password of at least 8 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("An account with this email already exists.", "error")
        else:
            user = User(name=name, email=email,
                        password_hash=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            session["user_id"] = user.id
            flash("Account created. You are now logged in.", "success")
            return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            flash("Welcome back!", "success")
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("index"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/my-bookings")
@login_required
def my_bookings():
    bookings = Booking.query.filter_by(user_id=session["user_id"]).order_by(
        Booking.travel_date.desc(), Booking.id.desc()).all()
    return render_template("my_bookings.html", bookings=bookings)


@app.route("/admin")
@login_required
def admin():
    user = User.query.get(session["user_id"])
    if not user or not user.is_admin:
        flash("Admin access required.", "error")
        return redirect(url_for("index"))
    return render_template("admin.html", buses=Bus.query.order_by(Bus.destination).all(),
                           bookings=Booking.query.order_by(Booking.id.desc()).all())


def seed_data():
    # Create a private demo admin if one does not exist. Credentials are not shown on the login page.
    admin_email = os.environ.get("BUS_ADMIN_EMAIL", "admin@bus.com").strip().lower()
    admin_password = os.environ.get("BUS_ADMIN_PASSWORD", "Admin@12345")
    if not User.query.filter_by(email=admin_email).first():
        db.session.add(User(name="Administrator", email=admin_email,
                            password_hash=generate_password_hash(admin_password),
                            is_admin=True))
    # Demo bus inventory: one daily listing from Chennai to each other TN district.
    if Bus.query.count() == 0:
        for i, district in enumerate(DISTRICTS):
            if district == "Chennai":
                continue
            db.session.add(Bus(
                operator=["Southern Travels", "GreenLine Express", "Tamil Route Travels"][i % 3],
                bus_type=["AC Sleeper", "AC Seater", "Non-AC Sleeper"][i % 3],
                source="Chennai", destination=district,
                departure=["20:30", "21:15", "22:00"][i % 3],
                arrival=["05:30", "06:15", "07:00"][i % 3],
                price=450 + (i * 35),
                seats=30, image_url=BUS_IMAGE
            ))
    db.session.commit()


with app.app_context():
    db.create_all()
    seed_data()


BASE = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}Travel across India{% endblock %}</title>
<style>
:root{--green:#147653;--dark:#10251d;--muted:#718078;--line:#e2ebe5;--bg:#f5f8f6;--white:#fff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--dark);font-family:Inter,Segoe UI,Arial,sans-serif}
a{color:inherit;text-decoration:none}.nav{height:72px;background:#fff;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 max(5%,calc((100% - 1250px)/2));position:sticky;top:0;z-index:5}
.brand{font-weight:850;font-size:20px;letter-spacing:-.7px}.brand span{color:var(--green)}.links{display:flex;gap:22px;align-items:center;font-size:14px}.links a:hover{color:var(--green)}
.btn{border:0;border-radius:12px;background:var(--green);color:white;padding:13px 19px;font-weight:700;cursor:pointer;display:inline-block}.btn:hover{background:#0e5d40}.btn.light{background:#e8f4ed;color:var(--green)}.container{max-width:1250px;margin:0 auto;padding:35px 24px}
h1,h2,h3,p{margin-top:0}.muted{color:var(--muted)}.eyebrow{color:var(--green);font-size:11px;font-weight:800;letter-spacing:2px;text-transform:uppercase}
.card{background:#fff;border:1px solid var(--line);border-radius:18px;padding:22px;box-shadow:0 10px 30px #183a2510}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:18px}
input,select,textarea{width:100%;padding:14px;border:1px solid var(--line);border-radius:11px;background:#fff;font:inherit;color:var(--dark);outline:none}
input:focus,select:focus,textarea:focus{border-color:var(--green);box-shadow:0 0 0 3px #14765318}label{display:block;font-size:12px;font-weight:750;margin:0 0 7px}.field{margin-bottom:15px}
.flash{padding:13px 16px;border-radius:10px;margin:0 0 12px;background:#eaf5ee;color:#17613f}.flash.error{background:#fff0ee;color:#a33328}.flash.info{background:#edf4ff;color:#24518a}
.hero{display:grid;grid-template-columns:1fr 1.08fr;gap:48px;align-items:center;padding:38px 0 48px}.hero h1{font-size:clamp(42px,5vw,76px);line-height:1.02;letter-spacing:-3px;margin:22px 0}.hero h1 span{color:var(--green)}.hero p{font-size:17px;line-height:1.7;color:var(--muted);max-width:560px}
.hero-img{height:370px;width:100%;object-fit:cover;border-radius:28px;background:#dcebe2;box-shadow:0 20px 55px #183a2520}.searchbox{margin-top:10px}.searchgrid{display:grid;grid-template-columns:1fr 1fr 1fr auto;gap:12px;align-items:end}.popular{font-size:12px;color:var(--muted);margin-top:15px}
.bus-card{padding:0;overflow:hidden}.bus-card img{width:100%;height:175px;object-fit:cover;background:#dcebe2}.bus-body{padding:18px}.bus-top{display:flex;justify-content:space-between;gap:10px}.price{font-size:22px;font-weight:850;color:var(--green)}.pill{display:inline-block;background:#eaf5ee;color:var(--green);padding:6px 10px;border-radius:20px;font-size:11px;font-weight:750}
.seat-grid{display:grid;grid-template-columns:repeat(5,48px);gap:10px;margin:18px 0}.seat{padding:11px 0;border-radius:9px;border:1px solid #b6d7c4;background:#eff8f2;color:#17613f;text-align:center;cursor:pointer;font-size:12px}.seat input{display:none}.seat:has(input:checked){background:var(--green);color:white}.seat.booked{background:#e7e9e8;color:#9aa19d;border-color:#e7e9e8;cursor:not-allowed}.review{border-top:1px solid var(--line);padding:14px 0}.stars{color:#e5a522;letter-spacing:2px}.form-card{max-width:480px;margin:25px auto}.table{width:100%;border-collapse:collapse}.table th,.table td{text-align:left;padding:12px;border-bottom:1px solid var(--line);font-size:13px}
footer{text-align:center;padding:30px;color:var(--muted);font-size:12px}
@media(max-width:800px){.hero{grid-template-columns:1fr;gap:25px}.hero-img{height:260px}.searchgrid{grid-template-columns:1fr 1fr}.links{gap:10px}.nav{padding:0 4%;}.container{padding:24px 16px}}
@media(max-width:520px){.searchgrid{grid-template-columns:1fr}.links a:nth-child(2){display:none}.hero h1{letter-spacing:-1.5px}.seat-grid{grid-template-columns:repeat(5,1fr)}}
</style>
</head>
<body>
<nav class="nav"><a class="brand" href="{{ url_for('index') }}">Travel<span>Across</span>India</a>
<div class="links"><a href="{{ url_for('index') }}">Home</a><a href="{{ url_for('my_bookings') }}">My tickets</a>
{% if current_user %}<span class="muted">Hi, {{ current_user.name }}</span><a href="{{ url_for('logout') }}">Logout</a>
{% else %}<a href="{{ url_for('login') }}">Login</a><a class="btn" href="{{ url_for('register') }}">Sign up</a>{% endif %}</div></nav>
<main class="container">
{% with messages = get_flashed_messages(with_categories=true) %}{% for category,message in messages %}<div class="flash {{ category }}">{{ message }}</div>{% endfor %}{% endwith %}
{% block content %}{% endblock %}
</main><footer>Travel Across India · Demo booking system</footer>
</body></html>
"""

TEMPLATES = {
"base.html": BASE,
"index.html": r"""{% extends "base.html" %}{% block content %}
<section class="hero"><div><div class="eyebrow">● Your journey, our priority</div><h1>Every journey<br>starts <span>here.</span></h1>
<p>Discover Tamil Nadu, one comfortable ride at a time. Find buses, choose your seat, and keep your ticket right at your fingertips.</p>
<div class="muted" style="font-size:13px">✓ Easy booking　 ✓ Seat selection　 ✓ District-wise routes</div></div>
<img class="hero-img" src="{{ bus_image }}" alt="Passenger bus" onerror="this.onerror=null;this.src='{{ bus_image }}'"></section>
<section class="card searchbox"><div class="eyebrow">Plan your trip</div><h2 style="margin:8px 0 20px">Where are you going?</h2>
<form action="{{ url_for('search') }}" method="get" class="searchgrid">
<div><label>FROM</label><select name="source" required>{% for d in districts %}<option value="{{ d }}" {% if d=='Chennai' %}selected{% endif %}>{{ d }}</option>{% endfor %}</select></div>
<div><label>TO</label><select name="destination" required><option value="">Choose destination</option>{% for d in districts %}<option value="{{ d }}">{{ d }}</option>{% endfor %}</select></div>
<div><label>JOURNEY DATE</label><input type="date" name="date" min="{{ '' }}" value="{{ today or '' }}" required></div>
<button class="btn" type="submit">Search buses →</button></form><div class="popular">Popular routes: Chennai → Coimbatore · Madurai · Salem · Tiruchirappalli · Tirunelveli</div></section>
{% endblock %}""",
"search.html": r"""{% extends "base.html" %}{% block title %}Available buses{% endblock %}{% block content %}
<div class="eyebrow">Available services</div><h1 style="margin:10px 0 5px;font-size:34px">{{ source }} → {{ destination or 'Choose destination' }}</h1>
<p class="muted">Journey date: {{ travel_date }}</p>
<form action="{{ url_for('search') }}" method="get" class="card searchgrid" style="margin:20px 0">
<div><label>FROM</label><select name="source">{% for d in districts %}<option {% if d==source %}selected{% endif %}>{{ d }}</option>{% endfor %}</select></div>
<div><label>TO</label><select name="destination" required>{% for d in districts %}<option {% if d==destination %}selected{% endif %}>{{ d }}</option>{% endfor %}</select></div>
<div><label>DATE</label><input type="date" name="date" value="{{ travel_date }}" required></div><button class="btn">Search buses →</button></form>
{% if buses %}<div class="grid">{% for bus in buses %}<article class="card bus-card"><img src="{{ bus.image_url }}" alt="{{ bus.bus_type }} bus" onerror="this.onerror=null;this.src='{{ bus_image }}'"><div class="bus-body"><div class="bus-top"><div><h3 style="margin-bottom:5px">{{ bus.operator }}</h3><span class="pill">{{ bus.bus_type }}</span></div><div class="price">₹{{ bus.price }}</div></div><p style="margin:16px 0 5px"><b>{{ bus.departure }}</b>　→　<b>{{ bus.arrival }}</b></p><p class="muted" style="font-size:12px">{{ bus.source }} to {{ bus.destination }} · {{ bus.seats }} seats</p>
<a class="btn" href="{{ url_for('bus_details',bus_id=bus.id,date=travel_date) }}">View bus & choose seat →</a></div></article>{% endfor %}</div>
{% else %}<div class="card"><h3>No buses found for this route.</h3><p class="muted">The demo inventory currently includes daily services from Chennai to every other Tamil Nadu district. Choose Chennai as the departure district to explore them.</p></div>{% endif %}
{% endblock %}""",
"bus.html": r"""{% extends "base.html" %}{% block title %}{{ bus.operator }}{% endblock %}{% block content %}
<a class="muted" href="{{ url_for('search',source=bus.source,destination=bus.destination,date=travel_date) }}">← Back to buses</a>
<div class="grid" style="grid-template-columns:minmax(0,1.2fr) minmax(280px,.8fr);margin-top:18px">
<div class="card" style="padding:0;overflow:hidden"><img src="{{ bus.image_url }}" alt="Bus exterior" style="width:100%;height:260px;object-fit:cover" onerror="this.onerror=null;this.src='{{ bus_image }}'"><div style="padding:22px"><span class="pill">{{ bus.bus_type }}</span><h1 style="margin:12px 0">{{ bus.operator }}</h1><h2>{{ bus.source }} → {{ bus.destination }}</h2><p class="muted">{{ bus.departure }} departure · {{ bus.arrival }} arrival</p><div class="price">₹{{ bus.price }} <small class="muted" style="font-size:12px">/ seat</small></div></div></div>
<div class="card"><div class="eyebrow">Choose your seat</div><h2 style="margin:8px 0">Seat layout</h2><p class="muted" style="font-size:12px">Green = available · Grey = booked</p>
<form action="{{ url_for('book',bus_id=bus.id) }}" method="post"><input type="hidden" name="travel_date" value="{{ travel_date }}">
<div class="seat-grid">{% for n in range(1,bus.seats+1) %}{% if n in occupied %}<span class="seat booked">{{ n }}</span>{% else %}<label class="seat"><input type="radio" name="seat_number" value="{{ n }}" required>{{ n }}</label>{% endif %}{% endfor %}</div>
<button class="btn" type="submit" style="width:100%">Book selected seat · ₹{{ bus.price }}</button></form><p class="muted" style="font-size:11px;margin:12px 0 0">Demo booking only; no payment is collected.</p></div></div>
<section class="card" style="margin-top:22px"><div class="eyebrow">Passenger feedback</div><h2 style="margin:8px 0 15px">Customer reviews</h2>
{% if reviews %}{% for review in reviews %}<div class="review"><div class="stars">{{ "★" * review.rating }}{{ "☆" * (5-review.rating) }}</div><b>{{ review.user.name }}</b><p style="margin:6px 0 0">{{ review.comment }}</p></div>{% endfor %}{% else %}<p class="muted">No reviews yet. Be the first to share your experience.</p>{% endif %}
<form action="{{ url_for('add_review',bus_id=bus.id) }}" method="post" style="max-width:600px;margin-top:20px"><h3>Write a review</h3><div class="grid"><div><label>Rating</label><select name="rating"><option value="5">5 stars</option><option value="4">4 stars</option><option value="3">3 stars</option><option value="2">2 stars</option><option value="1">1 star</option></select></div><div><label>Your review</label><input name="comment" maxlength="500" placeholder="Share your experience..." required></div></div><button class="btn" style="margin-top:12px">Submit review</button></form></section>
{% endblock %}""",
"login.html": r"""{% extends "base.html" %}{% block title %}Login{% endblock %}{% block content %}
<div class="card form-card"><div class="eyebrow">Welcome back</div><h1 style="font-size:32px;margin:8px 0 20px">Login to your account</h1>
<form method="post"><div class="field"><label>Email address</label><input type="email" name="email" placeholder="name@example.com" required></div><div class="field"><label>Password</label><input type="password" name="password" placeholder="Enter your password" required></div><button class="btn" style="width:100%">Login</button></form><p class="muted" style="margin:18px 0 0;font-size:13px">New here? <a style="color:var(--green);font-weight:700" href="{{ url_for('register') }}">Create an account</a></p></div>
{% endblock %}""",
"register.html": r"""{% extends "base.html" %}{% block title %}Create account{% endblock %}{% block content %}
<div class="card form-card"><div class="eyebrow">Join us</div><h1 style="font-size:32px;margin:8px 0 20px">Create your account</h1>
<form method="post"><div class="field"><label>Full name</label><input name="name" required maxlength="100" placeholder="Your name"></div><div class="field"><label>Email address</label><input type="email" name="email" required placeholder="name@example.com"></div><div class="field"><label>Password (at least 8 characters)</label><input type="password" name="password" minlength="8" required placeholder="Create a password"></div><button class="btn" style="width:100%">Create account</button></form><p class="muted" style="margin:18px 0 0;font-size:13px">Already registered? <a style="color:var(--green);font-weight:700" href="{{ url_for('login') }}">Login</a></p></div>
{% endblock %}""",
"my_bookings.html": r"""{% extends "base.html" %}{% block title %}My tickets{% endblock %}{% block content %}
<div class="eyebrow">Your journeys</div><h1 style="font-size:34px">My tickets</h1>
{% if bookings %}<div class="grid">{% for b in bookings %}<div class="card"><span class="pill">Booking #{{ b.id }}</span><h2 style="margin:12px 0">{{ b.bus.source }} → {{ b.bus.destination }}</h2><p><b>{{ b.bus.operator }}</b></p><p class="muted">{{ b.travel_date }} · {{ b.bus.departure }} · Seat {{ b.seat_number }}</p><div class="price">₹{{ b.bus.price }}</div></div>{% endfor %}</div>{% else %}<div class="card"><h3>No tickets booked yet</h3><p class="muted">Search for a bus and book your first journey.</p><a class="btn" href="{{ url_for('index') }}">Search buses →</a></div>{% endif %}
{% endblock %}""",
"admin.html": r"""{% extends "base.html" %}{% block title %}Admin{% endblock %}{% block content %}
<div class="eyebrow">Administration</div><h1>Booking overview</h1><div class="card" style="overflow:auto"><h2>Bookings</h2><table class="table"><tr><th>Ticket</th><th>Passenger</th><th>Route</th><th>Date</th><th>Seat</th></tr>{% for b in bookings %}<tr><td>#{{ b.id }}</td><td>{{ b.user.name }}</td><td>{{ b.bus.source }} → {{ b.bus.destination }}</td><td>{{ b.travel_date }}</td><td>{{ b.seat_number }}</td></tr>{% endfor %}</table></div>
{% endblock %}"""
}
app.jinja_loader = DictLoader(TEMPLATES)

if __name__ == "__main__":
    app.run(debug=True)
