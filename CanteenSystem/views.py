from django.shortcuts import render, redirect
from django.contrib import messages
from admindashboard.models import User


def login_view(request):
    if request.session.get('user_id'):
        return _redirect_by_role(request.session.get('role'))

    if request.method == 'POST':
        login_mode = request.POST.get('login_mode')
        password   = request.POST.get('password', '').strip()

        user = None

        if login_mode == 'email':
            email = request.POST.get('email', '').strip()
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                pass

        elif login_mode == 'admission':
            admission_number = request.POST.get('admission_number', '').strip()
            try:
                user = User.objects.get(admission_number=admission_number, role='STUDENT')
            except User.DoesNotExist:
                pass

        if user is None or user.password != password:
            messages.error(request, 'Invalid credentials. Please try again.')
            return render(request, 'login.html')

        if user.is_blocked:
            messages.error(request, 'Your account has been blocked. Contact admin.')
            return render(request, 'login.html')

        request.session['user_id']          = user.id
        request.session['user_name']        = user.name
        request.session['user_email']       = user.email
        request.session['role']             = user.role
        request.session['admission_number'] = user.admission_number or ''

        return _redirect_by_role(user.role)

    return render(request, 'login.html')


def logout_view(request):
    request.session.flush()
    return redirect('login')


def _redirect_by_role(role):
    redirects = {
        'ADMIN':   'admin_dashboard',
        'STAFF':   'staff_dashboard',
        'STUDENT': 'student_dashboard',
    }
    return redirect(redirects.get(role, 'login'))


from django.shortcuts import render, redirect
from django.contrib import messages
from admindashboard.models import User


def register(request):
    if request.session.get('user_id'):
        role = request.session.get('role')
        if role == 'STUDENT':
            return redirect('student_dashboard')
        elif role == 'ADMIN':
            return redirect('admin_dashboard')
        elif role == 'STAFF':
            return redirect('staff_dashboard')

    if request.method == 'POST':
        name             = request.POST.get('name', '').strip()
        admission_number = request.POST.get('admission_number', '').strip()
        email            = request.POST.get('email', '').strip()
        phone            = request.POST.get('phone', '').strip()
        password         = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        # ── Validations ───────────────────────────────────────────────────
        if not all([name, admission_number, email, password, confirm_password]):
            messages.error(request, 'All fields except phone are required.')
            return render(request, 'register.html', {'form_data': request.POST})

        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'register.html', {'form_data': request.POST})

        if len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
            return render(request, 'register.html', {'form_data': request.POST})

        if User.objects.filter(email=email).exists():
            messages.error(request, f'Email "{email}" is already registered.')
            return render(request, 'register.html', {'form_data': request.POST})

        if User.objects.filter(admission_number=admission_number).exists():
            messages.error(request, f'Admission number "{admission_number}" is already registered.')
            return render(request, 'register.html', {'form_data': request.POST})

        # ── Create student ────────────────────────────────────────────────
        user = User.objects.create(
            name             = name,
            admission_number = admission_number,
            email            = email,
            phone            = phone,
            password         = password,
            role             = 'STUDENT',
        )

        # ── Auto login ────────────────────────────────────────────────────
        request.session['user_id']         = user.id
        request.session['user_name']       = user.name
        request.session['user_email']      = user.email
        request.session['role']            = 'STUDENT'
        request.session['admission_number'] = user.admission_number

        messages.success(request, f'Welcome, {user.name}! Your account has been created.')
        return redirect('student_dashboard')

    return render(request, 'register.html', {'form_data': {}})