from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.conf import settings
import razorpay
from .forms import CustomUserCreationForm, AddFundsForm, WithdrawFundsForm
from .models import Wallet, WalletTransaction, WalletPayment

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
    """Start Razorpay order for adding funds, redirect to checkout"""
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = AddFundsForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            # Razorpay uses paise. Convert ₹ to paise
            amount_paise = int(amount * 100)
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            rzp_order = client.order.create(dict(amount=amount_paise, currency='INR', payment_capture=1))
            
            # Save a pending WalletPayment
            WalletPayment.objects.create(
                user=request.user,
                amount=amount,
                order_id=rzp_order.get('id'),
                status='created',
                notes=rzp_order.get('notes') if isinstance(rzp_order, dict) else None
            )
            
            context = {
                'wallet': wallet,
                'amount': amount,
                'amount_paise': amount_paise,
                'order_id': rzp_order.get('id'),
                'razorpay_key_id': settings.RAZORPAY_KEY_ID,
                'callback_url': request.build_absolute_uri('/accounts/wallet/verify/'),
                'user_email': request.user.email or '',
                'user_name': request.user.get_full_name() or request.user.username,
            }
            return render(request, 'accounts/razorpay_checkout.html', context)
    else:
        form = AddFundsForm()
    
    context = {
        'form': form,
        'wallet': wallet,
    }
    return render(request, 'accounts/add_funds.html', context)

@login_required
def verify_payment(request):
    """Handle Razorpay callback: verify signature and credit wallet"""
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('wallet')
    
    params_dict = {
        'razorpay_order_id': request.POST.get('razorpay_order_id'),
        'razorpay_payment_id': request.POST.get('razorpay_payment_id'),
        'razorpay_signature': request.POST.get('razorpay_signature')
    }
    
    try:
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        client.utility.verify_payment_signature(params_dict)
    except razorpay.errors.SignatureVerificationError:
        # Mark failed
        WalletPayment.objects.filter(order_id=params_dict['razorpay_order_id']).update(status='failed')
        messages.error(request, 'Payment verification failed.')
        return redirect('add_funds')
    
    # Signature valid: credit wallet
    payment = WalletPayment.objects.select_for_update().get(order_id=params_dict['razorpay_order_id'])
    if payment.status == 'success':
        # Idempotent
        messages.success(request, 'Payment already processed.')
        return redirect('wallet')
    
    payment.payment_id = params_dict['razorpay_payment_id']
    payment.signature = params_dict['razorpay_signature']
    payment.status = 'success'
    
    with transaction.atomic():
        payment.save()
        wallet, _ = Wallet.objects.get_or_create(user=payment.user)
        new_balance = wallet.add_funds(payment.amount)
        WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type='deposit',
            amount=payment.amount,
            balance_after=new_balance,
            description=f'Razorpay payment {payment.payment_id}'
        )
    
    messages.success(request, 'Payment successful! Funds added to your wallet.')
    return redirect('wallet')

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
