from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('profile/', views.profile, name='profile'),
    path('wallet/', views.wallet_view, name='wallet'),
    path('wallet/add-funds/', views.add_funds, name='add_funds'),
    path('wallet/verify/', views.verify_payment, name='verify_payment'),
    path('wallet/withdraw-funds/', views.withdraw_funds, name='withdraw_funds'),
    path('wallet/transactions/', views.transaction_history, name='transaction_history'),
]
