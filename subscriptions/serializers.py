
# =============================================================================
# APP: subscriptions - Serializers (Gestion des abonnements et paiements)
# =============================================================================

# subscriptions/serializers.py
from rest_framework import serializers
from .models import SubscriptionPlan, Subscription, Payment


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Serializer pour les plans d'abonnement"""
    yearly_discount = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionPlan
        fields = (
            'id', 'name', 'plan_type', 'monthly_price', 'yearly_price',
            'yearly_discount', 'daily_word_limit', 'monthly_word_limit',
            'max_file_size', 'max_concurrent_tasks', 'features', 'is_active'
        )
        read_only_fields = ('id', 'yearly_discount')

    def get_yearly_discount(self, obj):
        if obj.yearly_price and obj.monthly_price:
            yearly_equivalent = obj.monthly_price * 12
            discount = ((yearly_equivalent - obj.yearly_price) / yearly_equivalent) * 100
            return round(discount, 2)
        return None


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer pour les abonnements"""
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_type = serializers.CharField(source='plan.plan_type', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    remaining_words = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = (
            'id', 'user', 'user_email', 'plan', 'plan_name', 'plan_type',
            'billing_cycle', 'start_date', 'end_date', 'next_billing_date',
            'is_active', 'is_cancelled', 'cancelled_at', 'stripe_subscription_id',
            'stripe_customer_id', 'current_word_usage', 'last_usage_reset',
            'remaining_words', 'days_remaining'
        )
        read_only_fields = (
            'id', 'user_email', 'plan_name', 'plan_type', 'start_date',
            'current_word_usage', 'last_usage_reset', 'remaining_words',
            'days_remaining'
        )

    def get_remaining_words(self, obj):
        return obj.get_remaining_words()

    def get_days_remaining(self, obj):
        from django.utils import timezone
        if obj.end_date:
            delta = obj.end_date - timezone.now()
            return max(0, delta.days)
        return None


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer pour les paiements"""
    user_email = serializers.CharField(source='user.email', read_only=True)
    subscription_plan = serializers.CharField(source='subscription.plan.name', read_only=True)

    class Meta:
        model = Payment
        fields = (
            'id', 'user', 'user_email', 'subscription', 'subscription_plan',
            'amount', 'currency', 'payment_status', 'stripe_payment_id',
            'stripe_invoice_id', 'payment_date', 'payment_method', 'failure_reason'
        )
        read_only_fields = (
            'id', 'user_email', 'subscription_plan', 'payment_date'
        )
