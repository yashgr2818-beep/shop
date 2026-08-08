import csv
import os
from PIL import Image
from database import get_db
from werkzeug.utils import secure_filename
import io

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

def process_csv_upload(file_stream, manager_id):
    # Process the CSV stream
    stream = io.StringIO(file_stream.stream.read().decode("UTF8"), newline=None)
    csv_input = csv.DictReader(stream)
    
    db = get_db()
    count = 0
    
    # Expected columns: sku, name, description, price_inr, stock_qty, status
    for row in csv_input:
        name = row.get('name', '').strip()
        if not name:
            continue

        sku = row.get('sku', '').strip()
        if not sku:
            sku = generate_next_sku(db, manager_id)

        description = row.get('description', '')
        price_val = row.get('price_inr', '').strip()
        price_inr = float(price_val) if price_val else 0.0
        stock_qty = row.get('stock_qty', 0)
        status = row.get('status', 'Active')
        
        try:
            db.execute(
                "INSERT INTO tbl_products (manager_id, sku, name, description, price_inr, stock_qty, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(manager_id, sku) DO UPDATE SET "
                "name=excluded.name, description=excluded.description, "
                "price_inr=excluded.price_inr, stock_qty=excluded.stock_qty, status=excluded.status",
                (manager_id, sku, name, description, price_inr, stock_qty, status)
            )
            count += 1
        except Exception as e:
            print(f"Error inserting row {sku}: {e}")
                
    db.commit()
    return count

def process_image_upload(file, manager_id, image_folder):
    if not file:
        return False, "No file provided"
        
    filename = secure_filename(file.filename)
    if not filename:
        return False, "Invalid filename"
        
    # The file is expected to be named like SKU001.jpg
    # Strip extension to get SKU
    sku, ext = os.path.splitext(filename)
    
    db = get_db()
    # Check if SKU exists for this manager
    product = db.execute(
        "SELECT product_id FROM tbl_products WHERE manager_id = ? AND sku = ?", 
        (manager_id, sku)
    ).fetchone()
    
    if not product:
        return False, f"No matching product found for SKU: {sku}"
        
    # Process image with Pillow
    try:
        img = Image.open(file.stream)
        
        # Convert to RGB if it's RGBA or P
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
            
        # Resize/Compress
        img.thumbnail((800, 800))
        
        # Save compressed image
        new_filename = f"{manager_id}_{sku}.jpg"
        save_path = os.path.join(image_folder, new_filename)
        img.save(save_path, format="JPEG", quality=85)
        
        # Update DB
        db.execute(
            "UPDATE tbl_products SET image_path = ? WHERE product_id = ?",
            (new_filename, product['product_id'])
        )
        db.commit()
        
        return True, "Success"
    except Exception as e:
        return False, f"Image processing failed: {str(e)}"
