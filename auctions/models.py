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
        ('extended', 'Extended'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='selling_items')
    starting_price = models.DecimalField(max_digits=10, decimal_places=2)
    current_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    image = models.ImageField(upload_to='auction_images/', blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    original_end_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=10, choices=AUCTION_STATUS, default='active')
    winner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='won_items')
    time_extensions = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('auction_detail', kwargs={'pk': self.pk})
    
    def is_active(self):
        return self.status in ['active', 'extended'] and timezone.now() < self.end_time
    
    def time_remaining(self):
        if self.end_time > timezone.now():
            return self.end_time - timezone.now()
        return None
    
    def get_time_remaining_display(self):
        """Get a human-readable time remaining string"""
        time_left = self.time_remaining()
        if not time_left:
            return None
        
        total_seconds = int(time_left.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        
        if days > 0:
            return f"{days} day{'s' if days != 1 else ''} remaining"
        elif hours > 0:
            return f"{hours} hour{'s' if hours != 1 else ''} remaining"
        else:
            return f"{minutes} minute{'s' if minutes != 1 else ''} remaining"
    
    def update_current_price(self):
        highest_bid = self.bids.filter(is_deleted=False).order_by('-amount').first()
        if highest_bid:
            self.current_price = highest_bid.amount
        else:
            self.current_price = self.starting_price
        self.save()
    
    def can_extend_time(self):
        return self.status == 'active' and self.time_extensions < 3
    def can_be_managed_by_seller(self):
        """Check if auction can be managed by seller"""
        return True

    def can_be_ended_early(self):
        """Check if auction can be ended early by seller"""
        return self.status == 'active'

    def can_modify_description(self):
        """Check if description can be modified"""
        return True

    def can_modify_image(self):
        """Check if image can be modified"""
        return True

    def can_be_deleted_by_seller(self):
        """Check if auction can be deleted by seller within 10 minutes"""
        if self.status != 'active':
            return False
    
        time_limit = self.created_at + timezone.timedelta(minutes=10)
        within_time_limit = timezone.now() < time_limit
    
        has_bids = self.bids.filter(is_deleted=False).exists()
    
        return within_time_limit and not has_bids

    @property
    def can_be_deleted_by_seller_property(self):
        """Property version for template access"""
        return self.can_be_deleted_by_seller()

    @property
    def can_extend_time_property(self):
        """Property version for template access"""
        return self.can_extend_time()


class Bid(models.Model):
    item = models.ForeignKey(AuctionItem, on_delete=models.CASCADE, related_name='bids')
    bidder = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    timestamp = models.DateTimeField(default=timezone.now)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        status = " (Deleted)" if self.is_deleted else ""
        return f"₹{self.amount} on {self.item.title} by {self.bidder.username}{status}"
    
    def can_be_deleted(self):
        """Check if bid can be deleted by bidder"""
        if self == self.item.bids.filter(is_deleted=False).order_by('-amount').first():
            return False
        
        if not self.item.is_active():
            return False
        
        time_limit = self.timestamp + timezone.timedelta(minutes=5)
        return timezone.now() < time_limit

    @property
    def can_be_deleted_property(self):
        """Property version for template access"""
        return self.can_be_deleted()
    
    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()
        self.item.update_current_price()
    
    class Meta:
        ordering = ['-timestamp']

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"

class AuctionExtension(models.Model):
    auction = models.ForeignKey(AuctionItem, on_delete=models.CASCADE, related_name='extensions')
    extended_by = models.ForeignKey(User, on_delete=models.CASCADE)
    old_end_time = models.DateTimeField()
    new_end_time = models.DateTimeField()
    extension_reason = models.CharField(max_length=200)
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Extension for {self.auction.title} by {self.extended_by.username}"
