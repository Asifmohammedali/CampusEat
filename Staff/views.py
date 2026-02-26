from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from admindashboard.models import Menu, Item, Category,  User
from student.models import Order, CartItem,Wallet


def is_staff(request):
    return request.session.get('user_id') and request.session.get('role') == 'STAFF'


# ── Staff Dashboard ───────────────────────────────────────────────────────────
def staff_dashboard(request):
    if not is_staff(request):
        return redirect('login')

    today = timezone.localdate()
    staff_id = request.session.get('user_id')

    # Quick stats for dashboard cards
    todays_menu_count  = Menu.objects.filter(date_added=today).count()
    todays_orders      = Order.objects.filter(date=today).exclude(status='CANCELLED').count()
    pending_orders     = Order.objects.filter(date=today, status='PENDING').count()
    completed_orders = Order.objects.filter(
    date=today,
    status='COMPLETED',
    accepted_by_id=staff_id
).count()

    return render(request, 'staff_dashboard.html', {
        'todays_menu_count': todays_menu_count,
        'todays_orders':     todays_orders,
        'pending_orders':    pending_orders,
        'completed_orders':  completed_orders,
        'today':             today,
    })


# ── Staff Prepare Menu (same logic as admin) ──────────────────────────────────
def staff_prepare_menu(request):
    if not is_staff(request):
        return redirect('login')

    today = timezone.localdate()

    if request.method == 'POST':
        action   = request.POST.get('action')
        item_ids = request.POST.getlist('item_ids')

        if action == 'add_to_menu':
            if not item_ids:
                messages.error(request, 'Select at least one item to add.')
            else:
                added = 0
                for item_id in item_ids:
                    item = get_object_or_404(Item, id=item_id)
                    if not Menu.objects.filter(item=item, date_added=today).exists():
                        Menu.objects.create(item=item)
                        added += 1
                if added:
                    messages.success(request, f'{added} item(s) added to today\'s menu.')
                else:
                    messages.error(request, 'Selected items are already in today\'s menu.')

        elif action == 'stockout':
            menu_id    = request.POST.get('menu_id')
            menu_entry = get_object_or_404(Menu, id=menu_id, date_added=today)
            menu_entry.status = 'UNAVAILABLE'
            menu_entry.save()
            messages.success(request, f'"{menu_entry.item.name}" marked as stock out.')

        elif action == 'restock':
            menu_id    = request.POST.get('menu_id')
            menu_entry = get_object_or_404(Menu, id=menu_id, date_added=today)
            menu_entry.status = 'AVAILABLE'
            menu_entry.save()
            messages.success(request, f'"{menu_entry.item.name}" marked as available.')

        return redirect('staff_prepare_menu')

    todays_menu     = Menu.objects.filter(date_added=today).select_related('item', 'item__category').order_by('item__category__name', 'item__name')
    has_menu        = todays_menu.exists()
    added_item_ids  = todays_menu.values_list('item_id', flat=True)
    available_items = Item.objects.exclude(id__in=added_item_ids).select_related('category').order_by('category__name', 'name')

    return render(request, 'staff_prepare_menu.html', {
        'todays_menu':     todays_menu,
        'has_menu':        has_menu,
        'available_items': available_items,
        'today':           today,
    })


# ── Staff Order Management  ────────────────────────────────
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST



def is_staff(request):
    return request.session.get('user_id') and request.session.get('role') == 'STAFF'


def staff_order_management(request):
    if not is_staff(request):
        return redirect('login')

    today = timezone.localdate()

    # All non-delivered, non-cancelled orders for today
    orders = (
        Order.objects
        .filter(date=today)
        .exclude(status__in=['COMPLETED', 'REJECTED', 'CANCELLED'])
        .select_related('user', 'accepted_by')
        .order_by('ordered_at')
    )

    return render(request, 'staff_order_management.html', {
        'orders': orders,
        'today':  today,
    })


def order_detail_partial(request, order_id):
    """AJAX — returns item rows for a specific order."""
    if not is_staff(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    order      = get_object_or_404(Order, id=order_id)
    cart_items = CartItem.objects.filter(order=order).select_related('item', 'item__category')

    return render(request, 'staff_order_detail_partial.html', {
        'order':      order,
        'cart_items': cart_items,
    })


@require_POST
def update_order_status(request, order_id):
    if not is_staff(request):
        return redirect('login')

    order  = get_object_or_404(Order, id=order_id)
    action = request.POST.get('action')
    staff  = get_object_or_404(User, id=request.session['user_id'])

    # Get last wallet balance of the student
    last_wallet = Wallet.objects.filter(user=order.user).order_by('-date', '-time').first()
    last_balance = last_wallet.balance if last_wallet else 0

    if action == 'accept':
        order.status      = 'CONFIRMED'
        order.accepted_by = staff

        # 🔥 Refund logic
        new_balance = last_balance + order.total_amount
        Wallet.objects.create(
            user=order.user,
            balance=new_balance,
            amount=order.total_amount,
            transaction_type="RETURN",
            order=order
        )

    elif action == 'reject':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            reason = 'Rejected by staff.'

        order.status          = 'REJECTED'
        order.accepted_by     = staff
        order.rejected_reason = reason

        #  Refund logic
        new_balance = last_balance + order.total_amount
        Wallet.objects.create(
            user=order.user,
            balance=new_balance,
            amount=order.total_amount,
            transaction_type="RETURN",
            order=order
        )

    elif action == 'preparing':
        order.status = 'PREPARING'

    elif action == 'ready':
        order.status = 'READY'

    elif action == 'delivered':
        order.status       = 'COMPLETED'
        order.delivered_at = timezone.now()

    order.save()
    return redirect('staff_order_management')



def print_receipt(request, order_id):
    if not is_staff(request):
        return redirect('login')

    order      = get_object_or_404(Order, id=order_id)
    cart_items = CartItem.objects.filter(order=order).select_related('item', 'item__category')

    return render(request, 'receipt.html', {
        'order':      order,
        'cart_items': cart_items,
    })

# ── Staff Order History ───────────────────────────────────────────────────────
def staff_order_history(request):
    if not is_staff(request):
        return redirect('login')

    staff_id = request.session.get('user_id')

    orders = Order.objects.select_related('user').filter(
        accepted_by_id=staff_id,
        status__in=['COMPLETED', 'REJECTED'],
    ).order_by('-ordered_at')

    return render(request, 'staff_order_history.html', {
        'orders': orders,
    })
