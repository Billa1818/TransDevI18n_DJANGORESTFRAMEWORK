# =============================================================================
# APP: subscriptions (Gestion des abonnements et paiements)
# =============================================================================

# subscriptions/models.py
from django.db import models
from django.conf import settings
from decimal import Decimal

class SubscriptionPlan(models.Model):
    """Plans d'abonnement disponibles"""
    PLAN_TYPES = [
        ('free', 'Free'),
        ('basic', 'Basic'),
        ('pro', 'Pro'),
        ('enterprise', 'Enterprise'),
    ]
    
    name = models.CharField(max_length=50)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES, unique=True)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    yearly_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    # Limites
    daily_word_limit = models.IntegerField()
    monthly_word_limit = models.IntegerField(blank=True, null=True)
    max_file_size = models.BigIntegerField()  # en bytes
    max_concurrent_tasks = models.IntegerField(default=1)
    
    # Fonctionnalités
    features = models.JSONField(default=list)  # Liste des fonctionnalités
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} - {self.monthly_price}€/mois"

class Subscription(models.Model):
    """Abonnements utilisateurs"""
    BILLING_CYCLES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    billing_cycle = models.CharField(max_length=10, choices=BILLING_CYCLES, default='monthly')
    
    # Dates
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    next_billing_date = models.DateTimeField()
    
    # Statut
    is_active = models.BooleanField(default=True)
    is_cancelled = models.BooleanField(default=False)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    
    # Stripe
    stripe_subscription_id = models.CharField(max_length=255, blank=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    
    # Usage tracking
    current_word_usage = models.IntegerField(default=0)
    last_usage_reset = models.DateTimeField(auto_now_add=True)
    
    def get_remaining_words(self):
        """Calcule les mots restants pour la période"""
        if self.billing_cycle == 'monthly':
            return max(0, self.plan.monthly_word_limit - self.current_word_usage)
        return max(0, self.plan.daily_word_limit - self.user.daily_word_count)
    
    def can_translate(self, word_count):
        """Vérifie si l'utilisateur peut traduire"""
        return self.get_remaining_words() >= word_count
    
    def __str__(self):
        return f"{self.user.email} - {self.plan.name}"

class Payment(models.Model):
    """Historique des paiements"""
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='EUR')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS)
    
    # Stripe
    stripe_payment_id = models.CharField(max_length=255, blank=True)
    stripe_invoice_id = models.CharField(max_length=255, blank=True)
    
    # Timestamps
    payment_date = models.DateTimeField(auto_now_add=True)
    
    # Métadonnées
    payment_method = models.CharField(max_length=50, blank=True)
    failure_reason = models.TextField(blank=True)
    
    def __str__(self):
        return f"Payment {self.id} - {self.amount}€ - {self.payment_status}"
