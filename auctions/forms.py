from django import forms
from django.utils import timezone
from datetime import timedelta
from .models import AuctionItem, Bid

class AuctionItemForm(forms.ModelForm):
    class Meta:
        model = AuctionItem
        fields = ['title', 'description', 'category', 'starting_price', 'end_time', 'image']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'starting_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def clean_end_time(self):
        end_time = self.cleaned_data['end_time']
        if end_time <= timezone.now():
            raise forms.ValidationError("End time must be in the future.")
        if end_time <= timezone.now() + timedelta(hours=1):
            raise forms.ValidationError("Auction must run for at least 1 hour.")
        return end_time
    
    def clean_starting_price(self):
        starting_price = self.cleaned_data['starting_price']
        if starting_price <= 0:
            raise forms.ValidationError("Starting price must be greater than 0.")
        return starting_price

class BidForm(forms.ModelForm):
    class Meta:
        model = Bid
        fields = ['amount']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Enter bid amount',
                'step': '0.01',
                'min': '0.01'
            })
        }
    
    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise forms.ValidationError("Bid amount must be greater than 0.")
        return amount
