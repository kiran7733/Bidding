from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import Wallet

class Command(BaseCommand):
    help = 'Create wallets for existing users who don\'t have them'

    def handle(self, *args, **options):
        users_without_wallets = User.objects.filter(wallet__isnull=True)
        
        created_count = 0
        for user in users_without_wallets:
            wallet, created = Wallet.objects.get_or_create(user=user)
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created wallet for user: {user.username}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} wallets')
        )
