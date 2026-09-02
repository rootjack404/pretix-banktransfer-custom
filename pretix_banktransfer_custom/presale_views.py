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
import mimetypes
import os

from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from django.views import View

from pretix.base.models import OrderPayment
from pretix.multidomain.urlreverse import eventreverse
from pretix.presale.views import EventViewMixin
from pretix.presale.views.order import OrderDetailMixin

from .forms import PaymentProofUploadForm
from .models import PaymentProof


class BankTransferPaymentMixin:
    @cached_property
    def payment(self):
        return get_object_or_404(
            self.order.payments,
            pk=self.kwargs['payment'],
            provider='banktransfer_custom',
        )

    def get_order_redirect(self):
        return redirect(eventreverse(self.request.event, 'presale:event.order', kwargs={
            'order': self.order.code,
            'secret': self.order.secret,
        }))


class PaymentProofUploadView(EventViewMixin, OrderDetailMixin, BankTransferPaymentMixin, View):
    def post(self, request, *args, **kwargs):
        if self.payment.state in (
            OrderPayment.PAYMENT_STATE_CONFIRMED,
            OrderPayment.PAYMENT_STATE_REFUNDED,
            OrderPayment.PAYMENT_STATE_CANCELED,
        ):
            messages.error(request, _('This payment has already been processed.'))
            return self.get_order_redirect()

        provider = self.payment.payment_provider
        if not provider.settings.get('proof_upload_enabled', True, as_type=bool):
            raise Http404()

        form = PaymentProofUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            for field_errors in form.errors.values():
                for err in field_errors:
                    messages.error(request, err)
            return self.get_order_redirect()

        uploaded_file = form.cleaned_data['file']
        proof, created = PaymentProof.objects.get_or_create(payment=self.payment)
        if proof.file:
            proof.file.delete(save=False)
        proof.filename = uploaded_file.name
        proof.file.save(uploaded_file.name, uploaded_file, save=False)
        proof.save()

        self.order.log_action('pretix_banktransfer_custom.proof.uploaded', user=None, data={
            'payment': self.payment.local_id,
            'filename': proof.filename,
        })
        messages.success(request, _('Your proof of payment has been uploaded successfully.'))
        return self.get_order_redirect()


class PaymentProofDownloadView(EventViewMixin, OrderDetailMixin, BankTransferPaymentMixin, View):
    def get(self, request, *args, **kwargs):
        try:
            proof = self.payment.banktransfer_proof
        except PaymentProof.DoesNotExist:
            raise Http404()

        if not proof.file:
            raise Http404()

        ftype, ignored = mimetypes.guess_type(proof.file.name)
        resp = FileResponse(proof.file, content_type=ftype or 'application/octet-stream')
        resp['Content-Disposition'] = 'attachment; filename="{}"'.format(
            os.path.basename(proof.filename)
        )
        return resp
