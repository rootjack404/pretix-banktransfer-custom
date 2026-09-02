#
# Import/job models are provided by pretix.plugins.banktransfer (built-in).
# PaymentProof is defined here because older pretix builds do not include it.
#
import os
import string

from django.db import models
from django.utils.crypto import get_random_string
from django.utils.encoding import escape_uri_path

from pretix.plugins.banktransfer import models as _banktransfer_models

BankImportJob = _banktransfer_models.BankImportJob
BankTransaction = _banktransfer_models.BankTransaction
RefundExport = _banktransfer_models.RefundExport


def paymentproof_name(instance, filename: str) -> str:
    secret = get_random_string(length=32, allowed_chars=string.ascii_letters + string.digits)
    event = instance.payment.order.event
    return 'cachedfiles/paymentproofs/{org}/{ev}/{secret}.{filename}'.format(
        org=event.organizer.slug,
        ev=event.slug,
        secret=secret,
        filename=escape_uri_path(os.path.basename(filename)),
    )


class PaymentProof(models.Model):
    payment = models.OneToOneField(
        'pretixbase.OrderPayment',
        related_name='banktransfer_custom_proof',
        on_delete=models.CASCADE,
    )
    file = models.FileField(upload_to=paymentproof_name, max_length=255)
    filename = models.CharField(max_length=255)
    uploaded = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-uploaded',)


__all__ = [
    'BankImportJob',
    'BankTransaction',
    'PaymentProof',
    'RefundExport',
    'paymentproof_name',
]
