from django.db import models

class BaseModel(models.Model):
    """Abstract base model with timestamps"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]  # Orders by newest first


class MpesaCalls(BaseModel):
    """Stores all M-Pesa API call logs"""
    business = models.ForeignKey(
        "business_api.Business",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mpesa_calls",
    )
    shortcode = models.ForeignKey(
        "business_api.MpesaShortcode",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mpesa_calls",
    )
    ip_address = models.GenericIPAddressField()
    caller = models.TextField()
    conversation_id = models.TextField(blank=True, null=True, db_index=True)
    content = models.TextField()

    class Meta:
        verbose_name = "Mpesa Call"
        verbose_name_plural = "Mpesa Calls"

    def __str__(self):
        return f"Mpesa Call from {self.caller} - {self.created_at}"


class MpesaPayment(BaseModel):
    """Stores completed or failed STK push payments"""
    business = models.ForeignKey(
        "business_api.Business",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mpesa_payments",
    )
    shortcode = models.ForeignKey(
        "business_api.MpesaShortcode",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mpesa_payments",
    )
    merchant_request_id = models.CharField(max_length=100, blank=True, null=True)
    checkout_request_id = models.CharField(max_length=100, blank=True, null=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    product_type = models.CharField(max_length=60, blank=True, default="")
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    mpesa_receipt_number = models.CharField(max_length=50, blank=True, null=True)
    transaction_date = models.DateTimeField(null=True, blank=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    status = models.CharField(
    max_length=20,
    choices=[("successful", "Successful"), ("failed", "Failed"), ("pending", "Pending")],
    default="pending")
    result_code = models.IntegerField(null=True, blank=True)
    result_description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Transaction {self.transaction_id} - {self.status}"


class MpesaCallBacks(BaseModel):
    """Stores callback responses from M-Pesa"""
    business = models.ForeignKey(
        "business_api.Business",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mpesa_callbacks",
    )
    shortcode = models.ForeignKey(
        "business_api.MpesaShortcode",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mpesa_callbacks",
    )
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    caller = models.CharField(max_length=50)
    conversation_id = models.CharField(max_length=100, blank=True, null=True)
    content = models.JSONField()
    result_code = models.IntegerField(null=True, blank=True)
    result_description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Callback - {self.conversation_id}"


class StkPushInitiation(BaseModel):
    """Maps STK push initiation response IDs back to a business/shortcode.

    STK callbacks do not reliably include BusinessShortCode, so we persist the
    CheckoutRequestID at initiation time and use it to resolve tenancy later.
    """

    business = models.ForeignKey(
        "business_api.Business",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stk_push_initiations",
    )
    shortcode = models.ForeignKey(
        "business_api.MpesaShortcode",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stk_push_initiations",
    )

    merchant_request_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    checkout_request_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    account_reference = models.CharField(max_length=64, blank=True, default="")
    product_type = models.CharField(max_length=60, blank=True, default="")

    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]



class StkPushCallback(BaseModel):
    """Stores STK Push callback responses"""
    ip_address = models.GenericIPAddressField()
    merchant_request_id = models.CharField(max_length=100)
    checkout_request_id = models.CharField(max_length=100)
    response_code = models.CharField(max_length=10)
    response_description = models.TextField()
    customer_message = models.TextField()
    status = models.CharField(max_length=20, choices=[("successful", "Successful"), ("failed", "Failed"), ("pending", "Pending")], default="pending")

    class Meta:
        verbose_name = "STK Push Callback"
        verbose_name_plural = "STK Push Callbacks"

    def __str__(self):
        return f"STK Push Callback - {self.merchant_request_id}"


class StkPushError(BaseModel):
    """Stores STK Push error responses"""
    ip_address = models.GenericIPAddressField()
    merchant_request_id = models.CharField(max_length=100)
    error_code = models.CharField(max_length=10)
    error_message = models.TextField()

    class Meta:
        verbose_name = "STK Push Error"
        verbose_name_plural = "STK Push Errors"

    def __str__(self):
        return f"STK Push Error - {self.merchant_request_id}"


class MpesaTransactionStatusQuery(BaseModel):
    """Stores Transaction Status Query lifecycle.

    - `response_payload` holds the synchronous Daraja response.
    - `result_payload` holds the asynchronous result callback payload.
    """

    business = models.ForeignKey(
        "business_api.Business",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mpesa_status_queries",
    )
    shortcode = models.ForeignKey(
        "business_api.MpesaShortcode",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mpesa_status_queries",
    )

    transaction_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    originator_conversation_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    conversation_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)

    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    result_payload = models.JSONField(default=dict, blank=True)

    result_code = models.IntegerField(null=True, blank=True)
    result_description = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=[("successful", "Successful"), ("failed", "Failed"), ("pending", "Pending")],
        default="pending",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Txn Status Query - {self.transaction_id or self.originator_conversation_id or ''}"
