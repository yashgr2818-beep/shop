import os
from flask import Flask, render_template, redirect, url_for
from database import init_db

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev_secret_key_change_in_production'),
        DATABASE=os.path.join(app.root_path, 'shop_catalog.db'),
        UPLOAD_FOLDER=os.path.join(app.root_path, 'static', 'uploads'),
        IMAGE_FOLDER=os.path.join(app.root_path, 'static', 'images'),
        QR_FOLDER=os.path.join(app.root_path, 'static', 'qrs'),
    )

    if test_config is None:
        app.config.from_pyfile('config.py', silent=True)
    else:
        app.config.from_mapping(test_config)

    # Ensure directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['IMAGE_FOLDER'], exist_ok=True)
    os.makedirs(app.config['QR_FOLDER'], exist_ok=True)

    import database
    app.teardown_appcontext(database.close_connection)

    # Initialize DB (if not exists)
    init_db(app)

    # Register blueprints
    from routes import manager, shop, admin
    app.register_blueprint(manager.bp)
    app.register_blueprint(shop.bp)
    app.register_blueprint(admin.bp)

    @app.route('/')
    def index():
        return redirect(url_for('manager.login'))

    return app

# WSGI Application instance for Gunicorn / Render
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
