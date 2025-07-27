from django.core.management.base import BaseCommand
from django.utils import timezone
from auctions.models import AuctionItem

class Command(BaseCommand):
    help = 'Close expired auctions and set winners'
    
    def handle(self, *args, **options):
        now = timezone.now()
        expired_auctions = AuctionItem.objects.filter(
            end_time__lte=now,
            status='active'
        )
        
        for auction in expired_auctions:
            auction.status = 'closed'
            # Find the highest bidder
            highest_bid = auction.bids.order_by('-amount').first()
            if highest_bid:
                auction.winner = highest_bid.bidder
            auction.save()
            
        self.stdout.write(
            self.style.SUCCESS(f'Closed {expired_auctions.count()} expired auctions')
        )
