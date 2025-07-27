from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import AuctionItem, Bid

@receiver(post_save, sender=Bid)
def update_auction_winner(sender, instance, created, **kwargs):
    """Update auction winner when it ends"""
    if created:
        auction = instance.item
        # Check if auction has ended
        if timezone.now() >= auction.end_time and auction.status == 'active':
            auction.status = 'closed'
            # Set the highest bidder as winner
            highest_bid = auction.bids.order_by('-amount').first()
            if highest_bid:
                auction.winner = highest_bid.bidder
            auction.save()
