from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
from admindashboard.models import User, Menu
from student.models import Cart, CartItem, Order, Wallet

def is_student(request):
    return request.session.get('user_id') and request.session.get('role') == 'STUDENT'


def get_wallet_balance(user):
    last = Wallet.objects.filter(user=user).order_by('-date', '-time').first()
    return last.balance if last else 0


def get_cart_count(user):
    try:
        cart = Cart.objects.get(user=user)
        return cart.items.filter(order_id__isnull=True).count()
    except Cart.DoesNotExist:
        return 0


# ── Student Dashboard / Menu ──────────────────────────────────────────────────
def student_dashboard(request):
    if not is_student(request):
        return redirect('login')

    today = timezone.localdate()
    user  = get_object_or_404(User, id=request.session['user_id'])

    todays_menu = (
        Menu.objects
        .filter(date_added=today)
        .select_related('item', 'item__category')
        .order_by('item__category__name', 'item__name')
    )

    categories = {}
    for entry in todays_menu:
        cat_name = entry.item.category.name
        if cat_name not in categories:
            categories[cat_name] = []
        categories[cat_name].append(entry)

    return render(request, 'student_dashboard.html', {
        'user':        user,
        'categories':  categories,
        'has_menu':    todays_menu.exists(),
        'cart_count':  get_cart_count(user),
        'today':       today,
    })


# ── Add to Cart ───────────────────────────────────────────────────────────────
def add_to_cart(request):
    if not is_student(request):
        return JsonResponse({'error': 'Login required'}, status=401)

    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)

    item_id = request.POST.get('item_id')
    menu_entry = get_object_or_404(Menu, item_id=item_id, date_added=timezone.localdate(), status='AVAILABLE')
    user = get_object_or_404(User, id=request.session['user_id'])

    # Get or create cart for user
    cart, _ = Cart.objects.get_or_create(user=user)

    # Check if item already in cart with no order (active cart item)
    existing = CartItem.objects.filter(cart=cart, item_id=item_id, order__isnull=True).first()

    if existing:
        existing.quantity += 1
        existing.subtotal  = existing.price * existing.quantity
        existing.save()
        quantity = existing.quantity
    else:
        price    = menu_entry.item.price
        cart_item = CartItem.objects.create(
            cart     = cart,
            item_id  = item_id,
            price    = price,
            quantity = 1,
            subtotal = price,
            order    = None,
        )
        quantity = 1

    cart_count = CartItem.objects.filter(cart=cart, order__isnull=True).count()
    return JsonResponse({'success': True, 'quantity': quantity, 'cart_count': cart_count})


# ── Cart Page ─────────────────────────────────────────────────────────────────
def view_cart(request):
    if not is_student(request):
        return redirect('login')

    user = get_object_or_404(User, id=request.session['user_id'])

    try:
        cart       = Cart.objects.get(user=user)
        cart_items = CartItem.objects.filter(cart=cart, order__isnull=True).select_related('item', 'item__category')
    except Cart.DoesNotExist:
        cart_items = []

    grand_total    = sum(ci.subtotal for ci in cart_items)
    wallet_balance = get_wallet_balance(user)
    today          = timezone.localdate()

    # Flag items not in today's menu
    for ci in cart_items:
        ci.in_todays_menu = Menu.objects.filter(
            item=ci.item,
            date_added=today,
            status='AVAILABLE'
        ).exists()

    has_unavailable = any(not ci.in_todays_menu for ci in cart_items)

    return render(request, 'cart.html', {
        'user':            user,
        'cart_items':      cart_items,
        'grand_total':     grand_total,
        'wallet_balance':  wallet_balance,
        'cart_count':      len(cart_items),
        'has_unavailable': has_unavailable,
    })


# ── Update Cart Item Quantity ─────────────────────────────────────────────────
def update_cart(request):
    if not is_student(request):
        return JsonResponse({'error': 'Login required'}, status=401)

    cart_item_id = request.POST.get('cart_item_id')
    action       = request.POST.get('action')  # 'increment' or 'decrement'
    user         = get_object_or_404(User, id=request.session['user_id'])
    cart_item    = get_object_or_404(CartItem, id=cart_item_id, cart__user=user, order__isnull=True)

    if action == 'increment':
        cart_item.quantity += 1
        cart_item.subtotal  = cart_item.price * cart_item.quantity
        cart_item.save()
    elif action == 'decrement':
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.subtotal  = cart_item.price * cart_item.quantity
            cart_item.save()
        else:
            cart_item.delete()
            return JsonResponse({'success': True, 'removed': True})

    return JsonResponse({'success': True, 'quantity': cart_item.quantity, 'subtotal': float(cart_item.subtotal)})


# ── Remove Cart Item ──────────────────────────────────────────────────────────
def remove_cart_item(request, cart_item_id):
    if not is_student(request):
        return redirect('login')

    user      = get_object_or_404(User, id=request.session['user_id'])
    cart_item = get_object_or_404(CartItem, id=cart_item_id, cart__user=user, order__isnull=True)
    cart_item.delete()
    return redirect('view_cart')


# ── Place Order ───────────────────────────────────────────────────────────────
@transaction.atomic
def place_order(request):
    if not is_student(request):
        return redirect('login')

    if request.method != 'POST':
        return redirect('view_cart')

    user = get_object_or_404(User, id=request.session['user_id'])

    try:
        cart       = Cart.objects.get(user=user)
        cart_items = CartItem.objects.filter(cart=cart, order__isnull=True)
    except Cart.DoesNotExist:
        messages.error(request, 'Your cart is empty.')
        return redirect('view_cart')

    if not cart_items.exists():
        messages.error(request, 'Your cart is empty.')
        return redirect('view_cart')

    grand_total    = sum(ci.subtotal for ci in cart_items)
    wallet_balance = get_wallet_balance(user)

    # ── Validate all cart items are in today's menu & available ─────────
    today_check = timezone.localdate()
    unavailable_items = []
    for ci in cart_items:
        in_menu = Menu.objects.filter(
            item=ci.item,
            date_added=today_check,
            status='AVAILABLE'
        ).exists()
        if not in_menu:
            unavailable_items.append(ci.item.name)

    if unavailable_items:
        names = ', '.join(unavailable_items)
        messages.error(request, f"Some items are not in today's menu: {names}. Please remove them from your cart.")

        return redirect('view_cart')

    # ── Insufficient balance ──────────────────────────────────────────────
    if wallet_balance < grand_total:
        messages.error(request, f'Insufficient wallet balance. Your balance is ₹{wallet_balance:.2f} but order total is ₹{grand_total:.2f}.')
        return redirect('view_cart')

    # ── Create order ──────────────────────────────────────────────────────
    order = Order.objects.create(
        user         = user,
        total_amount = grand_total,
        status       = 'PENDING',
        delivered_at = None,
    )

    # Link cart items to this order
    cart_items.update(order=order)

    # ── Deduct from wallet ────────────────────────────────────────────────
    new_balance = wallet_balance - grand_total
    Wallet.objects.create(
        user             = user,
        balance          = new_balance,
        amount           = grand_total,
        transaction_type = 'DEBIT',
        order            = order,
    )

    messages.success(request, f'Order #{order.id} placed successfully! ₹{grand_total:.2f} deducted from wallet.')
    return redirect('order_history_student')


# ── Order History ─────────────────────────────────────────────────────────────
def order_history_student(request):
    if not is_student(request):
        return redirect('login')

    user   = get_object_or_404(User, id=request.session['user_id'])
    orders = Order.objects.filter(user=user).order_by('-ordered_at')

    return render(request, 'order_history_student.html', {
        'user':       user,
        'orders':     orders,
        'cart_count': get_cart_count(user),
    })


# ── Wallet / Transactions ─────────────────────────────────────────────────────
def student_wallet(request):
    if not is_student(request):
        return redirect('login')

    user         = get_object_or_404(User, id=request.session['user_id'])
    transactions = Wallet.objects.filter(user=user).order_by('-date', '-time')
    balance      = get_wallet_balance(user)

    return render(request, 'student_wallet.html', {
        'user':         user,
        'transactions': transactions,
        'balance':      balance,
        'cart_count':   get_cart_count(user),
    })

def student_order_status(request):
    if not is_student(request):
        return redirect('login')

    user  = get_object_or_404(User, id=request.session['user_id'])
    today = timezone.localdate()

    orders = (
        Order.objects
        .filter(user=user, date=today)
        .order_by('-ordered_at')
        .prefetch_related('cart_items__item__category')
    )

    return render(request, 'student_order_status.html', {
        'user':       user,
        'orders':     orders,
        'today':      today,
        'cart_count': get_cart_count(user),
    })
