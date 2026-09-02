#
# This file is part of pretix (Community Edition).
#
# Copyright (C) 2014-2020  Raphael Michel and contributors
# Copyright (C) 2020-today pretix GmbH and contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General
# Public License as published by the Free Software Foundation in version 3 of the License.
#
# ADDITIONAL TERMS APPLY: Pursuant to Section 7 of the GNU Affero General Public License, additional terms are
# applicable granting you additional permissions and placing additional restrictions on your usage of this software.
# Please refer to the pretix LICENSE file to obtain the full terms applicable to this work. If you did not receive
# this file, see <https://pretix.eu/about/en/license>.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License along with this program.  If not, see
# <https://www.gnu.org/licenses/>.
#

# This file is based on an earlier version of pretix which was released under the Apache License 2.0. The full text of
# the Apache License 2.0 can be obtained at <http://www.apache.org/licenses/LICENSE-2.0>.
#
# This file may have since been changed and any changes are released under the terms of AGPLv3 as described above. A
# full history of changes and contributors is available at <https://github.com/pretix/pretix>.
#
# This file contains Apache-licensed contributions copyrighted by: Tobias Kunze
#
# Unless required by applicable law or agreed to in writing, software distributed under the Apache License 2.0 is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under the License.

import json
import random
from collections import OrderedDict
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.http import HttpRequest
from django.template.loader import get_template
from django.utils.translation import gettext, gettext_lazy as _
from i18nfield.fields import I18nFormField, I18nTextarea
from i18nfield.forms import I18nTextInput
from i18nfield.strings import LazyI18nString
from localflavor.generic.forms import BICFormField, IBANFormField
from localflavor.generic.validators import IBANValidator

from pretix.base.forms import I18nMarkdownTextarea
from pretix.base.models import InvoiceAddress, Order, OrderFee, OrderPayment, OrderRefund
from pretix.base.payment import BasePaymentProvider
from pretix.base.templatetags.money import money_filter
from pretix.helpers.payment import generate_payment_qr_codes
from pretix.plugins.banktransfer.templatetags.ibanformat import ibanformat
from pretix.presale.views.cart import cart_session


class BankTransfer(BasePaymentProvider):
    identifier = 'banktransfer_custom'
    verbose_name = _('Bank transfer (custom)')
    abort_pending_allowed = True
    VERIFICATION_INTERNAL_TYPE = 'banktransfer_custom_verification'
    SESSION_KEY = 'banktransfer_custom_verification'

    @staticmethod
    def form_fields():
        return OrderedDict([
            ('ack',
             forms.BooleanField(
                 label=_('I have understood that people will pay the ticket price directly to my bank account and '
                         'pretix cannot automatically know what payments arrived. Therefore, I will either mark '
                         'payments as complete manually, or regularly import a digital bank statement in order to '
                         'give pretix the required information.'),
                 required=True,
             )),
            ('bank_details_type', forms.ChoiceField(
                label=_('Bank account type'),
                widget=forms.RadioSelect,
                choices=(
                    ('sepa', _('SEPA bank account')),
                    ('other', _('Other bank account')),
                ),
                initial='sepa'
            )),
            ('bank_details_sepa_name', forms.CharField(
                label=_('Name of account holder'),
                help_text=_(
                    'Please note: special characters other than letters, numbers, and some punctuation can cause problems with some banks.'),
                widget=forms.TextInput(
                    attrs={
                        'data-display-dependency': '#id_payment_banktransfer_custom_bank_details_type_0',
                        'data-required-if': '#id_payment_banktransfer_custom_bank_details_type_0'
                    }
                ),
                required=False
            )),
            ('bank_details_sepa_iban', IBANFormField(
                label=_('IBAN'),
                required=False,
                widget=forms.TextInput(
                    attrs={
                        'data-display-dependency': '#id_payment_banktransfer_custom_bank_details_type_0',
                        'data-required-if': '#id_payment_banktransfer_custom_bank_details_type_0'
                    }
                ),
            )),
            ('bank_details_sepa_bic', BICFormField(
                label=_('BIC'),
                widget=forms.TextInput(
                    attrs={
                        'data-display-dependency': '#id_payment_banktransfer_custom_bank_details_type_0',
                        'data-required-if': '#id_payment_banktransfer_custom_bank_details_type_0'
                    }
                ),
                required=False
            )),
            ('bank_details_sepa_bank', forms.CharField(
                label=_('Name of bank'),
                widget=forms.TextInput(
                    attrs={
                        'data-display-dependency': '#id_payment_banktransfer_custom_bank_details_type_0',
                        'data-required-if': '#id_payment_banktransfer_custom_bank_details_type_0'
                    }
                ),
                required=False
            )),
            ('bank_details', I18nFormField(
                label=_('Bank account details'),
                widget=I18nMarkdownTextarea,
                help_text=_('Include everything else that your customers might need to send you a bank transfer payment, '
                            'such as account number and bank name. Do not mention a payment reference code here — '
                            'customers are identified by the unique transfer amount instead.'),
                widget_kwargs={'attrs': {
                    'rows': '4',
                    'placeholder': _(
                        'For SEPA accounts, you can leave this empty. Otherwise, please add everything that '
                        'your customers need to transfer the money, e.g. account numbers, routing numbers, '
                        'addresses, etc.'
                    ),
                }},
                required=False
            )),
            ('invoice_immediately',
             forms.BooleanField(
                 label=_('Create an invoice for orders using bank transfer immediately if the event is otherwise '
                         'configured to create invoices after payment is completed.'),
                 required=False,
             )),
            ('public_name', I18nFormField(
                label=_('Payment method name'),
                widget=I18nTextInput,
                required=False
            )),
            ('pending_description', I18nFormField(
                label=_('Additional text to show on pending orders'),
                help_text=_('This text will be shown on the order confirmation page for pending orders in addition to '
                            'the standard text about the exact transfer amount.'),
                widget=I18nTextarea,
                widget_kwargs={'attrs': {
                    'rows': '2',
                }},
                required=False,
            )),
            ('proof_upload_enabled', forms.BooleanField(
                label=_('Allow customers to upload proof of payment'),
                help_text=_('Shows an upload form on the order page while the payment is still pending.'),
                required=False,
                initial=True,
            )),
            ('proof_upload_help_text', I18nFormField(
                label=_('Help text for proof of payment upload'),
                widget=I18nTextarea,
                widget_kwargs={'attrs': {
                    'rows': '2',
                }},
                required=False,
            )),
            ('refund_iban_blocklist', forms.CharField(
                label=_('IBAN blocklist for refunds'),
                required=False,
                widget=forms.Textarea(attrs={'rows': 4}),
                help_text=_('Put one IBAN or IBAN prefix per line. The system will not attempt to send refunds to any '
                            'of these IBANs. Useful e.g. if you receive a lot of "forwarded payments" by a third-party payment '
                            'provider. You can also list country codes such as "GB" if you never want to send refunds to '
                            'IBANs from a specific country. The check digits will be ignored for comparison, so you '
                            'can e.g. ban DE0012345 to ban all German IBANs with the bank identifier starting with '
                            '12345.')
            )),
        ])

    @property
    def public_name(self):
        return str(self.settings.get('public_name', as_type=LazyI18nString) or self.verbose_name)

    @property
    def test_mode_message(self):
        return _('In test mode, you can just manually mark this order as paid in the backend after it has been '
                 'created.')

    @property
    def requires_invoice_immediately(self):
        return self.settings.get('invoice_immediately', False, as_type=bool)

    @property
    def settings_form_fields(self):
        more_fields_first = OrderedDict([
            ('_restricted_business',
             forms.BooleanField(
                 label=_('Restrict to business customers'),
                 help_text=_('Only allow choosing this payment provider for customers who enter an invoice address '
                             'and select "Business or institutional customer".'),
                 required=False,
             )),
        ])

        d = OrderedDict(
            list(super().settings_form_fields.items()) +
            list(more_fields_first.items()) +
            list(BankTransfer.form_fields().items())
        )
        d.move_to_end('invoice_immediately', last=False)
        d.move_to_end('bank_details', last=False)
        d.move_to_end('bank_details_sepa_bank', last=False)
        d.move_to_end('bank_details_sepa_bic', last=False)
        d.move_to_end('bank_details_sepa_iban', last=False)
        d.move_to_end('bank_details_sepa_name', last=False)
        d.move_to_end('bank_details_type', last=False)
        d.move_to_end('ack', last=False)
        d.move_to_end('_enabled', last=False)
        return d

    def settings_form_clean(self, cleaned_data):
        if cleaned_data.get('payment_banktransfer_custom_bank_details_type') == 'sepa':
            for f in (
                'bank_details_sepa_name', 'bank_details_sepa_bank', 'bank_details_sepa_bic',
                'bank_details_sepa_iban'
            ):
                if not cleaned_data.get('payment_banktransfer_custom_%s' % f):
                    raise ValidationError(
                        {'payment_banktransfer_custom_%s' % f: _('Please fill out your bank account details.')})
        else:
            if not cleaned_data.get('payment_banktransfer_custom_bank_details'):
                raise ValidationError(
                    {'payment_banktransfer_custom_bank_details': _('Please enter your bank account details.')})
        return cleaned_data

    def is_allowed(self, request: HttpRequest, total: Decimal=None) -> bool:
        def get_invoice_address():
            if not hasattr(request, '_checkout_flow_invoice_address'):
                cs = cart_session(request)
                iapk = cs.get('invoice_address')
                if not iapk:
                    request._checkout_flow_invoice_address = InvoiceAddress()
                else:
                    try:
                        request._checkout_flow_invoice_address = InvoiceAddress.objects.get(pk=iapk, order__isnull=True)
                    except InvoiceAddress.DoesNotExist:
                        request._checkout_flow_invoice_address = InvoiceAddress()
            return request._checkout_flow_invoice_address

        restricted_business = self.settings.get('_restricted_business', as_type=bool)
        if restricted_business:
            ia = get_invoice_address()
            if not ia.is_business:
                return False

        return super().is_allowed(request, total)

    def payment_form_render(self, request, total=None, order=None) -> str:
        template = get_template('pretixplugins/banktransfer_custom/checkout_payment_form.html')
        ctx = {
            'request': request,
            'event': self.event,
            'settings': self.settings,
            'order': order,
            'details': self.settings.get('bank_details', as_type=LazyI18nString),
        }
        return template.render(ctx)

    def calculate_fee(self, price: Decimal) -> Decimal:
        # Verification is added as a separate order fee line item (see signals).
        return Decimal('0.00')

    def checkout_prepare(self, request, cart):
        cs = cart_session(request)
        base_total = self._base_total_from_cart(cart)
        code, fee = self.get_or_create_verification(cs, base_total)
        self._sync_payment_info_verification(cs.get('payments', []), base_total, code, fee)
        return True

    def payment_prepare(self, request: HttpRequest, payment: OrderPayment):
        from django.db import transaction

        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=payment.order_id)
            payment = order.payments.select_for_update().get(pk=payment.pk)
            provider = BankTransfer(order.event)
            provider.apply_verification_fee_to_order(payment)
        return True

    @classmethod
    def verification_fee_from_info(cls, info_data, base_total=None):
        if not info_data:
            return None
        if 'verification_code' not in info_data or 'verification_fee' not in info_data:
            return None
        stored_base = info_data.get('verification_base_total')
        if stored_base is not None and base_total is not None and Decimal(stored_base) != base_total:
            return None
        return info_data['verification_code'], Decimal(info_data['verification_fee'])

    def get_or_create_verification(self, session, base_total: Decimal):
        stored = session.get(self.SESSION_KEY)
        if stored and Decimal(stored['base_total']) == base_total:
            return stored['code'], Decimal(stored['fee'])

        fee, code, _target = self._generate_verification(base_total)
        session[self.SESSION_KEY] = {
            'base_total': str(base_total),
            'code': code,
            'fee': str(fee),
        }
        return code, fee

    def make_verification_fee(self, code: str, fee_amount: Decimal) -> OrderFee:
        return OrderFee(
            fee_type=OrderFee.FEE_TYPE_OTHER,
            value=fee_amount,
            description=str(_('Unique code')),
            internal_type=self.VERIFICATION_INTERNAL_TYPE,
        )

    @staticmethod
    def get_verification_code(payment: OrderPayment):
        return (payment.info_data or {}).get('verification_code')

    @staticmethod
    def _sync_payment_info_verification(payment_requests, base_total: Decimal, code: str, fee: Decimal):
        for payment in payment_requests or []:
            if payment.get('provider') == BankTransfer.identifier:
                payment['info_data'] = {
                    **payment.get('info_data', {}),
                    'verification_code': code,
                    'verification_fee': str(fee),
                    'verification_base_total': str(base_total),
                }

    @staticmethod
    def _base_total_from_cart(cart) -> Decimal:
        if isinstance(cart, dict):
            fees = [
                fee for fee in cart.get('fees', [])
                if getattr(fee, 'internal_type', '') != BankTransfer.VERIFICATION_INTERNAL_TYPE
            ]
            positions = cart.get('raw') or cart.get('positions') or []
            return sum(position.price for position in positions) + sum(fee.value for fee in fees)
        return sum(position.price for position in cart)

    def build_verification_fee(self, payment_requests, base_total: Decimal, session=None):
        if not payment_requests:
            return None
        if not any(payment.get('provider') == self.identifier for payment in payment_requests):
            return None

        for payment in payment_requests:
            if payment.get('provider') != self.identifier:
                continue
            verified = self.verification_fee_from_info(payment.get('info_data'), base_total)
            if verified:
                code, fee = verified
                return self.make_verification_fee(code, fee)

        if session is not None:
            code, fee = self.get_or_create_verification(session, base_total)
            self._sync_payment_info_verification(payment_requests, base_total, code, fee)
            return self.make_verification_fee(code, fee)

        fee, code, _target = self._generate_verification(base_total)
        return self.make_verification_fee(code, fee)

    def apply_verification_fee_to_order(self, payment: OrderPayment) -> bool:
        order = payment.order
        if order.fees.filter(
            internal_type=self.VERIFICATION_INTERNAL_TYPE,
            canceled=False,
        ).exists():
            return False

        verified = self.verification_fee_from_info(payment.info_data)
        if verified:
            code, fee = verified
        else:
            base_total = order.total
            fee, code, _target = self._generate_verification(base_total, exclude_payment_pk=payment.pk)

        fee_obj = self.make_verification_fee(code, fee)
        fee_obj.order = order
        fee_obj._calculate_tax(event=self.event)
        fee_obj.save()

        order.total += fee
        order.save(update_fields=['total'])
        order.create_transactions()

        payment.amount = order.pending_sum
        payment.info_data = {
            **payment.info_data,
            'verification_code': code,
            'verification_fee': str(fee),
            'verification_base_total': str(order.total - fee),
        }
        payment.save(update_fields=['amount', 'info'])
        return True

    @classmethod
    def get_verification_fee(cls, order: Order):
        return order.fees.filter(
            internal_type=cls.VERIFICATION_INTERNAL_TYPE,
            canceled=False,
        ).first()

    def payment_is_valid_session(self, request):
        return True

    def checkout_confirm_render(self, request, order=None):
        return self.payment_form_render(request, order=order)

    def order_pending_mail_render(self, order, payment) -> str:
        t = gettext("Please transfer the full amount to the following bank account:")
        t += "\n\n"

        md_nl2br = "  \n"
        amount_label = _("Amount (transfer exactly this amount)")
        if self.settings.get('bank_details_type') == 'sepa':
            bankdetails = (
                (amount_label, money_filter(payment.amount, self.event.currency)),
                (_("Account holder"), self.settings.get('bank_details_sepa_name')),
                (_("IBAN"), ibanformat(self.settings.get('bank_details_sepa_iban'))),
                (_("BIC"), self.settings.get('bank_details_sepa_bic')),
                (_("Bank"), self.settings.get('bank_details_sepa_bank')),
            )
        else:
            bankdetails = (
                (amount_label, money_filter(payment.amount, self.event.currency)),
            )
        t += md_nl2br.join([f"**{k}:** {v}" for k, v in bankdetails])
        if self.settings.get('bank_details', as_type=LazyI18nString):
            t += md_nl2br
        t += str(self.settings.get('bank_details', as_type=LazyI18nString))
        return t

    def payment_pending_render(self, request: HttpRequest, payment: OrderPayment):
        from pretix_banktransfer_custom.forms import PaymentProofUploadForm
        from pretix_banktransfer_custom.models import PaymentProof

        template = get_template('pretixplugins/banktransfer_custom/pending.html')
        proof_upload_enabled = self.settings.get('proof_upload_enabled', True, as_type=bool)
        proof = None
        if proof_upload_enabled:
            try:
                proof = payment.banktransfer_custom_proof
            except PaymentProof.DoesNotExist:
                pass
        ctx = {
            'event': self.event,
            'order': payment.order,
            'payment': payment,
            'amount': payment.amount,
            'verification_code': self.get_verification_code(payment),
            'payment_info': payment.info_data,
            'settings': self.settings,
            'payment_qr_codes': generate_payment_qr_codes(
                event=self.event,
                code=payment.order.full_code,
                amount=payment.amount,
                bank_details_sepa_bic=self.settings.get('bank_details_sepa_bic'),
                bank_details_sepa_name=self.settings.get('bank_details_sepa_name'),
                bank_details_sepa_iban=self.settings.get('bank_details_sepa_iban'),
            ) if self.settings.bank_details_type == "sepa" else None,
            'pending_description': self.settings.get('pending_description', as_type=LazyI18nString),
            'proof_upload_help_text': self.settings.get('proof_upload_help_text', as_type=LazyI18nString),
            'proof_upload_enabled': proof_upload_enabled,
            'proof': proof,
            'proof_upload_form': PaymentProofUploadForm() if proof_upload_enabled else None,
            'details': self.settings.get('bank_details', as_type=LazyI18nString),
            'has_invoices': payment.order.invoices.exists(),
        }
        return template.render(ctx, request=request)

    def payment_control_render(self, request: HttpRequest, payment: OrderPayment) -> str:
        warning = None
        if not self.payment_refund_supported(payment):
            warning = _("Invalid IBAN/BIC")
        return self._render_control_info(request, payment.order, payment.info_data, payment=payment, warning=warning)

    def _render_control_info(self, request, order, info_data, payment=None, **extra_context):
        from pretix_banktransfer_custom.models import PaymentProof

        template = get_template('pretixplugins/banktransfer_custom/control.html')
        proof = None
        if payment:
            try:
                proof = payment.banktransfer_custom_proof
            except PaymentProof.DoesNotExist:
                pass
        ctx = {'request': request, 'event': self.event,
               'amount': payment.amount if payment else None,
               'verification_code': self.get_verification_code(payment) if payment else None,
               'payment_info': info_data, 'order': order,
               'payment': payment, 'proof': proof,
               **extra_context}
        return template.render(ctx)

    def _get_used_transfer_amounts(self, exclude_payment_pk=None):
        qs = OrderPayment.objects.filter(
            order__event=self.event,
            provider=self.identifier,
            state__in=(
                OrderPayment.PAYMENT_STATE_CREATED,
                OrderPayment.PAYMENT_STATE_PENDING,
            ),
        )
        if exclude_payment_pk:
            qs = qs.exclude(pk=exclude_payment_pk)
        return set(qs.values_list('amount', flat=True))

    def _generate_verification(self, base_total: Decimal, exclude_payment_pk=None):
        used_amounts = self._get_used_transfer_amounts(exclude_payment_pk)
        target = base_total
        for _ in range(100):
            target = self._apply_unique_amount_suffix(base_total)
            if target != base_total and target not in used_amounts:
                break
        fee = target - base_total
        return fee, self._verification_code_for_target(target), target

    @staticmethod
    def _verification_code_for_target(target: Decimal) -> str:
        if target == target.quantize(Decimal('1'), rounding=ROUND_DOWN):
            return str(int(target) % 100).zfill(2)
        cents = int((target.quantize(Decimal('0.01'), rounding=ROUND_DOWN) * 100) % 100)
        return str(cents).zfill(2)

    @staticmethod
    def _apply_unique_amount_suffix(amount: Decimal) -> Decimal:
        """
        Add a unique suffix to the payment amount without ever decreasing it.
        Whole-number amounts (e.g. IDR): randomize the last two digits upward.
        Decimal amounts (e.g. EUR): randomize the last two decimal places upward.
        """
        if amount == amount.quantize(Decimal('1'), rounding=ROUND_DOWN):
            integer_amount = int(amount)
            last_two = integer_amount % 100
            prefix = integer_amount - last_two
            if last_two < 99:
                suffix = random.randint(last_two + 1, 99)
                return Decimal(prefix + suffix)
            return Decimal(prefix + 100 + random.randint(1, 99))

        quantized = amount.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        cents = int((quantized * 100) % 100)
        whole = int(quantized)
        if cents < 99:
            new_cents = random.randint(cents + 1, 99)
            return Decimal(whole) + Decimal(new_cents) / Decimal('100')
        return Decimal(whole + 1) + Decimal(random.randint(1, 99)) / Decimal('100')

    def _code(self, order, force=False):
        prefix = self.settings.get('prefix', default='')
        li = order.invoices.last()
        invoice_number = li.number if self.settings.get('include_invoice_number', as_type=bool) and li else ''

        invoice_will_be_generated = (
            not li and
            self.settings.get('include_invoice_number', as_type=bool) and
            order.event.settings.get('invoice_generate') == 'paid' and
            self.requires_invoice_immediately
        )
        if invoice_will_be_generated and not force:
            return None

        code = " ".join((prefix, order.full_code, invoice_number)).strip(" ")

        if self.settings.get('omit_hyphen', as_type=bool):
            code = code.replace('-', '')

        return code

    def shred_payment_info(self, obj):
        from pretix_banktransfer_custom.models import PaymentProof

        if not obj.info_data:
            pass
        else:
            d = obj.info_data
            d['reference'] = '█'
            d['payer'] = '█'
            if 'send_invoice_to' in d:
                d['send_invoice_to'] = '█'
            d['_shredded'] = True
            obj.info = json.dumps(d)
            obj.save(update_fields=['info'])

        try:
            proof = obj.banktransfer_custom_proof
        except PaymentProof.DoesNotExist:
            return
        if proof.file:
            proof.file.delete(save=False)
        proof.delete()

    @staticmethod
    def norm(s):
        return s.strip().upper().replace(" ", "")

    def payment_refund_supported(self, payment: OrderPayment) -> bool:
        if not all(payment.info_data.get(key) for key in ("payer", "iban")):
            return False
        try:
            iban = self.norm(payment.info_data['iban'])
            IBANValidator()(iban)
        except ValidationError:
            return False
        else:
            def _compare(iban, prefix):  # Compare IBAN with pretix ignoring the check digits
                iban = iban[:2] + iban[4:]
                prefix = prefix[:2] + prefix[4:]
                return iban.startswith(prefix)

            return not any(_compare(iban, b) for b in (self.settings.refund_iban_blocklist or '').splitlines() if b)

    def payment_partial_refund_supported(self, payment: OrderPayment) -> bool:
        return self.payment_refund_supported(payment)

    def payment_control_render_short(self, payment: OrderPayment) -> str:
        pi = payment.info_data or {}
        r = pi.get('payer', '')
        if pi.get('iban'):
            if r:
                r += ' / '
            r += pi.get('iban')
        if pi.get('bic'):
            if r:
                r += ' / '
            r += pi.get('bic')
        return r

    def payment_presale_render(self, payment: OrderPayment) -> str:
        pi = payment.info_data or {}
        if self.payment_refund_supported(payment):
            try:
                iban = self.norm(pi['iban'])
                return gettext('Bank account {iban}').format(
                    iban=iban[0:2] + '****' + iban[-4:]
                )
            except:
                pass
        return super().payment_presale_render(payment)

    def execute_refund(self, refund: OrderRefund):
        """
        We just keep a created refund object. It will be marked as done using the control view
        for bank transfer refunds.
        """
        if refund.info_data.get('iban'):
            return  # we're already done here

        if refund.payment is None:
            raise ValueError(_("Can only create a bank transfer refund from an existing payment."))

        refund.info_data = {
            'payer': refund.payment.info_data['payer'],
            'iban': self.norm(refund.payment.info_data['iban']),
            'bic': self.norm(refund.payment.info_data['bic']) if refund.payment.info_data.get('bic') else None,
        }
        refund.save(update_fields=["info"])

    def refund_control_render(self, request: HttpRequest, refund: OrderRefund) -> str:
        return self._render_control_info(request, refund.order, refund.info_data)

    class NewRefundForm(forms.Form):
        payer = forms.CharField(
            label=_('Account holder'),
        )
        iban = IBANFormField(
            label=_('IBAN'),
        )
        bic = BICFormField(
            label=_('BIC (optional)'),
            required=False,
        )

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            for n, f in self.fields.items():
                f.required = False
                f.widget.is_required = False

        def clean_payer(self):
            val = self.cleaned_data.get('payer')
            if not val:
                raise ValidationError(_("This field is required."))
            return val

        def clean_iban(self):
            val = self.cleaned_data.get('iban')
            if not val:
                raise ValidationError(_("This field is required."))
            return val

    def new_refund_control_form_render(self, request: HttpRequest, order: Order) -> str:
        f = self.NewRefundForm(
            prefix="refund-banktransfer-custom",
            data=request.POST if request.method == "POST" and request.POST.get("refund-banktransfer-custom-iban") else None,
        )
        template = get_template('pretixplugins/banktransfer_custom/new_refund_control_form.html')
        ctx = {
            'form': f,
        }
        return template.render(ctx)

    def new_refund_control_form_process(self, request: HttpRequest, amount: Decimal, order: Order) -> OrderRefund:
        f = self.NewRefundForm(
            prefix="refund-banktransfer-custom",
            data=request.POST
        )
        if not f.is_valid():
            raise ValidationError(_('Your input was invalid, please see below for details.'))
        d = {
            'payer': f.cleaned_data['payer'],
            'iban': self.norm(f.cleaned_data['iban']),
        }
        if f.cleaned_data.get('bic'):
            d['bic'] = f.cleaned_data['bic']
        return OrderRefund(
            order=order,
            payment=None,
            state=OrderRefund.REFUND_STATE_CREATED,
            amount=amount,
            provider=self.identifier,
            info=json.dumps(d)
        )
