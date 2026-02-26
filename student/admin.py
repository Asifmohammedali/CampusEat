from django.contrib import admin

# Register your models here.
from .models import Wallet,Order,CartItem
admin.site.register(Order)  
admin.site.register(CartItem)
admin.site.register(Wallet) 
