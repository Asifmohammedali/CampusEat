"""
URL configuration for CanteenSystem project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from CanteenSystem import views as c_views
from admindashboard import views as a_views 
from student import views as s_views
from Staff import views as st_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/',  c_views.login_view,  name='login'),
    path('logout/', c_views.logout_view, name='logout'),
    path('register/', c_views.register, name='register'),
    path('admindashboard/', a_views.admin_dashboard, name='admin_dashboard'),
    path('category/',           a_views.manage_category,  name='manage_category'),
    path('category/add/',       a_views.manage_category,  name='add_category'),
    path('category/<int:category_id>/delete/', a_views.delete_category, name='delete_category'),
    path('items/',a_views.manage_items, name='manage_items'),
    path('items/<int:item_id>/delete/', a_views.delete_item,  name='delete_item'),
    path('prepare_menu/', a_views.prepare_menu, name='prepare_menu'),
    path('', a_views.landing, name='landing'),
    path('wallet_recharge/', a_views.recharge_wallet, name='recharge_wallet'),
    path('admindassboard/transactions/', a_views.transaction_history, name='transaction_history'),
    path('studentdashboard/', s_views.student_dashboard,    name='student_dashboard'),
    path('cart/', s_views.view_cart,            name='view_cart'),
    path('cart/add/', s_views.add_to_cart,          name='add_to_cart'),
    path('cart/update/', s_views.update_cart,          name='update_cart'),
    path('cart/remove/<int:cart_item_id>/', s_views.remove_cart_item, name='remove_cart_item'),
    path('order/place/', s_views.place_order,          name='place_order'),
    path('orders/', s_views.order_history_student, name='order_history_student'),
    path('wallet/', s_views.student_wallet,       name='student_wallet'),
    path('admin_revenue/', a_views.revenue, name='revenue'),
    path('admin_orders/', a_views.order_history, name='order_history'),
    path('admin_order/<int:order_id>/detail/', a_views.order_detail, name='order_detail'),
    path('manage_staff/',a_views.manage_staff,         name='manage_staff'),
    path('manage_staff/<int:staff_id>/delete/', a_views.delete_staff,         name='delete_staff'),
    path('manage_students/', a_views.manage_students,       name='manage_students'),
    path('manage_students/<int:student_id>/delete/', a_views.delete_student,  name='delete_student'),
    path('manage_students/<int:student_id>/block/', a_views.toggle_block_student, name='toggle_block_student'),
    path('staff/',st_views.staff_dashboard,  name='staff_dashboard'),
    path('staff/menu/',               st_views.staff_prepare_menu,     name='staff_prepare_menu'),
    path('staff/orders/manage/',      st_views.staff_order_management, name='staff_order_management'),
    path('staff/orders/<int:order_id>/detail/',    st_views.order_detail_partial,       name='staff_order_detail_partial'),
    path('staff/orders/<int:order_id>/status/',    st_views.update_order_status,        name='update_order_status'),
    path('staff/orders/history/',     st_views.staff_order_history,    name='staff_order_history'),
    path('staff/orders/<int:order_id>/receipt/', st_views.print_receipt, name='print_receipt'),
    path('order-status/', s_views.student_order_status, name='student_order_status'),
    path('admin/', admin.site.urls),  
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)