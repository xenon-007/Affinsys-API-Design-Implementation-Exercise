from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import base64
import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = '1234567890' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:1234567890@localhost/wallet_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    balance = db.Column(db.Float, default=0.0)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(80), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# Basic Auth Decorator
from functools import wraps

def basic_auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Basic '):
            return jsonify({'message': 'Basic Auth required!'})

        try:
            auth_decoded = base64.b64decode(auth_header.split(' ')[1]).decode('utf-8')
            username, password = auth_decoded.split(':', 1)
            user = User.query.filter_by(username=username).first()
            if not user or not check_password_hash(user.password_hash, password):
                return jsonify({'message': 'Invalid credentials!'})
        except Exception as e:
            return jsonify({'message': 'Invalid auth format!'})

        return f(user, *args, **kwargs)
    return decorated

# Routes

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    hashed_pw = generate_password_hash(data['password'])
    new_user = User(username=data['username'], password_hash=hashed_pw)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'User registered successfully!'}), 201

@app.route('/fund', methods=['POST'])
@basic_auth_required
def fund(current_user):
    data = request.get_json()
    amount = data['amount']
    current_user.balance += amount
    transaction = Transaction(user_id=current_user.id, type='credit', amount=amount)
    db.session.add(transaction)
    db.session.commit()
    return jsonify({'message': f'Account funded with {amount}! New balance: {current_user.balance}'})

@app.route('/bal', methods=['GET'])
@basic_auth_required
def balance(current_user):
    return jsonify({'balance': current_user.balance})

@app.route('/product', methods=['POST'])
@basic_auth_required
def add_product(current_user):
    data = request.get_json()
    new_product = Product(name=data['name'], price=data['price'], description=data.get('description', ''))
    db.session.add(new_product)
    db.session.commit()
    return jsonify({'message': 'Created'}), 201

@app.route('/product', methods=['GET'])
def list_products():
    products = Product.query.all()
    output = []
    for product in products:
        output.append({'id': product.id, 'name': product.name, 'price': product.price,'description': product.description})
    return jsonify(output)

@app.route('/buy', methods=['POST'])
@basic_auth_required
def buy_product(current_user):
    data = request.get_json()
    product = Product.query.get(data['product_id'])
    if not product:
        return jsonify({'message': 'Product not found!'}), 400
    if current_user.balance < product.price:
        return jsonify({'message': 'Insufficient balance!'}), 400
    current_user.balance -= product.price
    transaction = Transaction(user_id=current_user.id, type='debit', amount=product.price)
    db.session.add(transaction)
    db.session.commit()
    return jsonify({'message': f'Purchased {product.name} for {product.price} Balance: {current_user.balance}'})

@app.route('/pay', methods=['POST'])
@basic_auth_required
def pay(current_user):
    data = request.get_json()
    recipient_username = data.get('to')
    amount = data.get('amt')

    if not recipient_username or not amount:
        return jsonify({'message': 'Recipient and amount required!'}), 400

    recipient = User.query.filter_by(username=recipient_username).first()
    if not recipient:
        return jsonify({'message': 'Recipient does not exist!'}), 400

    if current_user.balance < amount:
        return jsonify({'message': 'Insufficient balance!'}), 400

    current_user.balance -= amount
    recipient.balance += amount

    transaction_out = Transaction(user_id=current_user.id, type='debit', amount=amount)
    transaction_in = Transaction(user_id=recipient.id, type='credit', amount=amount)

    db.session.add(transaction_out)
    db.session.add(transaction_in)
    db.session.commit()

    return jsonify({'balance': current_user.balance})

@app.route('/stmt', methods=['GET'])
@basic_auth_required
def transaction_history(current_user):
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    output = []
    for txn in transactions:
        output.append({
            'type': txn.type,
            'amount': txn.amount,
            'timestamp': txn.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        })
    return jsonify(output)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
