#
# Database models are provided by pretix.plugins.banktransfer (built-in).
# This plugin only adds a custom payment provider and matching logic on top.
#
from pretix.plugins.banktransfer import models as _banktransfer_models

BankImportJob = _banktransfer_models.BankImportJob
BankTransaction = _banktransfer_models.BankTransaction
RefundExport = _banktransfer_models.RefundExport
paymentproof_name = getattr(_banktransfer_models, 'paymentproof_name', None)
PaymentProof = getattr(_banktransfer_models, 'PaymentProof', None)

__all__ = [
    'BankImportJob',
    'BankTransaction',
    'PaymentProof',
    'RefundExport',
    'paymentproof_name',
]
