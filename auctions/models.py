from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse

class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Categories"

class AuctionItem(models.Model):
    AUCTION_STATUS = [
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('pending', 'Pending'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='selling_items')
    starting_price = models.DecimalField(max_digits=10, decimal_places=2)
    current_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    image = models.ImageField(upload_to='auction_images/', blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField()
    status = models.CharField(max_length=10, choices=AUCTION_STATUS, default='active')
    winner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='won_items')
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('auction_detail', kwargs={'pk': self.pk})
    
    def is_active(self):
        return self.status == 'active' and timezone.now() < self.end_time
    
    def time_remaining(self):
        if self.end_time > timezone.now():
            return self.end_time - timezone.now()
        return None

class Bid(models.Model):
    item = models.ForeignKey(AuctionItem, on_delete=models.CASCADE, related_name='bids')
    bidder = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    timestamp = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"${self.amount} on {self.item.title} by {self.bidder.username}"
    
    class Meta:
        ordering = ['-timestamp']

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
