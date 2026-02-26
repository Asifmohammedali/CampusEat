from django.shortcuts import render, get_object_or_404

# Create your views here.
from django.shortcuts import render, redirect
from admindashboard.models import Category,Item,Menu
from django.utils import timezone
from django.contrib import messages
from .models  import User
from student.models import Wallet,Order,CartItem
from django.db.models import Sum, F, ExpressionWrapper, DecimalField ,Q, Count
from datetime import timedelta, date
from student.models import Cart, CartItem, Order, Wallet
from admindashboard.models import User, Menu








def is_admin(request):
    return request.session.get('user_id') and request.session.get('role') == 'ADMIN'


def admin_dashboard(request):
    if not is_admin(request):
        return redirect('login')

    today       = timezone.localdate()
    filter_type = request.GET.get('filter', 'today')
    date_from   = request.GET.get('date_from', '')
    date_to     = request.GET.get('date_to', '')

    # ── Date range ────────────────────────────────────────────────────────
    if filter_type == 'today':
        d_from = d_to = today
    elif filter_type == 'week':
        d_from = today - timedelta(days=today.weekday())
        d_to   = today
    elif filter_type == 'month':
        d_from = today.replace(day=1)
        d_to   = today
    elif filter_type == 'custom':
        try:
            d_from = date.fromisoformat(date_from)
            d_to   = date.fromisoformat(date_to)
        except (ValueError, TypeError):
            d_from = d_to = today
    else:
        d_from = d_to = today

    # ── Orders in range (exclude cancelled) ───────────────────────────────
    orders_qs = Order.objects.filter(
        date__gte=d_from, date__lte=d_to
    ).exclude(status__in=['CANCELLED', 'REJECTED'])

    order_ids = orders_qs.values_list('id', flat=True)

    # ── Revenue ───────────────────────────────────────────────────────────
    total_revenue = orders_qs.aggregate(t=Sum('total_amount'))['t'] or 0
    total_orders = orders_qs.exclude(
    status__in=['REJECTED', 'CANCELLED']
    ).count()


    # ── Most bought products (by qty) ─────────────────────────────────────
    top_products = (
        CartItem.objects
        .filter(order_id__in=order_ids)
        .values('item__name', 'item__category__name')
        .annotate(total_qty=Sum('quantity'), total_rev=Sum('subtotal'))
        .order_by('-total_qty')[:5]
    )

    # ── Top revenue-generating products ───────────────────────────────────
    top_revenue_products = (
        CartItem.objects
        .filter(order_id__in=order_ids)
        .values('item__name', 'item__category__name')
        .annotate(total_rev=Sum('subtotal'), total_qty=Sum('quantity'))
        .order_by('-total_rev')[:5]
    )

    # ── Most bought combos (pairs of items bought in same order) ──────────
    # Self-join CartItem on same order_id where item_id differs
    from django.db import connection
    order_id_list = list(order_ids)
    if order_id_list:
        with connection.cursor() as cursor:
            placeholders = ','.join(['%s'] * len(order_id_list))
            cursor.execute(f"""
                SELECT a.item_id, b.item_id,
                       ia.name AS item_a, ib.name AS item_b,
                       COUNT(*) AS combo_count
                FROM cart_items a
                JOIN cart_items b ON a.order_id = b.order_id AND a.item_id < b.item_id
                JOIN items ia ON a.item_id = ia.id
                JOIN items ib ON b.item_id = ib.id
                WHERE a.order_id IN ({placeholders})
                GROUP BY a.item_id, b.item_id, ia.name, ib.name
                ORDER BY combo_count DESC
                LIMIT 5
            """, order_id_list)
            top_combos = cursor.fetchall()
    else:
        top_combos = []
        # (item_a_id, item_b_id, item_a_name, item_b_name, count)

    # ── Fixed stats (not date-filtered) ───────────────────────────────────
    total_students    = User.objects.filter(role='STUDENT').count()
    total_staff       = User.objects.filter(role='STAFF').count()
    todays_menu_count = Menu.objects.filter(date_added=today).count()

    # ── Orders by status (for today range pie data) ───────────────────────
    status_counts = (
        orders_qs.values('status')
        .annotate(count=Count('id'))
    )
    status_data = {s['status']: s['count'] for s in status_counts}

    # ── Daily revenue trend (last 7 days, always) ─────────────────────────
    trend_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        rev = Order.objects.filter(date=day).exclude(status__in=['CANCELLED', 'REJECTED']) \
                   .aggregate(t=Sum('total_amount'))['t'] or 0
        trend_data.append({'day': day.strftime('%a'), 'revenue': float(rev)})

    return render(request, 'admin_dashboard.html', {
        'filter_type':          filter_type,
        'date_from':            d_from,
        'date_to':              d_to,
        'total_revenue':        total_revenue,
        'total_orders':         total_orders,
        'total_students':       total_students,
        'total_staff':          total_staff,
        'todays_menu_count':    todays_menu_count,
        'top_products':         top_products,
        'top_revenue_products': top_revenue_products,
        'top_combos':           top_combos,
        'status_data':          status_data,
        'trend_data':           trend_data,
        'today':                today,
    })

def is_admin(request):
    return request.session.get('user_id') and request.session.get('role') == 'ADMIN'


def manage_category(request):
    if not is_admin(request):
        return redirect('login')

    if request.method == 'POST':
        action      = request.POST.get('action')
        name        = request.POST.get('category_name', '').strip()
        category_id = request.POST.get('category_id')

        if not name:
            messages.error(request, 'Category name cannot be empty.')
            return redirect('manage_category')

        if action == 'add':
            if Category.objects.filter(name__iexact=name).exists():
                messages.error(request, f'"{name}" already exists.')
            else:
                Category.objects.create(name=name)
                messages.success(request, f'"{name}" added successfully.')

        elif action == 'edit':
            category = get_object_or_404(Category, id=category_id)
            if Category.objects.filter(name__iexact=name).exclude(id=category_id).exists():
                messages.error(request, f'"{name}" already exists.')
            else:
                category.name = name
                category.save()
                messages.success(request, f'Category updated to "{name}".')

        return redirect('manage_category')

    categories = Category.objects.all().order_by('-created_at')
    return render(request, 'category.html', {'categories': categories})


def delete_category(request, category_id):
    if not is_admin(request):
        return redirect('login')

    if request.method == 'POST':
        category = get_object_or_404(Category, id=category_id)
        name = category.name
        category.delete()
        messages.success(request, f'"{name}" deleted successfully.')

    return redirect('manage_category')

def is_admin(request):
    return request.session.get('user_id') and request.session.get('role') == 'ADMIN'


def manage_items(request):
    if not is_admin(request):
        return redirect('login')

    if request.method == 'POST':
        action      = request.POST.get('action')
        name        = request.POST.get('name', '').strip()
        category_id = request.POST.get('category')
        description = request.POST.get('description', '').strip()
        price       = request.POST.get('price', '').strip()
        image       = request.FILES.get('image')
        item_id     = request.POST.get('item_id')

        # Basic validation
        if not name or not category_id or not price:
            messages.error(request, 'Name, category and price are required.')
            return redirect('manage_items')

        try:
            price = float(price)
            if price < 0:
                raise ValueError
        except ValueError:
            messages.error(request, 'Enter a valid price.')
            return redirect('manage_items')

        category = get_object_or_404(Category, id=category_id)

        # ── Add ──────────────────────────────────────────────
        if action == 'add':
            item = Item(
                name=name,
                category=category,
                description=description,
                price=price,
            )
            if image:
                item.image = image
            item.save()
            messages.success(request, f'"{name}" added successfully.')

        # ── Edit ─────────────────────────────────────────────
        elif action == 'edit':
            item = get_object_or_404(Item, id=item_id)
            item.name        = name
            item.category    = category
            item.description = description
            item.price       = price
            if image:
                # Remove old image
                if item.image:
                    if os.path.isfile(item.image.path):
                        os.remove(item.image.path)
                item.image = image
            item.save()
            messages.success(request, f'"{name}" updated successfully.')

        return redirect('manage_items')

    items      = Item.objects.select_related('category').all().order_by('-created_at')
    categories = Category.objects.all().order_by('name')
    return render(request, 'item.html', {'items': items, 'categories': categories})


def delete_item(request, item_id):
    if not is_admin(request):
        return redirect('login')

    if request.method == 'POST':
        item = get_object_or_404(Item, id=item_id)
        name = item.name
        # Remove image file
        if item.image:
            if os.path.isfile(item.image.path):
                os.remove(item.image.path)
        item.delete()
        messages.success(request, f'"{name}" deleted successfully.')

    return redirect('manage_items')



def is_admin(request):
    return request.session.get('user_id') and request.session.get('role') == 'ADMIN'


def prepare_menu(request):
    if not is_admin(request):
        return redirect('login')

    today = timezone.localdate()

    # ── Add items to today's menu ─────────────────────────────────────────
    if request.method == 'POST':
        action  = request.POST.get('action')
        item_ids = request.POST.getlist('item_ids')  # multiple checkboxes

        if action == 'add_to_menu':
            if not item_ids:
                messages.error(request, 'Select at least one item to add.')
            else:
                added = 0
                for item_id in item_ids:
                    item = get_object_or_404(Item, id=item_id)
                    # avoid duplicate entry for same item on same date
                    if not Menu.objects.filter(item=item, date_added=today).exists():
                        Menu.objects.create(item=item)
                        added += 1
                if added:
                    messages.success(request, f'{added} item(s) added to today\'s menu.')
                else:
                    messages.error(request, 'Selected items are already in today\'s menu.')

        elif action == 'stockout':
            menu_id = request.POST.get('menu_id')
            menu_entry = get_object_or_404(Menu, id=menu_id, date_added=today)
            menu_entry.status = 'UNAVAILABLE'
            menu_entry.save()
            messages.success(request, f'"{menu_entry.item.name}" marked as stock out.')

        elif action == 'restock':
            menu_id = request.POST.get('menu_id')
            menu_entry = get_object_or_404(Menu, id=menu_id, date_added=today)
            menu_entry.status = 'AVAILABLE'
            menu_entry.save()
            messages.success(request, f'"{menu_entry.item.name}" marked as available.')

        return redirect('prepare_menu')

    # ── Fetch today's menu ────────────────────────────────────────────────
    todays_menu = Menu.objects.filter(date_added=today).select_related('item', 'item__category')
    has_menu    = todays_menu.exists()

    # Items not yet added to today's menu
    added_item_ids = todays_menu.values_list('item_id', flat=True)
    available_items = Item.objects.exclude(id__in=added_item_ids).select_related('category').order_by('category__name', 'name')

    return render(request, 'prepare_menu.html', {
        'todays_menu':    todays_menu,
        'has_menu':       has_menu,
        'available_items': available_items,
        'today':          today,
    })


def landing(request):
    # If student session found, redirect to student dashboard
    if request.session.get('user_id') and request.session.get('role') == 'STUDENT':
        return redirect('user_dashboard')

    today = timezone.localdate()

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

    return render(request, 'landing.html', {
        'categories':       categories,
        'has_menu':         todays_menu.exists(),
        'todays_menu_count': todays_menu.count(),
    })



def is_admin(request):
    return request.session.get('user_id') and request.session.get('role') == 'ADMIN'


from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Q
from admindashboard.models import User
from student.models import Wallet


def is_admin(request):
    return request.session.get('user_id') and request.session.get('role') == 'ADMIN'


def get_wallet_balance(user):
    """Get latest balance for a user, default 0 if no transactions."""
    last = Wallet.objects.filter(user=user).order_by('-date', '-time').first()
    return last.balance if last else 0


def recharge_wallet(request):
    if not is_admin(request):
        return redirect('login')

    student     = None
    search_query = request.GET.get('q', '').strip()

    # ── Search ────────────────────────────────────────────────────────────
    if search_query:
        students = User.objects.filter(
            role='STUDENT',
            is_blocked=False
        ).filter(
            Q(name__icontains=search_query) |
            Q(admission_number__icontains=search_query)
        )
    else:
        students = None

    # ── Recharge POST ─────────────────────────────────────────────────────
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        amount_str = request.POST.get('amount', '').strip()

        try:
            student = User.objects.get(id=student_id, role='STUDENT')
        except User.DoesNotExist:
            messages.error(request, 'Student not found.')
            return redirect('recharge_wallet')

        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError
        except (ValueError, Exception):
            messages.error(request, 'Enter a valid amount greater than 0.')
            return redirect(f"{request.path}?q={search_query}")

        prev_balance = get_wallet_balance(student)
        new_balance  = prev_balance + amount

        Wallet.objects.create(
            user             = student,
            balance          = new_balance,
            amount           = amount,
            transaction_type = 'CREDIT',
            order            = None,
        )

        messages.success(request, f'₹{amount:.0f} credited to {student.name}. New balance: ₹{new_balance:.0f}')
        return redirect(f"{request.path}?q={search_query}")

    # Attach current balance to each student in results
    if students is not None:
        for s in students:
            s.current_balance = get_wallet_balance(s)

    return render(request, 'recharge_wallet.html', {
        'students':     students,
        'search_query': search_query,
    })

def is_admin(request):
    return request.session.get('user_id') and request.session.get('role') == 'ADMIN'


def transaction_history(request):
    if not is_admin(request):
        return redirect('login')

    search_query  = request.GET.get('q', '').strip()
    selected_date = request.GET.get('date', '').strip()
    student_id    = request.GET.get('student_id', '').strip()

    student      = None
    students     = None
    transactions = None

    # ── Search students ───────────────────────────────────────────────────
    if search_query:
        students = User.objects.filter(
            role='STUDENT'
        ).filter(
            Q(name__icontains=search_query) |
            Q(admission_number__icontains=search_query)
        )

    # ── Load transactions for selected student ────────────────────────────
    if student_id:
        try:
            student = User.objects.get(id=student_id, role='STUDENT')
            transactions = Wallet.objects.filter(user=student).order_by('-date', '-time')

            # Filter by date if provided
            if selected_date:
                transactions = transactions.filter(date=selected_date)

        except User.DoesNotExist:
            pass

    return render(request, 'transaction_history.html', {
        'search_query':  search_query,
        'students':      students,
        'student':       student,
        'transactions':  transactions,
        'selected_date': selected_date,
        'student_id':    student_id,
    })




def is_admin(request):
    return request.session.get('user_id') and request.session.get('role') == 'ADMIN'


def revenue(request):
    if not is_admin(request):
        return redirect('login')

    today = timezone.localdate()

    # ── Determine date range from filter ─────────────────────────────────
    filter_type  = request.GET.get('filter', 'today')
    date_from    = request.GET.get('date_from', '')
    date_to      = request.GET.get('date_to', '')

    if filter_type == 'today':
        date_from = date_to = today
    elif filter_type == 'week':
        date_from = today - timedelta(days=today.weekday())   # Monday
        date_to   = today
    elif filter_type == 'month':
        date_from = today.replace(day=1)
        date_to   = today
    elif filter_type == 'custom':
        try:
            date_from = date.fromisoformat(date_from)
            date_to   = date.fromisoformat(date_to)
        except (ValueError, TypeError):
            date_from = date_to = today
    else:
        date_from = date_to = today

    # ── Orders in range (exclude cancelled) ───────────────────────────────
    orders = Order.objects.filter(
        date__gte=date_from,
        date__lte=date_to,
    ).exclude(status__in=['CANCELLED', 'REJECTED'])

    order_ids = orders.values_list('id', flat=True)

    # ── Aggregate cart items by item ──────────────────────────────────────
    # Group by item, sum quantity and total amount
    item_summary = (
        CartItem.objects
        .filter(order_id__in=order_ids)
        .values('item__name', 'item__category__name', 'price')
        .annotate(
            total_quantity = Sum('quantity'),
            total_amount   = Sum(
                ExpressionWrapper(F('price') * F('quantity'), output_field=DecimalField())
            )
        )
        .order_by('item__category__name', 'item__name')
    )

    total_revenue  = sum(row['total_amount'] for row in item_summary) if item_summary else 0
    total_orders   = orders.count()
    total_items_sold = sum(row['total_quantity'] for row in item_summary) if item_summary else 0

    return render(request, 'revenue.html', {
        'item_summary':    item_summary,
        'total_revenue':   total_revenue,
        'total_orders':    total_orders,
        'total_items_sold': total_items_sold,
        'filter_type':     filter_type,
        'date_from':       date_from,
        'date_to':         date_to,
        'today':           today,
    })




def is_admin(request):
    return request.session.get('user_id') and request.session.get('role') == 'ADMIN'


def order_history(request):
    if not is_admin(request):
        return redirect('login')

    today       = timezone.localdate()
    search      = request.GET.get('q', '').strip()
    filter_type = request.GET.get('filter', 'all')
    date_from   = request.GET.get('date_from', '')
    date_to     = request.GET.get('date_to', '')

    # ── Base queryset ─────────────────────────────────────────────────────
    orders = Order.objects.select_related('user').order_by('-ordered_at')

    # ── Date filter ───────────────────────────────────────────────────────
    if filter_type == 'today':
        orders = orders.filter(date=today)
    elif filter_type == 'week':
        week_start = today - timedelta(days=today.weekday())
        orders = orders.filter(date__gte=week_start, date__lte=today)
    elif filter_type == 'month':
        orders = orders.filter(date__gte=today.replace(day=1), date__lte=today)
    elif filter_type == 'custom':
        try:
            df = date.fromisoformat(date_from)
            dt = date.fromisoformat(date_to)
            orders = orders.filter(date__gte=df, date__lte=dt)
        except (ValueError, TypeError):
            pass

    # ── Search by order id or admission number ────────────────────────────
    if search:
        orders = orders.filter(
            Q(id__icontains=search) |
            Q(user__admission_number__icontains=search)
        )

    return render(request, 'order_history.html', {
        'orders':      orders,
        'search':      search,
        'filter_type': filter_type,
        'date_from':   date_from,
        'date_to':     date_to,
        'today':       today,
    })


def order_detail(request, order_id):
    """Returns order items as partial HTML for the modal."""
    if not is_admin(request):
        return redirect('login')

    order      = get_object_or_404(Order, id=order_id)
    cart_items = CartItem.objects.filter(order=order).select_related('item', 'item__category')

    return render(request, 'order_detail_partial.html', {
        'order':      order,
        'cart_items': cart_items,
    })


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from admindashboard.models import User


def is_admin(request):
    return request.session.get('user_id') and request.session.get('role') == 'ADMIN'


# ══════════════════════════════════════════════════════
#  STAFF
# ══════════════════════════════════════════════════════

def manage_staff(request):
    if not is_admin(request):
        return redirect('login')

    if request.method == 'POST':
        action    = request.POST.get('action')
        name      = request.POST.get('name', '').strip()
        email     = request.POST.get('email', '').strip()
        phone     = request.POST.get('phone', '').strip()
        password  = request.POST.get('password', '').strip()
        staff_id  = request.POST.get('staff_id', '').strip()

        if not name or not email:
            messages.error(request, 'Name and email are required.')
            return redirect('manage_staff')

        # ── Add ──────────────────────────────────────────
        if action == 'add':
            if User.objects.filter(email=email).exists():
                messages.error(request, f'Email "{email}" is already registered.')
                return redirect('manage_staff')
            if not password:
                messages.error(request, 'Password is required when adding staff.')
                return redirect('manage_staff')
            User.objects.create(
                name=name, email=email, phone=phone,
                password=password, role='STAFF'
            )
            messages.success(request, f'Staff member "{name}" added successfully.')

        # ── Edit ─────────────────────────────────────────
        elif action == 'edit':
            staff = get_object_or_404(User, id=staff_id, role='STAFF')
            # Email uniqueness check (exclude self)
            if User.objects.filter(email=email).exclude(id=staff_id).exists():
                messages.error(request, f'Email "{email}" is already used by another user.')
                return redirect('manage_staff')
            staff.name  = name
            staff.email = email
            staff.phone = phone
            if password:
                staff.password = password
            staff.save()
            messages.success(request, f'"{name}" updated successfully.')

        return redirect('manage_staff')

    staff_list = User.objects.filter(role='STAFF').order_by('-created_at')
    return render(request, 'manage_staff.html', {'staff_list': staff_list})


def delete_staff(request, staff_id):
    if not is_admin(request):
        return redirect('login')
    if request.method == 'POST':
        staff = get_object_or_404(User, id=staff_id, role='STAFF')
        name  = staff.name
        staff.delete()
        messages.success(request, f'"{name}" has been removed.')
    return redirect('manage_staff')


# ══════════════════════════════════════════════════════
#  STUDENTS
# ══════════════════════════════════════════════════════

def manage_students(request):
    if not is_admin(request):
        return redirect('login')

    search   = request.GET.get('q', '').strip()
    students = User.objects.filter(role='STUDENT').order_by('-created_at')

    if search:
        from django.db.models import Q
        students = students.filter(
            Q(name__icontains=search) |
            Q(admission_number__icontains=search) |
            Q(email__icontains=search)
        )

    return render(request, 'manage_students.html', {
        'students': students,
        'search':   search,
    })


def delete_student(request, student_id):
    if not is_admin(request):
        return redirect('login')
    if request.method == 'POST':
        student = get_object_or_404(User, id=student_id, role='STUDENT')
        name    = student.name
        student.delete()
        messages.success(request, f'Student "{name}" has been removed.')
    return redirect('manage_students')


def toggle_block_student(request, student_id):
    if not is_admin(request):
        return redirect('login')
    if request.method == 'POST':
        student = get_object_or_404(User, id=student_id, role='STUDENT')
        student.is_blocked = not student.is_blocked
        student.save()
        action = 'blocked' if student.is_blocked else 'unblocked'
        messages.success(request, f'"{student.name}" has been {action}.')
    return redirect('manage_students')