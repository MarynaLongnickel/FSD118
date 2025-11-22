import os
from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_cors import CORS
from models import db, User, WatchItem
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import yfinance as yf

def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    load_dotenv(env_path)

    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret')
    raw_uri = os.getenv('DATABASE_URL', 'sqlite:///watchlist.db')
    if raw_uri.startswith("sqlite:///"):
        rel_path = raw_uri.replace("sqlite:///", "")
        abs_path = os.path.join(os.path.dirname(__file__), rel_path)
        db_uri = f"sqlite:///{abs_path}"
    else:
        db_uri = raw_uri
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    CORS(app, supports_credentials=True)

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        db.create_all()

    # ------------------------------------------------------------------------------------------
    # Fetch top movers
    def fetch_top_movers():
        symbols = ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'TSLA']
        movers = []
        watchlist_symbols = set()
        if current_user.is_authenticated:
            watchlist_symbols = {w.symbol for w in WatchItem.query.filter_by(user_id=current_user.id).all()}

        for symbol in symbols:
            try:
                stock = yf.Ticker(symbol)
                info = stock.info
                price = info.get('regularMarketPrice', 0)
                prev_close = info.get('regularMarketPreviousClose', 0)
                change = price - prev_close
                pct_change = f"{(change / prev_close * 100):.2f}%" if prev_close else "0%"
                name = info.get('shortName', '') or symbol

                movers.append({
                    'symbol': symbol,
                    'name': name,
                    'price': f"{price:.2f}",
                    'change': f"{change:.2f}",
                    'percent_change': pct_change,
                    'already_in_watchlist': symbol in watchlist_symbols
                })
            except Exception:
                movers.append({
                    'symbol': symbol,
                    'name': symbol,
                    'price': '0',
                    'change': '0',
                    'percent_change': '0%',
                    'already_in_watchlist': symbol in watchlist_symbols
                })
        return movers

    @app.route('/')
    def index():
        movers = fetch_top_movers()
        return render_template('index.html', movers=movers)


    @app.route('/dashboard')
    @login_required
    def dashboard():
        items = WatchItem.query.filter_by(user_id=current_user.id).all()
        movers = fetch_top_movers()
        return render_template('dashboard.html', movers=movers, watchlist=items)

    # ------------------------------------------------------------------------------------------
    # Search API
    @app.route('/api/search', methods=['GET'])
    def search():
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify([])

        results = []
        try:
            ticker = yf.Ticker(query.upper())
            info = ticker.info

            symbol = info.get('symbol', query.upper())
            name = info.get('shortName', '')

            already = False
            if current_user.is_authenticated:
                already = WatchItem.query.filter_by(user_id=current_user.id, symbol=symbol).first() is not None

            results.append({
                'symbol': symbol,
                'name': name,
                'already_in_watchlist': already
            })

        except Exception:
            results.append({
                'symbol': query.upper(),
                'name': '',
                'already_in_watchlist': False
            })

        return jsonify(results)

    # ------------------------------------------------------------------------------------------
    # Auth
    @app.route('/api/register', methods=['POST'])
    def register():
        data = request.json
        username = data.get('username')
        password = data.get('password')
        if not username or not password:
            return jsonify({'error': 'username and password required'}), 400
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'username taken'}), 400
        user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        return jsonify({'success': True})

    @app.route('/api/login', methods=['POST'])
    def login():
        data = request.json
        username = data.get('username')
        password = data.get('password')
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            return jsonify({'error': 'invalid credentials'}), 401
        login_user(user)
        return jsonify({'success': True, 'username': user.username})

    @app.route('/api/logout', methods=['POST'])
    @login_required
    def logout():
        logout_user()
        return jsonify({'success': True})

    # ------------------------------------------------------------------------------------------
    # Watchlist API
    @app.route('/api/watchlist', methods=['GET'])
    @login_required
    def get_watchlist():
        items = WatchItem.query.filter_by(user_id=current_user.id).all()
        watchlist_data = []

        for it in items:
            # fetch current price and daily change using yfinance
            try:
                ticker = yf.Ticker(it.symbol)
                info = ticker.info
                price = info.get('regularMarketPrice', 0)
                prev_close = info.get('regularMarketPreviousClose', 0)
                change = price - prev_close
            except Exception:
                price = 0
                change = 0

            watchlist_data.append({
                'id': it.id,
                'symbol': it.symbol,
                'name': it.name,
                'price': f"{price:.2f}",
                'change': f"{change:.2f}"
            })

        return jsonify(watchlist_data)

    @app.route('/api/watchlist', methods=['POST'])
    @login_required
    def add_watch():
        data = request.json
        symbol = (data.get('symbol') or '').upper().strip()
        name = data.get('name') or ''
        if not symbol:
            return jsonify({'error': 'symbol required'}), 400
        if WatchItem.query.filter_by(user_id=current_user.id, symbol=symbol).first():
            return jsonify({'error': 'already in watchlist'}), 400
        w = WatchItem(user_id=current_user.id, symbol=symbol, name=name)
        db.session.add(w)
        db.session.commit()
        return jsonify({'success': True, 'symbol': symbol})

    @app.route('/api/watchlist/<int:item_id>', methods=['DELETE'])
    @login_required
    def delete_watch(item_id):
        item = WatchItem.query.filter_by(id=item_id, user_id=current_user.id).first()
        if not item:
            return jsonify({'error': 'not found'}), 404
        db.session.delete(item)
        db.session.commit()
        return jsonify({'success': True})

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
