from flask import Flask, render_template, jsonify, request
import db
import telebot
import os

app = Flask(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_TOKEN_HERE')
ADMIN_ID = int(os.getenv('ADMIN_ID', '123456789'))

bot = telebot.TeleBot(BOT_TOKEN)

# ── Страницы ──────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

# ── API: каталог ──────────────────────────────────────────────

@app.route('/api/categories')
def api_categories():
    return jsonify({
        'cat_oolong': '🌊 Улуны',
        'cat_green':  '🌿 Зелёный чай',
        'cat_shu':    '🏺 Шу пуэры',
        'cat_shen':   '🌱 Шэн пуэры',
        'cat_white':  '🤍 Белый чай',
        'cat_red':    '🍂 Красный чай',
    })

@app.route('/api/products')
def api_products():
    category = request.args.get('category')
    form = request.args.get('form')
    if category and form:
        products = db.get_products(category, form)
    else:
        products = db.get_all_products()
    result = []
    for p in products:
        result.append({
            'id': p['id'], 'name': p['name'], 'category': p['category'],
            'form': p['form'], 'year': p['year'], 'weight': p['weight'],
            'price': p['price'], 'description': p['description'],
            'stock': p['stock'] or 0, 'photo_id': p['photo_id'],
        })
    return jsonify(result)

@app.route('/api/product/<int:pid>')
def api_product(pid):
    p = db.get_product(pid)
    if not p:
        return jsonify({'error': 'not found'}), 404
    reviews = db.reviews_get(pid)
    avg_rating = round(sum(r['rating'] for r in reviews) / len(reviews), 1) if reviews else None
    return jsonify({
        'id': p['id'], 'name': p['name'], 'category': p['category'],
        'form': p['form'], 'year': p['year'], 'weight': p['weight'],
        'price': p['price'], 'description': p['description'],
        'stock': p['stock'] or 0, 'photo_id': p['photo_id'],
        'avg_rating': avg_rating, 'review_count': len(reviews),
    })

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

    if not tg_id or not items:
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

    oid = db.save_order(tg_id, items_text, final_total, fio, phone, address, promo_code, discount)
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
    return jsonify([{
        'id': o['id'], 'status': o['status'], 'total': o['total'],
        'created_at': o['created_at'][:10], 'items': o['items'],
        'fio': o['fio'], 'address': o['address'],
    } for o in orders])

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
