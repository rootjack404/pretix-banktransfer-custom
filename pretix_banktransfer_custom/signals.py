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
from django.dispatch import receiver
from django.template.loader import get_template
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _, pgettext_lazy

from pretix.base.signals import order_fee_calculation, order_placed, register_payment_providers
from pretix.presale.signals import fee_calculation_for_cart
from pretix.presale.views.cart import cart_session
from pretix.control.signals import html_head, nav_event, nav_organizer

from pretix.base.logentrytypes import (
    ClearDataShredderMixin, OrderLogEntryType, log_entry_types,
)
from .payment import BankTransfer


@receiver(register_payment_providers, dispatch_uid="payment_banktransfer_custom")
def register_payment_provider(sender, **kwargs):
    return BankTransfer


@receiver(fee_calculation_for_cart, dispatch_uid="banktransfer_custom_fee_calculation_for_cart")
def add_verification_fee_to_cart(sender, request, total, payment_requests, **kwargs):
    provider = BankTransfer(sender)
    fee = provider.build_verification_fee(payment_requests, total, session=cart_session(request))
    return [fee] if fee else []


@receiver(order_fee_calculation, dispatch_uid="banktransfer_custom_order_fee_calculation")
def add_verification_fee_to_order(sender, total, payment_requests, **kwargs):
    provider = BankTransfer(sender)
    fee = provider.build_verification_fee(payment_requests, total)
    return [fee] if fee else []


@receiver(order_placed, dispatch_uid="banktransfer_custom_order_placed")
def store_verification_code_on_payment(sender, order, **kwargs):
    provider = BankTransfer(order.event)
    verification_fee = provider.get_verification_fee(order)
    if not verification_fee:
        return
    for payment in order.payments.filter(provider=BankTransfer.identifier):
        if payment.info_data.get('verification_code'):
            continue
        payment.info_data = {
            **payment.info_data,
            'verification_fee': str(verification_fee.value),
        }
        payment.save(update_fields=['info'])


@receiver(nav_event, dispatch_uid="payment_banktransfer_custom_nav")
def control_nav_import(sender, request=None, **kwargs):
    url = resolve(request.path_info)
    if not request.user.has_event_permission(request.organizer, request.event, 'event.orders:write', request=request):
        return []
    return [
        {
            'label': _("Bank transfer"),
            'url': reverse('plugins:banktransfer_custom:import', kwargs={
                'event': request.event.slug,
                'organizer': request.event.organizer.slug,
            }),
            'icon': 'university',
            'children': [
                {
                    'label': _('Import bank data'),
                    'url': reverse('plugins:banktransfer_custom:import', kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    }),
                    'active': (url.namespace == 'plugins:banktransfer_custom' and url.url_name == 'import'),
                },
                {
                    'label': _('Export refunds'),
                    'url': reverse('plugins:banktransfer_custom:refunds.list', kwargs={
                        'event': request.event.slug,
                        'organizer': request.event.organizer.slug,
                    }),
                    'active': (url.namespace == 'plugins:banktransfer_custom' and url.url_name.startswith("refunds")),
                },
            ]
        },
    ]


@receiver(nav_organizer, dispatch_uid="payment_banktransfer_custom_organav")
def control_nav_orga_import(sender, request=None, **kwargs):
    url = resolve(request.path_info)
    has_any_event_perm = request.user.get_events_with_permission(
        "event.orders:write", request=request
    ).filter(organizer=request.organizer).exists()
    if not has_any_event_perm:
        return []
    return [
        {
            'label': _("Bank transfer"),
            'url': reverse('plugins:banktransfer_custom:import', kwargs={
                'organizer': request.organizer.slug,
            }),
            'icon': 'university',
            'children': [
                {
                    'label': _('Import bank data'),
                    'url': reverse('plugins:banktransfer_custom:import', kwargs={
                        'organizer': request.organizer.slug,
                    }),
                    'active': (url.namespace == 'plugins:banktransfer_custom' and url.url_name == 'import'),
                    'icon': 'upload',
                },
                {
                    'label': _('Export refunds'),
                    'url': reverse('plugins:banktransfer_custom:refunds.list', kwargs={
                        'organizer': request.organizer.slug,
                    }),
                    'active': (url.namespace == 'plugins:banktransfer_custom' and url.url_name.startswith("refunds")),
                },
            ]
        }
    ]


@receiver(html_head, dispatch_uid="banktransfer_custom_html_head")
def html_head_presale(sender, request=None, **kwargs):
    url = resolve(request.path_info)
    if url.namespace == 'plugins:banktransfer_custom':
        template = get_template('pretixplugins/banktransfer_custom/control_head.html')
        return template.render({})
    else:
        return ""


@log_entry_types.new()
class BanktransferOrderEmailInvoiceLogEntryType(OrderLogEntryType, ClearDataShredderMixin):
    # For backwards-compatibility only
    action_type = 'pretix_banktransfer_custom.order.email.invoice'
    plain = _('The invoice was sent to the designated email address.')


@log_entry_types.new()
class BanktransferProofUploadedLogEntryType(OrderLogEntryType):
    action_type = 'pretix_banktransfer_custom.proof.uploaded'
    plain = pgettext_lazy('banktransfer_log', 'A proof of payment was uploaded.')
