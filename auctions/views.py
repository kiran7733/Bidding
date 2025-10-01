from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Max
from django.http import JsonResponse
from django.db import transaction
from datetime import timedelta
from .models import AuctionItem, Category, Bid, AuctionExtension
from .forms import AuctionItemForm, BidForm, ExtendTimeForm
from accounts.models import Wallet, WalletTransaction


def auto_close_expired_auctions():
    """Helper function to auto-close expired auctions"""
    expired_auctions = AuctionItem.objects.filter(
        status__in=['active', 'extended'],  # Include both active and extended auctions
        end_time__lte=timezone.now()
    )
    
    for auction in expired_auctions:
        auction.status = 'closed'
        highest_bid = auction.bids.filter(is_deleted=False).order_by('-amount').first()
        if highest_bid:
            auction.winner = highest_bid.bidder
        auction.save()
    
    return expired_auctions.count()


def home(request):
    # Auto-close expired auctions first
    auto_close_expired_auctions()
    
    # Get active auctions
    active_auctions = AuctionItem.objects.filter(
        status__in=['active', 'extended'],
        end_time__gt=timezone.now()
    ).order_by('-created_at')[:6]
    
    categories = Category.objects.all()
    
    # Get some statistics
    total_auctions = AuctionItem.objects.filter(status__in=['active', 'extended']).count()
    total_bids = Bid.objects.filter(is_deleted=False).count()
    
    context = {
        'active_auctions': active_auctions,
        'categories': categories,
        'total_auctions': total_auctions,
        'total_bids': total_bids,
    }
    return render(request, 'auctions/home.html', context)


def auction_list(request):
    # Auto-close expired auctions before displaying
    auto_close_expired_auctions()
    
    # Get active auctions
    auctions = AuctionItem.objects.filter(
        status__in=['active', 'extended'],
        end_time__gt=timezone.now()
    ).order_by('-created_at')
    
    # Search functionality
    query = request.GET.get('q')
    if query:
        auctions = auctions.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )
    
    # Category filter
    category_id = request.GET.get('category')
    if category_id:
        auctions = auctions.filter(category_id=category_id)
    
    # Sorting
    sort_by = request.GET.get('sort', '-created_at')
    if sort_by in ['-created_at', 'current_price', '-current_price', 'end_time']:
        auctions = auctions.order_by(sort_by)
    
    # Pagination
    paginator = Paginator(auctions, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    categories = Category.objects.all()
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'current_category': category_id,
        'query': query,
        'current_sort': sort_by,
    }
    return render(request, 'auctions/auction_list.html', context)


def auction_detail(request, pk):
    auction = get_object_or_404(AuctionItem, pk=pk)
    
    # Auto-close expired auctions
    auto_close_expired_auctions()
    
    # Refresh auction object in case it was updated
    auction.refresh_from_db()
    
    # Get valid bids only
    bids = auction.bids.filter(is_deleted=False).order_by('-timestamp')[:10]
    user_bids = None
    user_highest_bid = None
    current_highest_bid = None
    
    # Get the current highest bid
    current_highest_bid = auction.bids.filter(is_deleted=False).order_by('-amount').first()
    
    # Calculate minimum bid for display
    if current_highest_bid:
        min_bid_amount = current_highest_bid.amount + 1
    else:
        min_bid_amount = auction.starting_price
    
    if request.user.is_authenticated:
        # Get ALL user's bids for this auction (not deleted)
        user_bids = auction.bids.filter(bidder=request.user, is_deleted=False).order_by('-timestamp')
        user_highest_bid = user_bids.first()
    
    context = {
        'auction': auction,
        'bids': bids,
        'user_bids': user_bids,
        'user_highest_bid': user_highest_bid,
        'current_highest_bid': current_highest_bid,
        'min_bid_amount': min_bid_amount,
        'bid_form': BidForm(auction=auction) if request.user.is_authenticated else None,
        'extend_form': ExtendTimeForm() if request.user.is_authenticated else None,
    }
    return render(request, 'auctions/auction_detail.html', context)


@login_required
def place_bid(request, pk):
    auction = get_object_or_404(AuctionItem, pk=pk)
    
    if not auction.is_active():
        messages.error(request, 'This auction is no longer active.')
        return redirect('auction_detail', pk=pk)
    
    if request.user == auction.seller:
        messages.error(request, 'You cannot bid on your own auction.')
        return redirect('auction_detail', pk=pk)
    
    if request.method == 'POST':
        form = BidForm(request.POST, auction=auction)
        if form.is_valid():
            bid_amount = form.cleaned_data['amount']
            
            # Form validation already checks minimum bid, so we can proceed
            # Get user's wallet (create if doesn't exist)
            wallet, created = Wallet.objects.get_or_create(user=request.user)
            
            # Check if user has sufficient balance
            if not wallet.has_sufficient_balance(bid_amount):
                messages.error(request, f'Insufficient wallet balance. You need ₹{bid_amount} but have ₹{wallet.balance}. Please add funds to your wallet.')
                return redirect('auction_detail', pk=pk)
            
            try:
                with transaction.atomic():
                    # Deduct funds from wallet
                    new_balance = wallet.deduct_funds(bid_amount)
                    
                    # Create transaction record
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        transaction_type='bid_placed',
                        amount=bid_amount,
                        balance_after=new_balance,
                        description=f'Bid placed on {auction.title}'
                    )
                    
                    # Create new bid
                    Bid.objects.create(
                        item=auction,
                        bidder=request.user,
                        amount=bid_amount
                    )
                    
                    # Update auction current price
                    auction.current_price = bid_amount
                    auction.save()
                    
                    messages.success(request, f'Your bid of ₹{bid_amount} has been placed successfully! Funds deducted from your wallet.')
                    
            except ValueError as e:
                messages.error(request, f'Error processing bid: {str(e)}')
        else:
            # Form validation errors will be displayed
            pass
    
    return redirect('auction_detail', pk=pk)


@login_required
def delete_bid(request, bid_id):
    bid = get_object_or_404(Bid, id=bid_id, bidder=request.user, is_deleted=False)
    
    # Check if auction is still active
    if not bid.item.is_active():
        messages.error(request, 'Cannot delete bids on inactive auctions.')
        return redirect('auction_detail', pk=bid.item.pk)
    
    if request.method == 'POST':
        # Check if bid can be deleted at the time of deletion
        if not bid.can_be_deleted():
            messages.error(request, 'This bid cannot be deleted. Either the time limit has exceeded or it\'s currently the highest bid.')
            return redirect('auction_detail', pk=bid.item.pk)
        
        try:
            with transaction.atomic():
                # Get user's wallet (create if doesn't exist)
                wallet, created = Wallet.objects.get_or_create(user=request.user)
                
                # Refund the bid amount
                new_balance = wallet.add_funds(bid.amount)
                
                # Create transaction record for refund
                WalletTransaction.objects.create(
                    wallet=wallet,
                    transaction_type='bid_refund',
                    amount=bid.amount,
                    balance_after=new_balance,
                    description=f'Bid refund for {bid.item.title}'
                )
                
                # Perform soft delete
                bid.soft_delete()
                messages.success(request, f'Your bid of ₹{bid.amount} has been successfully deleted and refunded to your wallet.')
                
        except ValueError as e:
            messages.error(request, f'Error processing refund: {str(e)}')
            return redirect('auction_detail', pk=bid.item.pk)
        
        return redirect('auction_detail', pk=bid.item.pk)
    
    # Show confirmation page
    context = {
        'bid': bid,
        'can_delete': bid.can_be_deleted(),
        'is_highest': bid == bid.item.bids.filter(is_deleted=False).order_by('-amount').first()
    }
    return render(request, 'auctions/delete_bid.html', context)


@login_required
def extend_auction_time(request, pk):
    auction = get_object_or_404(AuctionItem, pk=pk)
    
    # Only allow the auction seller/owner to extend time
    if request.user != auction.seller:
        messages.error(request, 'Only the auction owner can extend auction time.')
        return redirect('auction_detail', pk=pk)
    
    if not auction.can_extend_time():
        messages.error(request, 'This auction cannot be extended further.')
        return redirect('auction_detail', pk=pk)
    
    if request.method == 'POST':
        form = ExtendTimeForm(request.POST)
        if form.is_valid():
            extension_hours = int(form.cleaned_data['extension_hours'])
            reason = form.cleaned_data['reason']
            
            old_end_time = auction.end_time
            new_end_time = auction.end_time + timedelta(hours=extension_hours)
            
            # Create extension record
            AuctionExtension.objects.create(
                auction=auction,
                extended_by=request.user,
                old_end_time=old_end_time,
                new_end_time=new_end_time,
                extension_reason=reason
            )
            
            # Update auction
            auction.end_time = new_end_time
            auction.time_extensions += 1
            if auction.time_extensions > 0:
                auction.status = 'extended'
            auction.save()
            
            messages.success(request, f'Auction extended by {extension_hours} hours successfully!')
            return redirect('auction_detail', pk=pk)
    else:
        form = ExtendTimeForm()
    
    return render(request, 'auctions/extend_auction.html', {'form': form, 'auction': auction})


@login_required
def delete_auction(request, pk):
    auction = get_object_or_404(AuctionItem, pk=pk, seller=request.user)
    
    if not auction.can_be_deleted_by_seller():
        messages.error(request, 'This auction cannot be deleted. Either the time limit has passed (10 minutes) or there are existing bids.')
        return redirect('auction_detail', pk=pk)
    
    if request.method == 'POST':
        auction_title = auction.title
        auction.delete()
        messages.success(request, f'Auction "{auction_title}" has been deleted successfully.')
        return redirect('my_auctions')
    
    context = {
        'auction': auction,
        'can_delete': auction.can_be_deleted_by_seller(),
        'time_left_to_delete': max(0, (auction.created_at + timedelta(minutes=10) - timezone.now()).total_seconds())
    }
    return render(request, 'auctions/delete_auction.html', context)


@login_required
def create_auction(request):
    if request.method == 'POST':
        form = AuctionItemForm(request.POST, request.FILES)
        if form.is_valid():
            auction = form.save(commit=False)
            auction.seller = request.user
            auction.current_price = auction.starting_price
            auction.original_end_time = auction.end_time  # Store original end time
            auction.save()
            messages.success(request, 'Your auction has been created successfully!')
            return redirect('auction_detail', pk=auction.pk)
    else:
        form = AuctionItemForm()
    
    return render(request, 'auctions/create_auction.html', {'form': form})


@login_required
def my_auctions(request):
    # Auto-close expired auctions first
    auto_close_expired_auctions()
    
    selling = AuctionItem.objects.filter(seller=request.user).order_by('-created_at')
    bidding = AuctionItem.objects.filter(
        bids__bidder=request.user, 
        bids__is_deleted=False
    ).distinct().order_by('-created_at')
    won_auctions = AuctionItem.objects.filter(winner=request.user).order_by('-end_time')
    
    context = {
        'selling': selling,
        'bidding': bidding,
        'won_auctions': won_auctions,
    }
    return render(request, 'auctions/my_auctions.html', context)


# Additional utility views for AJAX functionality (optional)
@login_required
def get_auction_status(request, pk):
    """AJAX endpoint to get real-time auction status"""
    auction = get_object_or_404(AuctionItem, pk=pk)
    
    # Auto-close if expired
    if auction.status == 'active' and timezone.now() >= auction.end_time:
        auction.status = 'closed'
        highest_bid = auction.bids.filter(is_deleted=False).order_by('-amount').first()
        if highest_bid:
            auction.winner = highest_bid.bidder
        auction.save()
    
    data = {
        'status': auction.status,
        'current_price': float(auction.current_price),
        'time_remaining': auction.time_remaining().total_seconds() if auction.time_remaining() else 0,
        'bid_count': auction.bids.filter(is_deleted=False).count(),
        'is_active': auction.is_active(),
    }
    
    return JsonResponse(data)


@login_required
def get_recent_bids(request, pk):
    """AJAX endpoint to get recent bids for live updates"""
    auction = get_object_or_404(AuctionItem, pk=pk)
    recent_bids = auction.bids.filter(is_deleted=False).order_by('-timestamp')[:5]
    
    bids_data = []
    for bid in recent_bids:
        bids_data.append({
            'bidder': bid.bidder.username,
            'amount': float(bid.amount),
            'timestamp': bid.timestamp.isoformat(),
            'is_current_user': bid.bidder == request.user,
        })

    return JsonResponse({'bids': bids_data})
@login_required
def manage_auction(request, pk):
    auction = get_object_or_404(AuctionItem, pk=pk, seller=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_description':
            new_description = request.POST.get('description')
            if new_description:
                auction.description = new_description
                auction.save()
                messages.success(request, 'Description updated successfully!')
        
        elif action == 'update_image':
            if 'image' in request.FILES:
                auction.image = request.FILES['image']
                auction.save()
                messages.success(request, 'Image updated successfully!')
        
        elif action == 'end_auction':
            if auction.status == 'active':
                auction.status = 'closed'
                highest_bid = auction.bids.filter(is_deleted=False).order_by('-amount').first()
                if highest_bid:
                    auction.winner = highest_bid.bidder
                auction.save()
                messages.success(request, 'Auction ended successfully!')
            else:
                messages.error(request, 'Can only end active auctions.')
        
        return redirect('auction_detail', pk=pk)
    
    context = {
        'auction': auction,
    }
    return render(request, 'auctions/manage_auction.html', context)

