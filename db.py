import sqlite3

DB = 'wisdomtea.db'

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    c = conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE,
            username TEXT,
            full_name TEXT,
            phone TEXT,
            address TEXT
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            form TEXT,
            name TEXT,
            year INTEGER,
            weight INTEGER,
            price INTEGER,
            description TEXT,
            stock INTEGER DEFAULT 0,
            photo_id TEXT,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER,
            items TEXT,
            total INTEGER,
            status TEXT DEFAULT 'Новый',
            fio TEXT,
            phone TEXT,
            address TEXT,
            promo TEXT,
            discount INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER,
            product_id INTEGER,
            UNIQUE(tg_id, product_id)
        );
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER,
            product_id INTEGER,
            rating INTEGER,
            text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS promocodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            discount INTEGER,
            uses_left INTEGER DEFAULT -1,
            is_active INTEGER DEFAULT 1
        );
    """)
    # Миграции для существующих БД
    migrations = [
        ('users', 'address', 'TEXT'),
        ('products', 'stock', 'INTEGER DEFAULT 0'),
        ('products', 'photo_id', 'TEXT'),
        ('orders', 'fio', 'TEXT'),
        ('orders', 'phone', 'TEXT'),
        ('orders', 'address', 'TEXT'),
        ('orders', 'promo', 'TEXT'),
        ('orders', 'discount', 'INTEGER DEFAULT 0'),
    ]
    for table, col, definition in migrations:
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
            c.commit()
        except Exception:
            pass
    c.close()

# ── Пользователи ──────────────────────────────────────────────

def save_user(tg_id, username, full_name, phone=None, address=None):
    c = conn()
    c.execute("INSERT OR IGNORE INTO users (tg_id, username, full_name) VALUES (?,?,?)",
              (tg_id, username, full_name))
    if phone:
        c.execute("UPDATE users SET phone=? WHERE tg_id=?", (phone, tg_id))
    if address:
        c.execute("UPDATE users SET address=? WHERE tg_id=?", (address, tg_id))
    c.commit()
    c.close()

def get_user(tg_id):
    c = conn()
    row = c.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)).fetchone()
    c.close()
    return row

def get_all_users():
    c = conn()
    rows = c.execute("SELECT * FROM users").fetchall()
    c.close()
    return rows

# ── Товары ────────────────────────────────────────────────────

def add_product(category, form, name, year, weight, price, description, stock=0, photo_id=None):
    c = conn()
    c.execute(
        "INSERT INTO products (category,form,name,year,weight,price,description,stock,photo_id) VALUES (?,?,?,?,?,?,?,?,?)",
        (category, form, name, year, weight, price, description, stock, photo_id)
    )
    c.commit()
    c.close()

def get_products(category, form):
    c = conn()
    rows = c.execute(
        "SELECT * FROM products WHERE category=? AND form=? AND is_active=1",
        (category, form)
    ).fetchall()
    c.close()
    return rows

def get_product(pid):
    c = conn()
    row = c.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    c.close()
    return row

def get_all_products():
    c = conn()
    rows = c.execute("SELECT * FROM products WHERE is_active=1 ORDER BY category, name").fetchall()
    c.close()
    return rows

def update_product(pid, name, price, stock, description, year):
    c = conn()
    c.execute(
        "UPDATE products SET name=?, price=?, stock=?, description=?, year=? WHERE id=?",
        (name, price, stock, description, year, pid)
    )
    c.commit()
    c.close()

def update_photo(pid, photo_id):
    c = conn()
    c.execute("UPDATE products SET photo_id=? WHERE id=?", (photo_id, pid))
    c.commit()
    c.close()

def delete_product(pid):
    c = conn()
    c.execute("UPDATE products SET is_active=0 WHERE id=?", (pid,))
    c.commit()
    c.close()

def get_top_products(limit=3):
    """Топ товаров по количеству заказов (для рекомендаций)."""
    c = conn()
    rows = c.execute(
        "SELECT * FROM products WHERE is_active=1 ORDER BY RANDOM() LIMIT ?", (limit,)
    ).fetchall()
    c.close()
    return rows

# ── Заказы ────────────────────────────────────────────────────

def save_order(tg_id, items_text, total, fio, phone, address, promo=None, discount=0):
    c = conn()
    cur = c.execute(
        "INSERT INTO orders (tg_id,items,total,fio,phone,address,promo,discount) VALUES (?,?,?,?,?,?,?,?)",
        (tg_id, items_text, total, fio, phone, address, promo, discount)
    )
    oid = cur.lastrowid
    c.commit()
    c.close()
    return oid

def get_orders(tg_id):
    c = conn()
    rows = c.execute("SELECT * FROM orders WHERE tg_id=? ORDER BY created_at DESC", (tg_id,)).fetchall()
    c.close()
    return rows

def get_order(oid):
    c = conn()
    row = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    c.close()
    return row

def set_order_status(oid, status):
    c = conn()
    c.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
    c.commit()
    c.close()

def get_all_orders():
    c = conn()
    rows = c.execute("""
        SELECT o.*, u.username, u.full_name
        FROM orders o LEFT JOIN users u ON o.tg_id = u.tg_id
        ORDER BY o.created_at DESC
    """).fetchall()
    c.close()
    return rows

def get_stats():
    c = conn()
    total_orders = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    total_revenue = c.execute("SELECT COALESCE(SUM(total),0) FROM orders").fetchone()[0]
    total_users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    top_products = c.execute("""
        SELECT p.name, COUNT(*) as cnt
        FROM orders o
        JOIN products p ON o.items LIKE '%' || p.name || '%'
        GROUP BY p.name ORDER BY cnt DESC LIMIT 5
    """).fetchall()
    c.close()
    return total_orders, total_revenue, total_users, top_products

# ── Избранное ─────────────────────────────────────────────────

def fav_add(tg_id, pid):
    c = conn()
    try:
        c.execute("INSERT INTO favorites (tg_id, product_id) VALUES (?,?)", (tg_id, pid))
        c.commit()
    except Exception:
        pass
    c.close()

def fav_remove(tg_id, pid):
    c = conn()
    c.execute("DELETE FROM favorites WHERE tg_id=? AND product_id=?", (tg_id, pid))
    c.commit()
    c.close()

def fav_get(tg_id):
    c = conn()
    rows = c.execute("""
        SELECT p.* FROM favorites f
        JOIN products p ON p.id = f.product_id
        WHERE f.tg_id=? AND p.is_active=1
    """, (tg_id,)).fetchall()
    c.close()
    return rows

def fav_check(tg_id, pid):
    c = conn()
    row = c.execute("SELECT id FROM favorites WHERE tg_id=? AND product_id=?", (tg_id, pid)).fetchone()
    c.close()
    return row is not None

# ── Отзывы ────────────────────────────────────────────────────

def review_add(tg_id, pid, rating, text):
    c = conn()
    c.execute("INSERT OR REPLACE INTO reviews (tg_id,product_id,rating,text) VALUES (?,?,?,?)",
              (tg_id, pid, rating, text))
    c.commit()
    c.close()

def reviews_get(pid):
    c = conn()
    rows = c.execute("""
        SELECT r.*, u.full_name, u.username FROM reviews r
        LEFT JOIN users u ON u.tg_id = r.tg_id
        WHERE r.product_id=? ORDER BY r.created_at DESC LIMIT 5
    """, (pid,)).fetchall()
    c.close()
    return rows

# ── Промокоды ─────────────────────────────────────────────────

def promo_check(code):
    c = conn()
    row = c.execute(
        "SELECT * FROM promocodes WHERE code=? AND is_active=1 AND (uses_left=-1 OR uses_left>0)",
        (code.upper(),)
    ).fetchone()
    c.close()
    return row

def promo_use(code):
    c = conn()
    c.execute("UPDATE promocodes SET uses_left=uses_left-1 WHERE code=? AND uses_left>0", (code.upper(),))
    c.commit()
    c.close()

def promo_add(code, discount, uses=-1):
    c = conn()
    try:
        c.execute("INSERT INTO promocodes (code,discount,uses_left) VALUES (?,?,?)",
                  (code.upper(), discount, uses))
        c.commit()
    except Exception:
        pass
    c.close()

def promo_list():
    c = conn()
    rows = c.execute("SELECT * FROM promocodes ORDER BY id DESC").fetchall()
    c.close()
    return rows

def promo_toggle(pid):
    c = conn()
    c.execute("UPDATE promocodes SET is_active=1-is_active WHERE id=?", (pid,))
    c.commit()
    c.close()

init()
print("DB OK")
