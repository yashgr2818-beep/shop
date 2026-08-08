from flask import Blueprint, render_template, request, redirect, url_for, session, current_app, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db
import sqlite3
import re
import os

bp = Blueprint('manager', __name__, url_prefix='/manager')

@bp.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        shop_name = request.form['shop_name']
        email = request.form['email']
        password = request.form['password']
        phone_number = request.form['phone_number']
        
        # Generate slug from shop name
        shop_slug = re.sub(r'[^a-z0-9]+', '-', shop_name.lower()).strip('-')

        db = get_db()
        error = None

        if not shop_name or not email or not password or not phone_number:
            error = 'All fields are required.'

        if error is None:
            try:
                db.execute(
                    "INSERT INTO tbl_managers (shop_name, shop_slug, email, password_hash, phone_number) VALUES (?, ?, ?, ?, ?)",
                    (shop_name, shop_slug, email, generate_password_hash(password), phone_number),
                )
                db.commit()
                # Generate QR Code for this shop
                from services.qr_service import generate_shop_qr
                generate_shop_qr(shop_slug, current_app.config['QR_FOLDER'])

            except sqlite3.IntegrityError as e:
                if 'shop_slug' in str(e):
                    # Simple handling for duplicate slugs - append a random number in production
                    error = f"Shop name '{shop_name}' is already taken."
                else:
                    error = f"Email '{email}' is already registered."
            else:
                return redirect(url_for('manager.login'))

        flash(error)

    return render_template('manager/register.html')

@bp.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        db = get_db()
        error = None
        manager = db.execute(
            'SELECT * FROM tbl_managers WHERE email = ?', (email,)
        ).fetchone()

        if manager is None:
            error = 'Incorrect email.'
        elif not check_password_hash(manager['password_hash'], password):
            error = 'Incorrect password.'

        if error is None:
            session.clear()
            session['manager_id'] = manager['manager_id']
            return redirect(url_for('manager.dashboard'))

        flash(error)

    return render_template('manager/login.html')

@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('manager.login'))

@bp.route('/dashboard')
def dashboard():
    manager_id = session.get('manager_id')
    if manager_id is None:
        return redirect(url_for('manager.login'))
        
    db = get_db()
    manager = db.execute('SELECT * FROM tbl_managers WHERE manager_id = ?', (manager_id,)).fetchone()
    products = db.execute('SELECT * FROM tbl_products WHERE manager_id = ? ORDER BY product_id DESC', (manager_id,)).fetchall()
    
    # Analytics queries
    from datetime import datetime
    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    total_scans = db.execute('SELECT COUNT(*) as count FROM tbl_visitor_sessions WHERE manager_id = ?', (manager_id,)).fetchone()['count']
    active_visitors = db.execute('SELECT COUNT(*) as count FROM tbl_visitor_sessions WHERE manager_id = ? AND expires_at > ?', (manager_id, now_str)).fetchone()['count']
    
    recent_scans = db.execute(
        '''SELECT *,
                  CASE WHEN expires_at > ? THEN 'Active' ELSE 'Expired' END as status
           FROM tbl_visitor_sessions
           WHERE manager_id = ?
           ORDER BY visit_id DESC LIMIT 10''',
        (now_str, manager_id)
    ).fetchall()

    from services.qr_service import get_local_ip
    local_ip = get_local_ip()

    return render_template('manager/dashboard.html',
                           manager=manager,
                           products=products,
                           total_scans=total_scans,
                           active_visitors=active_visitors,
                           recent_scans=recent_scans,
                           local_ip=local_ip)



@bp.route('/product/<int:product_id>/quick_edit', methods=['POST'])
def quick_edit_product(product_id):
    manager_id = session.get('manager_id')
    if manager_id is None:
        return redirect(url_for('manager.login'))

    price_inr = request.form.get('price_inr', '').strip()
    stock_qty  = request.form.get('stock_qty', '').strip()

    db = get_db()
    # make sure this product belongs to this manager
    product = db.execute(
        'SELECT product_id FROM tbl_products WHERE product_id = ? AND manager_id = ?',
        (product_id, manager_id)
    ).fetchone()

    if not product:
        flash('Product not found.')
        return redirect(url_for('manager.dashboard'))

    fields, values = [], []
    if price_inr != '':
        fields.append('price_inr = ?')
        values.append(float(price_inr) if price_inr else 0.0)
    if stock_qty != '':
        fields.append('stock_qty = ?')
        values.append(int(stock_qty))

    if fields:
        values.append(product_id)
        db.execute(f'UPDATE tbl_products SET {", ".join(fields)} WHERE product_id = ?', values)
        db.commit()
        flash('Product updated successfully!', 'success')

    return redirect(url_for('manager.dashboard'))

@bp.route('/toggle_whatsapp', methods=['POST'])
def toggle_whatsapp():
    manager_id = session.get('manager_id')
    if manager_id is None:
        return redirect(url_for('manager.login'))
        
    db = get_db()
    manager = db.execute('SELECT whatsapp_orders_enabled FROM tbl_managers WHERE manager_id = ?', (manager_id,)).fetchone()
    if manager:
        new_val = 0 if manager['whatsapp_orders_enabled'] == 1 else 1
        db.execute('UPDATE tbl_managers SET whatsapp_orders_enabled = ? WHERE manager_id = ?', (new_val, manager_id))
        db.commit()
        flash('WhatsApp Order settings updated.')
    return redirect(url_for('manager.dashboard'))

@bp.route('/toggle_price', methods=['POST'])
def toggle_price():
    manager_id = session.get('manager_id')
    if manager_id is None:
        return redirect(url_for('manager.login'))
        
    db = get_db()
    manager = db.execute('SELECT price_mandatory FROM tbl_managers WHERE manager_id = ?', (manager_id,)).fetchone()
    if manager:
        new_val = 0 if manager['price_mandatory'] == 1 else 1
        db.execute('UPDATE tbl_managers SET price_mandatory = ? WHERE manager_id = ?', (new_val, manager_id))
        db.commit()
        flash('Price mandatory setting updated.')
    return redirect(url_for('manager.dashboard'))

@bp.route('/toggle_show_price', methods=['POST'])
def toggle_show_price():
    manager_id = session.get('manager_id')
    if manager_id is None:
        return redirect(url_for('manager.login'))
        
    db = get_db()
    manager = db.execute('SELECT show_price FROM tbl_managers WHERE manager_id = ?', (manager_id,)).fetchone()
    if manager:
        new_val = 0 if manager['show_price'] == 1 else 1
        db.execute('UPDATE tbl_managers SET show_price = ? WHERE manager_id = ?', (new_val, manager_id))
        db.commit()
        flash('Price visibility updated.')
    return redirect(url_for('manager.dashboard'))

from services.upload_service import process_csv_upload, process_image_upload
from flask import jsonify

@bp.route('/upload', methods=('GET', 'POST'))
def upload():
    manager_id = session.get('manager_id')
    if manager_id is None:
        return redirect(url_for('manager.login'))
        
    db = get_db()
    manager = db.execute('SELECT * FROM tbl_managers WHERE manager_id = ?', (manager_id,)).fetchone()
    
    if manager['bulk_upload_enabled'] == 0:
        flash('Bulk upload is disabled for your account. Please contact the administrator.')
        return redirect(url_for('manager.dashboard'))
        
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('No file part')
            return redirect(request.url)
            
        file = request.files['csv_file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
            
        if file and file.filename.endswith('.csv'):
            try:
                count = process_csv_upload(file, manager_id)
                flash(f'Successfully imported/updated {count} products.')
            except Exception as e:
                flash(f'Error processing CSV: {str(e)}')
            return redirect(url_for('manager.dashboard'))
        else:
            flash('Please upload a valid CSV file.')
            
    return render_template('manager/upload.html', manager=manager)

@bp.route('/upload/image', methods=['POST'])
def upload_image():
    manager_id = session.get('manager_id')
    if manager_id is None:
        return jsonify({'error': 'Unauthorized'}), 401
        
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    success, message = process_image_upload(file, manager_id, current_app.config['IMAGE_FOLDER'])
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'error': message}), 400

from werkzeug.utils import secure_filename
from PIL import Image

def generate_next_sku(db, manager_id):
    row = db.execute("SELECT COUNT(*) as count FROM tbl_products WHERE manager_id = ?", (manager_id,)).fetchone()
    count = row['count'] if row else 0
    seq = count  # Every shop/manager starts sequence from 0 (00000)
    while True:
        candidate = f"SKU-{manager_id}-{seq:05d}"
        exists = db.execute("SELECT product_id FROM tbl_products WHERE manager_id = ? AND sku = ?", (manager_id, candidate)).fetchone()
        if not exists:
            return candidate
        seq += 1

@bp.route('/product/add', methods=('GET', 'POST'))
def add_product():
    manager_id = session.get('manager_id')
    if manager_id is None:
        return redirect(url_for('manager.login'))

    db = get_db()
    manager = db.execute('SELECT * FROM tbl_managers WHERE manager_id = ?', (manager_id,)).fetchone()
    next_sku = generate_next_sku(db, manager_id)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '')
        price_val = request.form.get('price_inr', '').strip()
        price_inr = float(price_val) if price_val else 0.0
        stock_qty = request.form.get('stock_qty', 0)
        status = request.form.get('status', 'Active')
        sku = next_sku

        if not name:
            flash("Product Name is required.", "error")
            return render_template('manager/add_product.html', manager=manager, next_sku=next_sku)
            
        if manager['price_mandatory'] == 1 and not price_val:
            flash("Price is required.", "error")
            return render_template('manager/add_product.html', manager=manager, next_sku=next_sku)

        image_path = 'placeholder.jpg'
        
        # Handle Image
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                try:
                    img = Image.open(file.stream)
                    if img.mode in ('RGBA', 'P'):
                        img = img.convert('RGB')
                    img.thumbnail((800, 800))
                    new_filename = f"{manager_id}_{sku}.jpg"
                    save_path = os.path.join(current_app.config['IMAGE_FOLDER'], new_filename)
                    img.save(save_path, format="JPEG", quality=85)
                    image_path = new_filename
                except Exception as e:
                    flash(f"Warning: Image failed to process: {e}", "error")

        try:
            db.execute(
                "INSERT INTO tbl_products (manager_id, sku, name, description, price_inr, stock_qty, status, image_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (manager_id, sku, name, description, price_inr, stock_qty, status, image_path)
            )
            db.commit()
            flash(f'Product added successfully with permanent SKU: {sku}!', 'success')
            return redirect(url_for('manager.dashboard'))
        except sqlite3.IntegrityError:
            flash(f"Error creating product with SKU '{sku}'. Please try again.", 'error')

    return render_template('manager/add_product.html', manager=manager, next_sku=next_sku)

@bp.route('/product/<int:product_id>/edit', methods=('GET', 'POST'))
def edit_product(product_id):
    manager_id = session.get('manager_id')
    if manager_id is None:
        return redirect(url_for('manager.login'))

    db = get_db()
    manager = db.execute('SELECT * FROM tbl_managers WHERE manager_id = ?', (manager_id,)).fetchone()
    product = db.execute('SELECT * FROM tbl_products WHERE product_id = ? AND manager_id = ?', (product_id, manager_id)).fetchone()

    if not product:
        flash('Product not found.', 'error')
        return redirect(url_for('manager.dashboard'))

    if request.method == 'POST':
        sku = product['sku']  # SKU is permanent and cannot be changed
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '')
        price_val = request.form.get('price_inr', '').strip()
        price_inr = float(price_val) if price_val else 0.0
        stock_qty = int(request.form.get('stock_qty', 0))
        requested_status = request.form.get('status', 'Active')

        if not name:
            flash("Product Name is required.", "error")
            return render_template('manager/edit_product.html', manager=manager, product=product)

        if manager['price_mandatory'] == 1 and not price_val:
            flash("Price is required.", "error")
            return render_template('manager/edit_product.html', manager=manager, product=product)

        # Preserve Suspended status if admin suspended it
        status = 'Suspended' if product['status'] == 'Suspended' else requested_status

        image_path = product['image_path']
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                try:
                    img = Image.open(file.stream)
                    if img.mode in ('RGBA', 'P'):
                        img = img.convert('RGB')
                    img.thumbnail((800, 800))
                    new_filename = f"{manager_id}_{sku}.jpg"
                    save_path = os.path.join(current_app.config['IMAGE_FOLDER'], new_filename)
                    img.save(save_path, format="JPEG", quality=85)
                    image_path = new_filename
                except Exception as e:
                    flash(f"Warning: Image failed to process: {e}")

        try:
            db.execute(
                "UPDATE tbl_products SET sku=?, name=?, description=?, price_inr=?, stock_qty=?, status=?, image_path=? "
                "WHERE product_id=? AND manager_id=?",
                (sku, name, description, price_inr, stock_qty, status, image_path, product_id, manager_id)
            )
            db.commit()
            flash('Product updated successfully!', 'success')
            return redirect(url_for('manager.dashboard'))
        except sqlite3.IntegrityError:
            flash(f"A product with SKU '{sku}' already exists.", 'error')

    return render_template('manager/edit_product.html', manager=manager, product=product)

@bp.route('/product/<int:product_id>/toggle_status', methods=['POST'])
def toggle_product_status(product_id):
    manager_id = session.get('manager_id')
    if manager_id is None:
        return redirect(url_for('manager.login'))

    db = get_db()
    product = db.execute('SELECT status FROM tbl_products WHERE product_id = ? AND manager_id = ?', (product_id, manager_id)).fetchone()

    if not product:
        flash('Product not found.', 'error')
        return redirect(url_for('manager.dashboard'))

    if product['status'] == 'Suspended':
        flash('This product is suspended by Super Admin and cannot be activated.', 'error')
    else:
        new_status = 'Inactive' if product['status'] == 'Active' else 'Active'
        db.execute('UPDATE tbl_products SET status = ? WHERE product_id = ?', (new_status, product_id))
        db.commit()
        flash(f'Product status changed to {new_status}.', 'success')

    return redirect(url_for('manager.dashboard'))

