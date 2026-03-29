from flask import Flask, render_template, jsonify, request
import db
import telebot
import os

app = Flask(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_TOKEN_HERE')
ADMIN_ID = int(os.getenv('ADMIN_ID', '123456789'))
ADMIN_SECRET = os.getenv('ADMIN_SECRET', 'wisdomtea_admin_2024')

bot = telebot.TeleBot(BOT_TOKEN)

CATEGORIES = {
    'cat_oolong': '🌊 Улуны',
    'cat_green':  '🌿 Зелёный чай',
    'cat_shu':    '🏺 Шу пуэры',
    'cat_shen':   '🌱 Шэн пуэры',
    'cat_white':  '🤍 Белый чай',
    'cat_red':    '🍂 Красный чай',
}

def is_admin(req):
    return req.headers.get('X-Admin-Secret') == ADMIN_SECRET

# ── Страницы ──────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

# ── API: каталог ──────────────────────────────────────────────

@app.route('/api/categories')
def api_categories():
    return jsonify(CATEGORIES)

@app.route('/api/products')
def api_products():
    category = request.args.get('category')
    form = request.args.get('form')
    if category and form:
        products = db.get_products(category, form)
    else:
        products = db.get_all_products()
    return jsonify([dict(p) for p in products])

@app.route('/api/product/<int:pid>')
def api_product(pid):
    p = db.get_product(pid)
    if not p:
        return jsonify({'error': 'not found'}), 404
    reviews = db.reviews_get(pid)
    avg_rating = round(sum(r['rating'] for r in reviews) / len(reviews), 1) if reviews else None
    result = dict(p)
    result['avg_rating'] = avg_rating
    result['review_count'] = len(reviews)
    return jsonify(result)

# ── API: заказ ────────────────────────────────────────────────

@app.route('/api/order', methods=['POST'])
def api_order():
    data = request.json
    tg_id   = data.get('tg_id')
    items   = data.get('items', [])
    fio     = data.get('fio', '')
    phone   = data.get('phone', '')
    address = data.get('address', '')
    promo   = data.get('promo', '')

    if not items:
        return jsonify({'error': 'missing data'}), 400

    discount = 0
    promo_code = None
    if promo:
        p = db.promo_check(promo)
        if p:
            discount = p['discount']
            promo_code = p['code']
            db.promo_use(promo_code)

    total = sum(i['price'] * i['qty'] for i in items)
    final_total = max(0, total - discount)
    lines = [f"{i['name']} ({i['weight']}г) × {i['qty']} шт. — {i['price'] * i['qty']}₽" for i in items]
    items_text = '\n'.join(lines)

    oid = db.save_order(tg_id or 0, items_text, final_total, fio, phone, address, promo_code, discount)
    if tg_id:
        db.save_user(tg_id, data.get('username', ''), data.get('full_name', ''), phone)

    discount_str = f'\n🎁 Скидка: {discount}₽ (промокод: {promo_code})' if promo_code else ''
    admin_text = (
        f'🔔 <b>Новый заказ №{oid}</b>\n\n'
        f'👤 {fio}\n📱 {phone}\n🏠 СДЭК: {address}\n\n'
        f'Состав:\n{items_text}\n{discount_str}\n💰 Итого: {final_total}₽'
    )
    try:
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(
            '📋 Управление заказом', callback_data=f'adm_order_{oid}'))
        bot.send_message(ADMIN_ID, admin_text, reply_markup=markup, parse_mode='HTML')
    except Exception:
        pass

    return jsonify({'order_id': oid, 'total': final_total, 'discount': discount})

@app.route('/api/promo/<code>')
def api_promo(code):
    p = db.promo_check(code)
    if not p:
        return jsonify({'valid': False})
    return jsonify({'valid': True, 'discount': p['discount'], 'code': p['code']})

@app.route('/api/orders/<int:tg_id>')
def api_orders(tg_id):
    orders = db.get_orders(tg_id)
    result = []
    for o in orders:
        d = dict(o)
        d['created_at'] = str(d['created_at'])[:10]
        result.append(d)
    return jsonify(result)

# ── ADMIN API ─────────────────────────────────────────────────

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    if data.get('secret') == ADMIN_SECRET:
        return jsonify({'ok': True})
    return jsonify({'ok': False}), 403

@app.route('/api/admin/products', methods=['GET'])
def admin_get_products():
    if not is_admin(request):
        return jsonify({'error': 'forbidden'}), 403
    products = db.get_all_products()
    return jsonify([dict(p) for p in products])

@app.route('/api/admin/product', methods=['POST'])
def admin_add_product():
    if not is_admin(request):
        return jsonify({'error': 'forbidden'}), 403
    data = request.json
    db.add_product(
        data['category'], data['form'], data['name'],
        data.get('year') or None, int(data['weight']),
        int(data['price']), data.get('description', ''),
        int(data.get('stock', 0))
    )
    return jsonify({'ok': True})

@app.route('/api/admin/product/<int:pid>', methods=['PUT'])
def admin_update_product(pid):
    if not is_admin(request):
        return jsonify({'error': 'forbidden'}), 403
    data = request.json
    db.update_product(pid, data['name'], int(data['price']),
                      int(data['stock']), data.get('description', ''),
                      data.get('year') or None)
    return jsonify({'ok': True})

@app.route('/api/admin/product/<int:pid>', methods=['DELETE'])
def admin_delete_product(pid):
    if not is_admin(request):
        return jsonify({'error': 'forbidden'}), 403
    db.delete_product(pid)
    return jsonify({'ok': True})

@app.route('/api/admin/orders', methods=['GET'])
def admin_get_orders():
    if not is_admin(request):
        return jsonify({'error': 'forbidden'}), 403
    orders = db.get_all_orders()
    result = []
    for o in orders:
        d = dict(o)
        d['created_at'] = str(d['created_at'])[:16]
        result.append(d)
    return jsonify(result)

@app.route('/api/admin/order/<int:oid>/status', methods=['PUT'])
def admin_update_status(oid):
    if not is_admin(request):
        return jsonify({'error': 'forbidden'}), 403
    data = request.json
    db.set_order_status(oid, data['status'])
    o = db.get_order(oid)
    status_emoji = {'Новый':'🆕','Принят в работу':'⚙️','Собран':'📦','Отправлен':'🚚','Завершён':'✅'}
    emoji = status_emoji.get(data['status'], '📍')
    try:
        bot.send_message(o['tg_id'],
            f'{emoji} Статус заказа №{oid} обновлён:\n\n<b>{data["status"]}</b>',
            parse_mode='HTML')
    except Exception:
        pass
    return jsonify({'ok': True})

@app.route('/api/admin/stats', methods=['GET'])
def admin_stats():
    if not is_admin(request):
        return jsonify({'error': 'forbidden'}), 403
    total_orders, total_revenue, total_users, _ = db.get_stats()
    return jsonify({'orders': total_orders, 'revenue': total_revenue, 'users': total_users})

@app.route('/api/admin/promos', methods=['GET'])
def admin_get_promos():
    if not is_admin(request):
        return jsonify({'error': 'forbidden'}), 403
    return jsonify([dict(p) for p in db.promo_list()])

@app.route('/api/admin/promo', methods=['POST'])
def admin_add_promo():
    if not is_admin(request):
        return jsonify({'error': 'forbidden'}), 403
    data = request.json
    db.promo_add(data['code'], int(data['discount']), int(data.get('uses', -1)))
    return jsonify({'ok': True})

@app.route('/api/admin/promo/<int:pid>/toggle', methods=['PUT'])
def admin_toggle_promo(pid):
    if not is_admin(request):
        return jsonify({'error': 'forbidden'}), 403
    db.promo_toggle(pid)
    return jsonify({'ok': True})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)