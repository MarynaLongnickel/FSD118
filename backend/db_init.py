from app import create_app, db
from models import User, WatchItem  # import models before create_all

app = create_app()

with app.app_context():
    db.create_all()
    print("Database created successfully")
