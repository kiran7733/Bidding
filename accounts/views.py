from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from .forms import CustomUserCreationForm, AddFundsForm, WithdrawFundsForm
from .models import Wallet, WalletTransaction

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful! Your wallet has been created.')
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})

@login_required
def profile(request):
    return render(request, 'accounts/profile.html')

@login_required
def wallet_view(request):
    """Display user's wallet and transaction history"""
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    
    # Get recent transactions
    transactions = wallet.transactions.all()[:10]
    
    context = {
        'wallet': wallet,
        'transactions': transactions,
    }
    return render(request, 'accounts/wallet.html', context)

@login_required
def add_funds(request):
    """Add funds to user's wallet"""
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = AddFundsForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            
            try:
                with transaction.atomic():
                    # Add funds to wallet
                    new_balance = wallet.add_funds(amount)
                    
                    # Create transaction record
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        transaction_type='deposit',
                        amount=amount,
                        balance_after=new_balance,
                        description=f'Added ₹{amount} to wallet'
                    )
                    
                    messages.success(request, f'Successfully added ₹{amount} to your wallet!')
                    return redirect('wallet')
                    
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = AddFundsForm()
    
    context = {
        'form': form,
        'wallet': wallet,
    }
    return render(request, 'accounts/add_funds.html', context)

@login_required
def withdraw_funds(request):
    """Withdraw funds from user's wallet"""
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = WithdrawFundsForm(request.POST, wallet=wallet)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            
            try:
                with transaction.atomic():
                    # Deduct funds from wallet
                    new_balance = wallet.deduct_funds(amount)
                    
                    # Create transaction record
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        transaction_type='withdrawal',
                        amount=amount,
                        balance_after=new_balance,
                        description=f'Withdrew ₹{amount} from wallet'
                    )
                    
                    messages.success(request, f'Successfully withdrew ₹{amount} from your wallet!')
                    return redirect('wallet')
                    
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = WithdrawFundsForm(wallet=wallet)
    
    context = {
        'form': form,
        'wallet': wallet,
    }
    return render(request, 'accounts/withdraw_funds.html', context)

@login_required
def transaction_history(request):
    """Display full transaction history"""
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    
    # Paginate transactions
    transactions = wallet.transactions.all()
    paginator = Paginator(transactions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'wallet': wallet,
        'page_obj': page_obj,
    }
    return render(request, 'accounts/transaction_history.html', context)
