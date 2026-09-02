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
from django.urls import include, re_path

from pretix.api.urls import orga_router
from pretix.multidomain import event_url
from pretix_banktransfer_custom.api import BankImportJobViewSet

from . import views
from .presale_views import PaymentProofDownloadView, PaymentProofUploadView

event_patterns = [
    re_path(r'^banktransfer_custom/', include([
        event_url(
            r'^order/(?P<order>[^/]+)/(?P<secret>[^/]+)/payment/(?P<payment>[0-9]+)/proof/$',
            PaymentProofUploadView.as_view(),
            name='proof.upload',
        ),
        event_url(
            r'^order/(?P<order>[^/]+)/(?P<secret>[^/]+)/payment/(?P<payment>[0-9]+)/proof/download/$',
            PaymentProofDownloadView.as_view(),
            name='proof.download',
        ),
    ])),
]

urlpatterns = [
    re_path(r'^control/organizer/(?P<organizer>[^/]+)/banktransfer_custom/import/',
            views.OrganizerImportView.as_view(),
            name='import'),
    re_path(r'^control/organizer/(?P<organizer>[^/]+)/banktransfer_custom/job/(?P<job>\d+)/',
            views.OrganizerJobDetailView.as_view(), name='import.job'),
    re_path(r'^control/organizer/(?P<organizer>[^/]+)/banktransfer_custom/action/',
            views.OrganizerActionView.as_view(), name='import.action'),
    re_path(r'^control/organizer/(?P<organizer>[^/]+)/banktransfer_custom/refunds/',
            views.OrganizerRefundExportListView.as_view(), name='refunds.list'),
    re_path(r'^control/organizer/(?P<organizer>[^/]+)/banktransfer_custom/export/(?P<id>\d+)/$',
            views.OrganizerDownloadRefundExportView.as_view(),
            name='refunds.download'),
    re_path(r'^control/organizer/(?P<organizer>[^/]+)/banktransfer_custom/sepa-export/(?P<id>\d+)/$',
            views.OrganizerSepaXMLExportView.as_view(),
            name='refunds.sepa'),

    re_path(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/banktransfer_custom/import/',
            views.EventImportView.as_view(),
            name='import'),
    re_path(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/banktransfer_custom/job/(?P<job>\d+)/',
            views.EventJobDetailView.as_view(), name='import.job'),
    re_path(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/banktransfer_custom/action/',
            views.EventActionView.as_view(), name='import.action'),
    re_path(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/banktransfer_custom/refunds/',
            views.EventRefundExportListView.as_view(),
            name='refunds.list'),
    re_path(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/banktransfer_custom/export/(?P<id>\d+)/$',
            views.EventDownloadRefundExportView.as_view(),
            name='refunds.download'),
    re_path(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/banktransfer_custom/sepa-export/(?P<id>\d+)/$',
            views.EventSepaXMLExportView.as_view(),
            name='refunds.sepa'),
    re_path(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/banktransfer_custom/order/(?P<code>[^/]+)/payment/(?P<payment>[0-9]+)/proof/$',
            views.PaymentProofDownloadView.as_view(),
            name='proof.download'),
]

orga_router.register('bankimportjobs-custom', BankImportJobViewSet, basename='bankimportjob-custom')
