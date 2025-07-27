from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Max
from django.http import JsonResponse
from .models import AuctionItem, Category, Bid
from .forms import AuctionItemForm, BidForm

def home(request):
    # Get active auctions
    active_auctions = AuctionItem.objects.filter(
        status='active',
        end_time__gt=timezone.now()
    ).order_by('-created_at')[:6]
    
    categories = Category.objects.all()
    
    # Get some statistics
    total_auctions = AuctionItem.objects.filter(status='active').count()
    total_bids = Bid.objects.count()
    
    context = {
        'active_auctions': active_auctions,
        'categories': categories,
        'total_auctions': total_auctions,
        'total_bids': total_bids,
    }
    return render(request, 'auctions/home.html', context)

def auction_list(request):
    auctions = AuctionItem.objects.filter(
        status='active',
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
    bids = auction.bids.all()[:10]  # Latest 10 bids
    user_highest_bid = None
    
    if request.user.is_authenticated:
        user_highest_bid = auction.bids.filter(bidder=request.user).order_by('-amount').first()
    
    context = {
        'auction': auction,
        'bids': bids,
        'bid_form': BidForm() if request.user.is_authenticated else None,
        'user_highest_bid': user_highest_bid,
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
        form = BidForm(request.POST)
        if form.is_valid():
            bid_amount = form.cleaned_data['amount']
            
            # Check if bid is higher than current price
            if bid_amount > auction.current_price:
                # Create new bid
                Bid.objects.create(
                    item=auction,
                    bidder=request.user,
                    amount=bid_amount
                )
                
                # Update auction current price
                auction.current_price = bid_amount
                auction.save()
                
                messages.success(request, f'Your bid of ${bid_amount} has been placed successfully!')
            else:
                messages.error(request, f'Your bid must be higher than the current price of ${auction.current_price}.')
        else:
            messages.error(request, 'Please enter a valid bid amount.')
    
    return redirect('auction_detail', pk=pk)

@login_required
def create_auction(request):
    if request.method == 'POST':
        form = AuctionItemForm(request.POST, request.FILES)
        if form.is_valid():
            auction = form.save(commit=False)
            auction.seller = request.user
            auction.current_price = auction.starting_price
            auction.save()
            messages.success(request, 'Your auction has been created successfully!')
            return redirect('auction_detail', pk=auction.pk)
    else:
        form = AuctionItemForm()
    
    return render(request, 'auctions/create_auction.html', {'form': form})

@login_required
def my_auctions(request):
    selling = AuctionItem.objects.filter(seller=request.user).order_by('-created_at')
    bidding = AuctionItem.objects.filter(bids__bidder=request.user).distinct().order_by('-created_at')
    won_auctions = AuctionItem.objects.filter(winner=request.user).order_by('-end_time')
    
    context = {
        'selling': selling,
        'bidding': bidding,
        'won_auctions': won_auctions,
    }
    return render(request, 'auctions/my_auctions.html', context)

@login_required
def delete_auction(request, pk):
    auction = get_object_or_404(AuctionItem, pk=pk, seller=request.user)
    
    # Only allow deletion if no bids have been placed
    if auction.bids.exists():
        messages.error(request, 'Cannot delete auction with existing bids.')
        return redirect('auction_detail', pk=pk)
    
    if request.method == 'POST':
        auction.delete()
        messages.success(request, 'Auction deleted successfully.')
        return redirect('my_auctions')
    
    return render(request, 'auctions/delete_auction.html', {'auction': auction})
