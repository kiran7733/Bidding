from django.contrib import admin
from .models import Category, AuctionItem, Bid, UserProfile

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']

@admin.register(AuctionItem)
class AuctionItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'seller', 'starting_price', 'current_price', 'status', 'created_at']
    list_filter = ['status', 'category', 'created_at']
    search_fields = ['title', 'description']

@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ['item', 'bidder', 'amount', 'timestamp']
    list_filter = ['timestamp']

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_number']
