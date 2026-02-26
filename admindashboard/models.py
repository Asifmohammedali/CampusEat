from django.db import models

# Create your models here.
from django.core.exceptions import ValidationError
from django.db import models



class User(models.Model):

    ROLE_CHOICES = (
        ("ADMIN", "Admin"),
        ("STAFF", "Staff"),
        ("STUDENT", "Student"),
    )

    name             = models.CharField(max_length=150)
    admission_number = models.CharField(max_length=50, unique=True, null=True, blank=True)  # mandatory for STUDENT only
    email            = models.EmailField(unique=True)
    phone            = models.CharField(max_length=15, blank=True)
    password         = models.CharField(max_length=255)  # store hashed password
    role             = models.CharField(max_length=10, choices=ROLE_CHOICES, default="STUDENT")
    is_blocked       = models.BooleanField(default=False)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users"

    def clean(self):
        if self.role == "STUDENT" and not self.admission_number:
            raise ValidationError({"admission_number": "Admission number is required for students."})

    def __str__(self):
        return f"{self.name} ({self.role})"
    
class Category(models.Model):
    name       = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "categories"

    def __str__(self):
        return self.name
    

class Item(models.Model):
    name        = models.CharField(max_length=150)
    category    = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='items')
    description = models.TextField(blank=True)
    price       = models.DecimalField(max_digits=8, decimal_places=2)
    image       = models.ImageField(upload_to='items/', blank=True, null=True)
    is_available = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "items"

    def __str__(self):
        return f"{self.name} ({self.category.name})"
    
class Menu(models.Model):

    STATUS_CHOICES = (
        ("AVAILABLE",   "Available"),
        ("UNAVAILABLE", "Unavailable"),
    )

    item       = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='menu_entries')
    date_added = models.DateField(auto_now_add=True)
    time_added = models.TimeField(auto_now_add=True)
    status     = models.CharField(max_length=15, choices=STATUS_CHOICES, default="AVAILABLE")

    class Meta:
        db_table = "menu"

    def __str__(self):
        return f"{self.item.name} — {self.status} ({self.date_added})"
    




    

