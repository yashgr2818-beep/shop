from flask import Blueprint, render_template, abort, redirect, url_for
from database import get_db

bp = Blueprint('shop', __name__, url_prefix='/shop')

# ── Public catalog ────────────────────────────────────────────────────────
@bp.route('/<shop_slug>')
def catalog(shop_slug):
    db = get_db()
    manager = db.execute(
        'SELECT * FROM tbl_managers WHERE shop_slug=? AND is_suspended=0',
        (shop_slug,)
    ).fetchone()
    if manager is None:
        abort(404)

    products = db.execute(
        "SELECT * FROM tbl_products WHERE manager_id=? AND status='Active'",
        (manager['manager_id'],)
    ).fetchall()

    from services.qr_service import get_local_ip
    local_ip = get_local_ip()

    return render_template('shop/catalog.html', manager=manager, products=products, local_ip=local_ip)

# ── QR Scan alias (redirects directly to public catalog) ─────────────────
@bp.route('/scan/<shop_slug>')
def scan(shop_slug):
    return redirect(url_for('shop.catalog', shop_slug=shop_slug))
