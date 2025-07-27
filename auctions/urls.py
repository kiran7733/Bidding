from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('auctions/', views.auction_list, name='auction_list'),
    path('auction/<int:pk>/', views.auction_detail, name='auction_detail'),
    path('auction/<int:pk>/bid/', views.place_bid, name='place_bid'),
    path('auction/<int:pk>/extend/', views.extend_auction_time, name='extend_auction_time'),
    path('auction/<int:pk>/delete/', views.delete_auction, name='delete_auction'),
    path('auction/<int:pk>/manage/', views.manage_auction, name='manage_auction'),  # Add this line
    path('bid/<int:bid_id>/delete/', views.delete_bid, name='delete_bid'),
    path('create/', views.create_auction, name='create_auction'),
    path('my-auctions/', views.my_auctions, name='my_auctions'),
]
