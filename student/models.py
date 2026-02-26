from django.db import models
from admindashboard.models import User,Item

# Create your models here.
class Cart(models.Model):
    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cart"

    def __str__(self):
        return f"Cart of {self.user.name}"


class CartItem(models.Model):
    cart     = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    order    = models.ForeignKey('Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='cart_items')
    item     = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='cart_items')
    price    = models.DecimalField(max_digits=8, decimal_places=2)   # snapshot of price at time of adding
    quantity = models.PositiveIntegerField(default=1)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)  # price × quantity

    class Meta:
        db_table = "cart_items"

    def save(self, *args, **kwargs):
        self.subtotal = self.price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity}× {self.item.name} in {self.cart}"


class Order(models.Model):

    STATUS_CHOICES = (
        ("PENDING",    "Pending"),
        ("CONFIRMED",  "Confirmed"),
        ("PREPARING",  "Preparing"),
        ("READY",      "Ready"),
        ("COMPLETED",  "Completed"),
        ("CANCELLED",  "Cancelled"),
        ("REJECTED",   "Rejected"),
        ("DELIVERED",  "Delivered"),
    )

    user            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    accepted_by     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='accepted_orders')
    total_amount    = models.DecimalField(max_digits=10, decimal_places=2)
    status          = models.CharField(max_length=15, choices=STATUS_CHOICES, default="PENDING")
    date            = models.DateField(auto_now_add=True)
    ordered_at      = models.DateTimeField(auto_now_add=True)
    delivered_at    = models.DateTimeField(null=True, blank=True)
    rejected_reason = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "orders"

    def __str__(self):
        return f"Order #{self.id} — {self.user.name} ({self.status})"
    


class Wallet(models.Model):

    TRANSACTION_CHOICES = (
        ("CREDIT", "Credit"),   # recharge / refund
        ("DEBIT",  "Debit"),    # order payment
        ("RETURN", "Return"), # refund for cancelled/rejected order
    )

    user             = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wallet_transactions')
    balance          = models.DecimalField(max_digits=10, decimal_places=2)   # balance after this transaction
    amount           = models.DecimalField(max_digits=10, decimal_places=2)   # transaction amount
    transaction_type = models.CharField(max_length=6, choices=TRANSACTION_CHOICES)
    order            = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='wallet_transactions')
    date             = models.DateField(auto_now_add=True)
    time             = models.TimeField(auto_now_add=True)

    class Meta:
        db_table = "wallet"

    def __str__(self):
        return f"{self.transaction_type} ₹{self.amount} — {self.user.name} ({self.date})"

