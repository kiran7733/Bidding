from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('auctions/', views.auction_list, name='auction_list'),  # This handles browse auctions
    path('auction/<int:pk>/', views.auction_detail, name='auction_detail'),
    path('auction/<int:pk>/bid/', views.place_bid, name='place_bid'),
    path('auction/<int:pk>/delete/', views.delete_auction, name='delete_auction'),
    path('create/', views.create_auction, name='create_auction'),
    path('my-auctions/', views.my_auctions, name='my_auctions'),
]
