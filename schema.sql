CREATE TABLE IF NOT EXISTS tbl_managers (
    manager_id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_name TEXT NOT NULL,
    shop_slug TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    phone_number TEXT NOT NULL,
    is_suspended INTEGER DEFAULT 0,
    secure_url_mode INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tbl_products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    manager_id INTEGER,
    sku TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    price_inr REAL NOT NULL,
    stock_qty INTEGER DEFAULT 0,
    status TEXT DEFAULT 'Active' CHECK(status IN ('Active', 'Inactive', 'Suspended')),
    image_path TEXT DEFAULT 'placeholder.jpg',
    FOREIGN KEY(manager_id) REFERENCES tbl_managers(manager_id) ON DELETE CASCADE,
    UNIQUE(manager_id, sku)
);

CREATE TABLE IF NOT EXISTS tbl_visitor_sessions (
    visit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    manager_id INTEGER NOT NULL,
    session_token TEXT UNIQUE NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    FOREIGN KEY (manager_id) REFERENCES tbl_managers(manager_id) ON DELETE CASCADE
);
